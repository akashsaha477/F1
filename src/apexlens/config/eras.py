"""Regulation eras used to group seasons whose cars are broadly comparable.

The boundaries follow major technical-regulation changes. They are an analytical convenience for
choosing reference populations, not an official classification. Comparisons of raw lap times are
only ever made within a session; eras restrict which seasons are pooled for percentiles.
"""

from __future__ import annotations

ERAS: list[tuple[int, int, str, str]] = [
    (1950, 1960, "early_front_engine", "Early championship (front-engined cars dominate)"),
    (1961, 1965, "1.5l", "1.5-litre formula"),
    (1966, 1987, "3l_ground_effect_turbo", "3-litre formula, ground-effect and first turbo era"),
    (1988, 2005, "na_v10_v12", "Naturally aspirated 3.5/3.0-litre era"),
    (2006, 2013, "v8", "2.4-litre V8 era"),
    (2014, 2016, "hybrid_narrow", "1.6-litre turbo-hybrid, narrow cars"),
    (2017, 2021, "hybrid_wide", "Turbo-hybrid, wider high-downforce cars"),
    (2022, 2025, "ground_effect", "Ground-effect aerodynamics, 18-inch tyres"),
    (2026, 2100, "2026_regulations", "2026 chassis and power-unit regulations"),
]


def era_for(season: int) -> str:
    for start, end, key, _ in ERAS:
        if start <= season <= end:
            return key
    return "unknown"


def era_label(key: str) -> str:
    for _, _, k, label in ERAS:
        if k == key:
            return label
    return key
