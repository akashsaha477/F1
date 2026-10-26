"""Static report figures (matplotlib, light theme).

Colours follow the dashboard: categorical slots in fixed order, faster = blue, slower = red,
compounds SOFT/MEDIUM/HARD = orange/blue/aqua. Thin marks, recessive grid, one y-axis per chart.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e2e1dc"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
FASTER, SLOWER = "#2a78d6", "#e34948"
COMPOUND = {"SOFT": "#eb6834", "MEDIUM": "#2a78d6", "HARD": "#1baf7a", "INTERMEDIATE": "#eda100", "WET": "#6250d6"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "text.color": TEXT, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5, "axes.titlesize": 11,
    "axes.titleweight": "semibold", "axes.titlelocation": "left", "legend.frameon": False, "lines.linewidth": 2,
    "axes.axisbelow": True,
})


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def hbar(labels, values, path: Path, title: str, xlabel: str, color: str = SERIES[0], value_fmt: str = "{:.1%}") -> None:
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(labels) + 1.2))
    y = np.arange(len(labels))
    ax.barh(y, values, color=color, height=0.6)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    for yi, v in zip(y, values, strict=True):
        ax.text(v, yi, " " + value_fmt.format(v), va="center", fontsize=8.5, color=TEXT_2)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.set_xlim(0, max(values) * 1.18 if len(values) else 1)
    if "%" in value_fmt:
        ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    _save(fig, path)


def histogram(values, path: Path, title: str, xlabel: str, bins: int = 80, clip: tuple[float, float] | None = None) -> None:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if clip:
        v = np.clip(v, *clip)
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ax.hist(v, bins=bins, color=SERIES[0], edgecolor=SURFACE, linewidth=0.4)
    ax.axvline(0, color=TEXT_2, linewidth=1, linestyle="--")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("laps")
    ax.set_title(title)
    _save(fig, path)


def interval_dots(labels, est, lo, hi, path: Path, title: str, xlabel: str, colors=None, ref: float | None = 0.0) -> None:
    """Point estimates with intervals, one row per label (top to bottom in the given order)."""
    n = len(labels)
    fig, ax = plt.subplots(figsize=(7, 0.28 * n + 1.3))
    y = np.arange(n)
    colors = colors or [SERIES[0]] * n
    for yi, e, a, b, c in zip(y, est, lo, hi, colors, strict=True):
        ax.plot([a, b], [yi, yi], color=c, linewidth=2, solid_capstyle="round")
        ax.plot([e], [yi], "o", color=c, markersize=5, markeredgecolor=SURFACE, markeredgewidth=1)
    if ref is not None:
        ax.axvline(ref, color=TEXT_2, linewidth=1, linestyle="--")
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    _save(fig, path)


def grouped_dots(groups, series: dict[str, tuple[list, list, list]], path: Path, title: str, ylabel: str) -> None:
    """Several series (estimate, lo, hi per group) side by side on a categorical x axis."""
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    x = np.arange(len(groups))
    k = len(series)
    for i, (name, (e, lo, hi)) in enumerate(series.items()):
        off = (i - (k - 1) / 2) * 0.12
        c = SERIES[i]
        ax.vlines(x + off, lo, hi, color=c, linewidth=2)
        ax.plot(x + off, e, "o", color=c, markersize=5, label=name, markeredgecolor=SURFACE, markeredgewidth=1)
    ax.set_xticks(x, groups)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    _save(fig, path)


def lines(xs: dict[str, list], ys: dict[str, list], path: Path, title: str, xlabel: str, ylabel: str,
          colors: dict[str, str] | None = None, ncols: int = 1) -> None:
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, name in enumerate(xs):
        ax.plot(xs[name], ys[name], color=(colors or {}).get(name, SERIES[i % len(SERIES)]), label=name)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if len(xs) > 1:
        ax.legend(ncols=ncols)
    _save(fig, path)


def small_multiples(panels: list[tuple[str, list, list]], path: Path, title: str, ylabel: str, ncols: int = 3) -> None:
    """One line per panel (x, y) with a shared y-scale."""
    nrows = int(np.ceil(len(panels) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3 * ncols, 2.4 * nrows), sharey=True, squeeze=False)
    for ax, (name, x, y) in zip(axes.flat, panels, strict=False):
        ax.plot(x, y, color=SERIES[0])
        ax.axhline(0, color=TEXT_2, linewidth=0.8, linestyle="--")
        ax.set_title(name, fontsize=9.5)
    for ax in list(axes.flat)[len(panels):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="semibold")
    _save(fig, path)
