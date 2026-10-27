"""Race-specific sporting rules that change the strategy space.

The general rule (a dry race must use at least two different dry compounds) is built into the optimiser.
Exceptions announced by the FIA for single events are listed here; each is consistent with the stint data
(e.g. no stint longer than the cap). Add new ones when they are announced.
"""

from __future__ import annotations

SPECIAL_RULES: dict[str, dict] = {
    "2023-17": {"max_stint_laps": 18, "note": "Qatar 2023: each tyre set limited to 18 laps (tyre safety)"},
    "2025-08": {"min_stops": 2, "note": "Monaco 2025: at least two pit stops and three different tyre sets"},
    "2025-23": {"max_stint_laps": 25, "note": "Qatar 2025: each tyre set limited to 25 laps (tyre safety)"},
}


def rules_for(event_id: str | None) -> dict:
    return SPECIAL_RULES.get(event_id or "", {})
