"""Atomic Parquet / JSON persistence.

Tables are directories of Parquet files. Each file is one *partition* (for example one session),
so re-running an ingestion step replaces that partition instead of appending duplicates.
Writes go to a temporary file first and are moved into place with ``os.replace`` so a failure
half-way through never leaves a corrupt table behind.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def write_bytes(path: Path, data: bytes) -> None:
    _atomic_write_bytes(Path(path), data)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj: Any) -> None:
    _atomic_write_bytes(Path(path), json.dumps(obj, indent=2, default=str, ensure_ascii=False).encode())


def read_json(path: Path, default: Any = None) -> Any:
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def safe_partition_name(key: str) -> str:
    keep = [c if c.isalnum() or c in "-_=." else "_" for c in key]
    return "".join(keep)


def coerce_mixed_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Object columns holding mixed Python types are stored as strings (Parquet needs one type)."""
    out = df
    for c in df.columns:
        if df[c].dtype != object:
            continue
        types = {type(v) for v in df[c].dropna().tolist()}
        if len(types) > 1:
            if out is df:
                out = df.copy()
            out[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and v != v) else str(v))
    return out


def write_partition(table_dir: Path, key: str, df: pd.DataFrame) -> Path:
    """Replace one partition of a table atomically."""
    df = coerce_mixed_columns(df)
    table_dir = Path(table_dir)
    table_dir.mkdir(parents=True, exist_ok=True)
    path = table_dir / f"{safe_partition_name(key)}.parquet"
    fd, tmp = tempfile.mkstemp(dir=table_dir, prefix=f".{path.name}.", suffix=".tmp")
    os.close(fd)
    try:
        table = pa.Table.from_pandas(df.reset_index(drop=True), preserve_index=False)
        pq.write_table(table, tmp, compression="zstd")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def write_table(table_dir: Path, df: pd.DataFrame) -> Path:
    """Write a single-partition table (replaces any existing content)."""
    table_dir = Path(table_dir)
    if table_dir.exists():
        for old in table_dir.glob("*.parquet"):
            if old.name != "all.parquet":
                old.unlink()
    return write_partition(table_dir, "all", df)


def partition_files(table_dir: Path) -> list[Path]:
    table_dir = Path(table_dir)
    if not table_dir.exists():
        return []
    return sorted(p for p in table_dir.glob("*.parquet") if not p.name.startswith("."))


def read_table(table_dir: Path, columns: Iterable[str] | None = None, filters: dict | None = None) -> pd.DataFrame:
    """Read every partition of a table into one DataFrame (empty frame if missing)."""
    files = partition_files(table_dir)
    if not files:
        return pd.DataFrame(columns=list(columns) if columns else None)
    frames = []
    cols = list(columns) if columns else None
    for f in files:
        df = pq.read_table(f, columns=cols).to_pandas()
        if filters:
            for k, v in filters.items():
                if k in df.columns:
                    df = df[df[k].isin(v if isinstance(v, (list, tuple, set)) else [v])]
        if len(df):
            frames.append(df)
    if not frames:
        return pq.read_table(files[0], columns=cols).to_pandas().iloc[0:0]
    return pd.concat(frames, ignore_index=True)


def read_partition(table_dir: Path, key: str, columns: Iterable[str] | None = None) -> pd.DataFrame:
    path = Path(table_dir) / f"{safe_partition_name(key)}.parquet"
    if not path.exists():
        return pd.DataFrame(columns=list(columns) if columns else None)
    return pq.read_table(path, columns=list(columns) if columns else None).to_pandas()


def table_exists(table_dir: Path) -> bool:
    return bool(partition_files(table_dir))
