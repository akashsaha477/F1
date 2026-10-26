import httpx

from apexlens.data_sources.http import HttpClient, RateLimiter


def make_client(tmp_path, handler, retries=3):
    sleeps = []
    client = HttpClient(cache_dir=tmp_path, max_retries=retries, backoff_base_s=1.0,
                        transport=httpx.MockTransport(handler), sleep=sleeps.append)
    return client, sleeps


def test_retries_with_exponential_backoff_then_succeeds(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=b'{"ok": true}')

    client, sleeps = make_client(tmp_path, handler)
    res = client.get("https://example.test/a")
    assert res.ok and res.json() == {"ok": True}
    assert res.attempts == 3
    assert sleeps == [1.0, 2.0]


def test_retry_after_header_is_honoured(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, content=b"x")

    client, sleeps = make_client(tmp_path, handler)
    assert client.get("https://example.test/b").ok
    assert sleeps == [7.0]


def test_gives_up_after_max_retries(tmp_path):
    client, sleeps = make_client(tmp_path, lambda r: httpx.Response(500), retries=2)
    res = client.get("https://example.test/c")
    assert not res.ok and res.error == "HTTP 500" and res.attempts == 3
    assert len(sleeps) == 2


def test_non_retryable_status_fails_fast(tmp_path):
    client, sleeps = make_client(tmp_path, lambda r: httpx.Response(403))
    res = client.get("https://example.test/d")
    assert not res.ok and res.attempts == 1 and sleeps == []


def test_network_errors_are_retried(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, content=b"y")

    client, _ = make_client(tmp_path, handler)
    assert client.get("https://example.test/e").content == b"y"


def test_cache_prevents_second_request(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, content=b"cached")

    client, _ = make_client(tmp_path, handler)
    a = client.get("https://example.test/f", params={"x": 1})
    b = client.get("https://example.test/f", params={"x": 1})
    assert calls["n"] == 1 and b.from_cache and b.content == a.content and b.content_hash == a.content_hash
    client.get("https://example.test/f", params={"x": 2})
    assert calls["n"] == 2


def test_404_is_negatively_cached(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(404)

    client, _ = make_client(tmp_path, handler)
    assert client.get("https://example.test/missing").status == 404
    assert client.get("https://example.test/missing").from_cache
    assert calls["n"] == 1


def test_rate_limiter_spacing_and_window():
    t = {"now": 0.0}
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        t["now"] += s

    rl = RateLimiter(min_interval_s=0.5, max_per_window=3, window_s=10, clock=lambda: t["now"], sleep=sleep)
    for _ in range(4):
        rl.acquire()
    # spacing of 0.5 s between first three, then wait for the window to free up
    assert sleeps[:2] == [0.5, 0.5]
    assert sum(sleeps) >= 10.0
