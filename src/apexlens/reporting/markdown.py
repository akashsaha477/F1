"""Small helpers for writing Markdown tables from computed results."""

from __future__ import annotations

import math
from collections.abc import Sequence


def fmt(v, nd: int = 3, signed: bool = False, pct: bool = False) -> str:
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, float):
        if math.isnan(v):
            return "–"
        if pct:
            return f"{100 * v:.{max(nd - 2, 0)}f}%"
        return f"{v:+.{nd}f}" if signed else f"{v:.{nd}f}"
    return str(v)


def ci(d: dict | None, nd: int = 3, signed: bool = True) -> str:
    """``estimate [lo, hi]`` with a marker when the interval excludes zero."""
    if not d:
        return "–"
    s = f"{fmt(d['estimate'], nd, signed)} [{fmt(d['lo'], nd, signed)}, {fmt(d['hi'], nd, signed)}]"
    if d.get("significant"):
        s += " *"
    return s


def table(rows: Sequence[dict], cols: Sequence[tuple[str, str]] | Sequence[str], nd: int = 3,
          formats: dict | None = None) -> str:
    """Markdown table. ``cols`` are keys or (key, header) pairs; ``formats`` maps key -> callable."""
    cols = [(c, c) if isinstance(c, str) else c for c in cols]
    formats = formats or {}
    out = ["| " + " | ".join(h.replace("|", "\\|") for _, h in cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in rows:
        cells = []
        for k, _ in cols:
            v = r.get(k)
            if k in formats:
                cells.append(formats[k](v))
            elif k in ("season", "k", "cluster") and v is not None:
                cells.append(str(v))
            else:
                cells.append(fmt(v, nd))
        out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    return "\n".join(out)


def figure(path: str, alt: str, caption: str | None = None) -> str:
    s = f"![{alt}]({path})"
    return s + (f"\n\n*{caption}*" if caption else "")
