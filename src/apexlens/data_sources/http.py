"""HTTP client shared by all network source adapters.

Features: request timeouts, retries with exponential backoff (honouring ``Retry-After``),
client-side rate limiting, an on-disk response cache keyed by URL + parameters, a short-lived
negative cache for 404s, and bounded concurrency for batch downloads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

from apexlens.storage.io import sha256_bytes, write_bytes

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class FetchResult:
    url: str
    status: int | None
    content: bytes | None
    from_cache: bool = False
    retrieved_at: str = field(default_factory=utc_now_iso)
    content_hash: str | None = None
    cache_path: str | None = None
    error: str | None = None
    attempts: int = 0

    @property
    def ok(self) -> bool:
        return self.content is not None and self.status is not None and 200 <= self.status < 300

    def json(self):
        if self.content is None:
            raise ValueError(f"No content for {self.url}: {self.error}")
        return json.loads(self.content)


class RateLimiter:
    """Minimum spacing between requests plus an optional sliding-window budget."""

    def __init__(self, min_interval_s: float = 0.0, max_per_window: int | None = None, window_s: float = 3600.0,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep):
        self.min_interval_s = min_interval_s
        self.max_per_window = max_per_window
        self.window_s = window_s
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last = -1e18
        self._history: deque[float] = deque()

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            wait = self._last + self.min_interval_s - now
            if self.max_per_window:
                while self._history and now - self._history[0] > self.window_s:
                    self._history.popleft()
                if len(self._history) >= self.max_per_window:
                    wait = max(wait, self._history[0] + self.window_s - now)
            if wait > 0:
                self._sleep(wait)
                now = self._clock()
            self._last = now
            if self.max_per_window:
                self._history.append(now)


class HttpClient:
    def __init__(
        self,
        cache_dir: Path | None,
        timeout_s: float = 30.0,
        max_retries: int = 4,
        backoff_base_s: float = 1.0,
        rate_limiter: RateLimiter | None = None,
        user_agent: str = "ApexLens",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        negative_cache_ttl_s: float = 24 * 3600,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.rate_limiter = rate_limiter or RateLimiter()
        self._sleep = sleep
        self.negative_cache_ttl_s = negative_cache_ttl_s
        self._client = httpx.Client(
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
            transport=transport,
        )

    # -- cache -----------------------------------------------------------------------------
    @staticmethod
    def cache_key(url: str, params: dict | None = None) -> str:
        full = url + ("?" + urlencode(sorted(params.items())) if params else "")
        return hashlib.sha256(full.encode()).hexdigest()

    def _cache_paths(self, key: str) -> tuple[Path, Path] | None:
        if not self.cache_dir:
            return None
        base = self.cache_dir / "http" / key[:2]
        return base / f"{key}.bin", base / f"{key}.meta.json"

    def _read_cache(self, key: str, url: str) -> FetchResult | None:
        paths = self._cache_paths(key)
        if not paths:
            return None
        body, meta_path = paths
        if not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            return None
        if meta.get("status") == 404:
            age = time.time() - meta.get("cached_epoch", 0)
            if age > self.negative_cache_ttl_s:
                return None
            return FetchResult(url=url, status=404, content=None, from_cache=True,
                               retrieved_at=meta.get("retrieved_at", ""), error="not found (cached)")
        if not body.exists():
            return None
        content = body.read_bytes()
        return FetchResult(url=url, status=meta.get("status", 200), content=content, from_cache=True,
                           retrieved_at=meta.get("retrieved_at", ""), content_hash=sha256_bytes(content),
                           cache_path=str(body))

    def _write_cache(self, key: str, res: FetchResult) -> None:
        paths = self._cache_paths(key)
        if not paths:
            return
        body, meta_path = paths
        meta = {"url": res.url, "status": res.status, "retrieved_at": res.retrieved_at, "cached_epoch": time.time()}
        if res.content is not None:
            write_bytes(body, res.content)
            res.cache_path = str(body)
        write_bytes(meta_path, json.dumps(meta).encode())

    # -- requests --------------------------------------------------------------------------
    def get(self, url: str, params: dict | None = None, use_cache: bool = True) -> FetchResult:
        key = self.cache_key(url, params)
        if use_cache:
            cached = self._read_cache(key, url)
            if cached is not None:
                return cached

        attempts = 0
        last_error = None
        status = None
        while attempts <= self.max_retries:
            attempts += 1
            self.rate_limiter.acquire()
            retry_after = None
            try:
                resp = self._client.get(url, params=params)
                status = resp.status_code
                if 200 <= status < 300:
                    content = resp.content
                    res = FetchResult(url=url, status=status, content=content, content_hash=sha256_bytes(content),
                                      attempts=attempts)
                    self._write_cache(key, res)
                    return res
                if status == 404:
                    res = FetchResult(url=url, status=404, content=None, error="not found", attempts=attempts)
                    self._write_cache(key, res)
                    return res
                last_error = f"HTTP {status}"
                if status not in RETRYABLE_STATUS:
                    break
                ra = resp.headers.get("Retry-After")
                if ra and ra.isdigit():
                    retry_after = float(ra)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                status = None
            if attempts > self.max_retries:
                break
            delay = retry_after if retry_after is not None else self.backoff_base_s * (2 ** (attempts - 1))
            log.warning("retrying %s after %s (attempt %d): %s", url, delay, attempts, last_error)
            self._sleep(delay)
        return FetchResult(url=url, status=status, content=None, error=last_error, attempts=attempts)

    def fetch_many(self, requests: Iterable[tuple[str, dict | None]], max_workers: int = 4) -> list[FetchResult]:
        reqs = list(requests)
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as pool:
            return list(pool.map(lambda r: self.get(r[0], r[1]), reqs))

    def close(self) -> None:
        self._client.close()
