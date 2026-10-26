"""Low-level value parsing and unit normalisation."""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

import numpy as np
import pandas as pd

NULL_STRINGS = {"", "none", "nan", "nat", "null", "<na>"}

STANDARD_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}
WET_COMPOUNDS = {"INTERMEDIATE", "WET"}
# 2018 nomenclature (absolute names) — not comparable with the relative SOFT/MEDIUM/HARD used since 2019.
LEGACY_SLICKS = {"HYPERSOFT", "ULTRASOFT", "SUPERSOFT", "SUPERHARD"}


def is_null(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    return isinstance(v, str) and v.strip().lower() in NULL_STRINGS


def to_float(v: Any) -> float:
    if is_null(v):
        return np.nan
    if isinstance(v, bool):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def to_bool(v: Any) -> float | bool:
    """Parse booleans that may arrive as bools, 0/1 or strings. Unknown -> NaN (kept nullable)."""
    if is_null(v):
        return np.nan
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"true", "1", "yes"}:
        return True
    if s in {"false", "0", "no"}:
        return False
    return np.nan


_DURATION_RE = re.compile(r"^(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)$")


def parse_duration_s(v: Any) -> float:
    """Parse ``"1:30.031"``, ``"1:31:44.742"``, ``"36.604"`` or numbers to seconds.

    Gap strings (``"+22.457"``) are parsed as positive durations; ``"+1 Lap"`` style values are NaN.
    """
    if is_null(v):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().lstrip("+")
    m = _DURATION_RE.match(s)
    if not m:
        return np.nan
    a, b, sec = m.groups()
    if a is not None and b is not None:  # h:m:s
        return int(a) * 3600 + int(b) * 60 + float(sec)
    if a is not None:  # m:s
        return int(a) * 60 + float(sec)
    return float(sec)


def normalize_compound(v: Any) -> str:
    if is_null(v):
        return "UNKNOWN"
    s = str(v).strip().upper()
    if s in STANDARD_COMPOUNDS:
        return s
    if s in {"INTER", "INTERMEDIATES"}:
        return "INTERMEDIATE"
    if s in {"FULL WET", "WETS"}:
        return "WET"
    if s in LEGACY_SLICKS:
        return "LEGACY_SLICK"
    return "UNKNOWN"


def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def series_to_float(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.map(to_float), errors="coerce").astype(float)


def series_to_nullable_bool(s: pd.Series) -> pd.Series:
    return s.map(to_bool).astype("boolean")
