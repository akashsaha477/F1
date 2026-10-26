"""Normalisation helpers for F1DB result records."""

from __future__ import annotations

import re

from apexlens.cleaning.parsing import is_null

# Explicit keyword lists; anything unmatched is "other". The classification describes the reported
# reason only — a "collision" retirement says nothing about who caused the collision.
RETIREMENT_CATEGORIES = {
    "collision_or_accident": ["collision", "accident", "spun off", "crash", "spin"],
    "disqualified_or_technical_infringement": ["illegal", "underweight", "outside assistance", "disqualified",
                                               "excluded", "fuel flow", "plank"],
    "withdrawn_or_health": ["withdrew", "unwell", "injury", "illness"],
    "tyre_or_puncture": ["puncture", "tyre", "wheel"],
    "mechanical_or_reliability": [
        "engine", "hydraulic", "gearbox", "brake", "power unit", "overheating", "fuel", "water", "suspension",
        "oil", "turbo", "vibration", "transmission", "throttle", "steering", "power loss", "mechanical",
        "electrical", "electronics", "battery", "ers", "mgu", "clutch", "driveshaft", "exhaust", "radiator",
        "cooling", "pressure", "differential", "halfshaft", "alternator", "spark plug", "ignition", "pneumatic",
        "handling", "pit stop issue",
    ],
    # Body damage of unreported origin (could follow contact, debris or failure).
    "damage_unspecified": ["undertray", "floor", "wing", "damage", "debris", "bodywork"],
}


def classify_retirement(reason, position_text: str | None) -> str:
    pt = (position_text or "").upper()
    if pt == "DSQ":
        return "disqualified_or_technical_infringement"
    if pt in {"DNS", "DNQ", "DNPQ"}:
        return "did_not_start"
    if is_null(reason):
        return "finished" if pt not in {"DNF", "NC", "EX"} else "unspecified"
    r = str(reason).lower()
    for cat in ["collision_or_accident", "disqualified_or_technical_infringement", "withdrawn_or_health",
                "tyre_or_puncture", "mechanical_or_reliability", "damage_unspecified"]:
        if any(re.search(rf"\b{re.escape(k)}", r) for k in RETIREMENT_CATEGORIES[cat]):
            return cat
    return "other"


def position_value(v) -> tuple[int | None, str | None]:
    if is_null(v):
        return None, None
    s = str(v).strip()
    if s.isdigit():
        return int(s), s
    return None, s.upper()
