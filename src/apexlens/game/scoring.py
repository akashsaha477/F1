"""Points for a top-ten prediction against the classified finishing order, and the season leaderboard."""

from __future__ import annotations

N_PICKS = 10
EXACT, OFF_BY_ONE, OFF_BY_TWO, IN_TOP_TEN = 10, 6, 3, 1
PODIUM_BONUS, PERFECT_BONUS = 10, 25
MAX_POINTS = N_PICKS * EXACT + PODIUM_BONUS + PERFECT_BONUS

RULES = {
    "picks": N_PICKS,
    "per_pick": [
        {"outcome": "exact", "condition": "driver classified exactly where you put them", "points": EXACT},
        {"outcome": "one off", "condition": "one place above or below", "points": OFF_BY_ONE},
        {"outcome": "two off", "condition": "two places above or below", "points": OFF_BY_TWO},
        {"outcome": "in top ten", "condition": "classified in the top ten, anywhere else", "points": IN_TOP_TEN},
        {"outcome": "outside top ten", "condition": "classified 11th or lower", "points": 0},
        {"outcome": "not classified", "condition": "retired, disqualified or did not start", "points": 0},
    ],
    "bonuses": [
        {"name": "podium", "condition": "all three podium finishers named in your top three, any order", "points": PODIUM_BONUS},
        {"name": "perfect ten", "condition": "all ten in the exact order", "points": PERFECT_BONUS},
    ],
    "max_points": MAX_POINTS,
    "deadline": "Predictions close at the scheduled race start (UTC). They can be changed until then.",
    "result": "Classified finishing positions from F1DB after the race; penalties applied by the stewards count.",
    "bots": "The ApexLens model's order is frozen when the race is opened for predictions, with the data ingested "
            "at that time; the AI's order is frozen when the first prediction is submitted. Neither sees your picks.",
}


def score_picks(picks: list[str], actual: dict[str, int | None]) -> dict:
    """``actual``: driver_id -> classified position (``None`` = not classified)."""
    detail, total = [], 0
    for i, d in enumerate(picks[:N_PICKS], 1):
        a = actual.get(d)
        if a is None:
            pts, why = 0, "not classified"
        elif a == i:
            pts, why = EXACT, "exact"
        elif abs(a - i) == 1:
            pts, why = OFF_BY_ONE, "one off"
        elif abs(a - i) == 2:
            pts, why = OFF_BY_TWO, "two off"
        elif a <= N_PICKS:
            pts, why = IN_TOP_TEN, "in top ten"
        else:
            pts, why = 0, "outside top ten"
        detail.append({"position": i, "driver_id": d, "actual_position": a, "points": pts, "outcome": why})
        total += pts
    classified = sorted(((d, a) for d, a in actual.items() if a is not None), key=lambda x: x[1])
    podium_set = {d for d, a in classified if a <= 3}
    bonuses = []
    if len(podium_set) == 3 and set(picks[:3]) == podium_set:
        bonuses.append({"name": "podium", "points": PODIUM_BONUS})
        total += PODIUM_BONUS
    top = [d for d, _ in classified[:N_PICKS]]
    if len(top) == N_PICKS and top == list(picks[:N_PICKS]):
        bonuses.append({"name": "perfect ten", "points": PERFECT_BONUS})
        total += PERFECT_BONUS
    return {
        "points": total, "picks": detail, "bonuses": bonuses,
        "exact": sum(1 for p in detail if p["outcome"] == "exact"),
        "in_top_ten": sum(1 for p in detail if p["actual_position"] is not None and p["actual_position"] <= N_PICKS),
        "podium": any(b["name"] == "podium" for b in bonuses),
        "winner": bool(detail) and detail[0]["outcome"] == "exact",
    }


def leaderboard(events: list[dict]) -> list[dict]:
    """Season totals from settled event records (each with ``entries`` holding a ``score``). Ties on points are
    broken by exact hits, then name. ``race_wins`` counts races where the entrant had the most points (shared ties)."""
    rows: dict[str, dict] = {}
    for ev in events:
        scored = {k: e for k, e in ev.get("entries", {}).items() if e.get("score")}
        if not scored:
            continue
        best = max(e["score"]["points"] for e in scored.values())
        for key, e in scored.items():
            s = e["score"]
            r = rows.setdefault(key, {"key": key, "name": e["name"], "kind": e["kind"], "points": 0, "races": 0, "exact": 0,
                                      "podiums": 0, "winners": 0, "race_wins": 0, "best_race": 0, "average": 0.0})
            r["points"] += s["points"]
            r["races"] += 1
            r["exact"] += s["exact"]
            r["podiums"] += int(bool(s.get("podium")))
            r["winners"] += int(bool(s.get("winner")))
            r["race_wins"] += int(s["points"] == best)
            r["best_race"] = max(r["best_race"], s["points"])
    out = sorted(rows.values(), key=lambda r: (-r["points"], -r["exact"], r["name"].lower()))
    for i, r in enumerate(out, 1):
        r["rank"] = i
        r["average"] = round(r["points"] / r["races"], 1) if r["races"] else 0.0
    return out
