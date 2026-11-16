"""Prediction game: scoring, leaderboard, the AI entrant's prompt/parsing, and the service lifecycle
(open → predict → lock → settle) with a fake strategy service and a controllable clock."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from apexlens.game import ai as AI
from apexlens.game.scoring import MAX_POINTS, leaderboard, score_picks
from apexlens.game.service import AI_KEY, MODEL_KEY, GameError, GameService, player_key
from apexlens.services.data_service import NotFound
from apexlens.storage.io import write_table
from apexlens.storage.paths import DataPaths

DRIVERS = [f"d{i:02d}" for i in range(1, 13)]
ACTUAL = {"d01": 1, "d02": 2, "d03": 3, "d04": 4, "d05": 5, "d06": 6, "d07": 7, "d08": 8, "d09": 9, "d10": 10,
          "d11": 11, "d12": None}


# -- scoring ---------------------------------------------------------------------------------------
def test_points_per_pick_and_bonuses():
    perfect = score_picks(DRIVERS[:10], ACTUAL)
    assert perfect["points"] == MAX_POINTS == 135 and perfect["exact"] == 10 and perfect["podium"] and perfect["winner"]
    assert {b["name"] for b in perfect["bonuses"]} == {"podium", "perfect ten"}

    # P1/P2 swapped: 8 exact (80) + two one-off (12) + podium set still right (10)
    swapped = score_picks(["d02", "d01", *DRIVERS[2:10]], ACTUAL)
    assert swapped["points"] == 80 + 12 + 10 and not swapped["winner"] and swapped["podium"]
    assert [p["outcome"] for p in swapped["picks"][:2]] == ["one off", "one off"]

    s = score_picks(["d03", "d05", "d12", "d11", "d10", "d06", "d07", "d08", "d09", "d01"], ACTUAL)
    by = {p["position"]: p for p in s["picks"]}
    assert by[1]["outcome"] == "two off" and by[1]["points"] == 3
    assert by[2]["outcome"] == "in top ten" and by[2]["points"] == 1
    assert by[3]["outcome"] == "not classified" and by[3]["points"] == 0 and by[3]["actual_position"] is None
    assert by[4]["outcome"] == "outside top ten" and by[4]["points"] == 0
    assert by[5]["outcome"] == "in top ten" and by[6]["outcome"] == "exact"
    assert s["points"] == 3 + 1 + 0 + 0 + 1 + 10 + 10 + 10 + 10 + 1 and not s["bonuses"]


def test_leaderboard_sums_and_breaks_ties():
    def entry(name, kind, points, exact, podium=False):
        return {"name": name, "kind": kind, "score": {"points": points, "exact": exact, "podium": podium, "winner": False}}

    e1 = {"entries": {"ann": entry("Ann", "player", 40, 3), MODEL_KEY: entry("ApexLens model", "model", 40, 4),
                      AI_KEY: entry("Claude (AI)", "ai", 20, 1, True)}}
    e2 = {"entries": {"ann": entry("Ann", "player", 10, 0), "bob": entry("Bob", "player", 50, 5),
                      MODEL_KEY: entry("ApexLens model", "model", 30, 2), "nobody": {"name": "x", "kind": "player", "score": None}}}
    rows = leaderboard([e1, e2])
    # 70 > 50 = 50 > 20; the tie is broken by exact hits (Bob 5, Ann 3)
    assert [r["key"] for r in rows] == [MODEL_KEY, "bob", "ann", AI_KEY]
    model = rows[0]
    assert model == {"key": MODEL_KEY, "name": "ApexLens model", "kind": "model", "points": 70, "races": 2, "exact": 6,
                     "podiums": 0, "winners": 0, "race_wins": 1, "best_race": 40, "average": 35.0, "rank": 1}
    # Bob won race 2 outright; Ann shared race 1 with the model (40 each)
    assert rows[1]["race_wins"] == 1 and rows[2]["race_wins"] == 1 and rows[3]["podiums"] == 1
    assert leaderboard([]) == []


# -- the AI entrant --------------------------------------------------------------------------------
def context(field=DRIVERS[:10]):
    return {"race": {"name": "Test Grand Prix", "circuit_name": "Test Ring", "date": "2026-11-29", "season": 2026, "round": 21,
                     "laps": 57},
            "field": [{"driver_id": d, "name": d.upper(), "constructor_id": "team"} for d in field],
            "recent_results": [{"race": "Previous GP", "date": "2026-11-15",
                                "top_ten": [{"position": 1, "driver_id": "d02", "constructor_id": "team"}]}],
            "previous_edition": None, "weather": {"track_temp_c": 31.5, "rain_risk": 0.2, "wet_race_likely": False}}


def test_ai_prompt_and_response_validation(tmp_settings):
    prompt = AI.build_prompt(context())
    assert "Test Grand Prix" in prompt and "- d01 — D01 — team" in prompt and "P1 d02 (team)" in prompt
    assert "Last race at this circuit: none on record" in prompt and "rain risk 20%" in prompt
    assert AI.schema(["a", "b"])["properties"]["picks"]["items"]["enum"] == ["a", "b"]

    good = json.dumps({"picks": DRIVERS[:10], "rationale": "form"})
    assert AI.parse_response(good, DRIVERS[:10]) == (DRIVERS[:10], "form")
    with pytest.raises(ValueError, match="expected 10"):
        AI.parse_response(json.dumps({"picks": DRIVERS[:9]}), DRIVERS)
    with pytest.raises(ValueError, match="not in the field"):
        AI.parse_response(json.dumps({"picks": [*DRIVERS[:9], "zz"]}), DRIVERS)
    with pytest.raises(ValueError, match="repeated"):
        AI.parse_response(json.dumps({"picks": [*DRIVERS[:9], "d01"]}), DRIVERS)

    out = AI.predict(context(), settings=tmp_settings, caller=lambda prompt, ids, s: (good, "claude-test"))
    assert out == {"status": "ok", "picks": DRIVERS[:10], "rationale": "form", "model": "claude-test"}

    def boom(prompt, ids, s):
        raise RuntimeError("rate limited")

    assert AI.predict(context(), settings=tmp_settings, caller=boom)["status"] == "error"
    bad = AI.predict(context(), settings=tmp_settings, caller=lambda *a: (json.dumps({"picks": ["zz"] * 10}), "m"))
    assert bad["status"] == "error" and "expected 10" not in bad["reason"] and "not in the field" in bad["reason"]
    tmp_settings.game_ai_enabled = False
    assert AI.predict(context(), settings=tmp_settings)["status"] == "unavailable"


# -- the service -----------------------------------------------------------------------------------
class FakeStrategy:
    """Two races: 2026-20 already has timing data, 2026-21 is upcoming with a known start time."""

    def __init__(self):
        self.calls = 0
        self.data = type("D", (), {})()
        self.data.events = pd.DataFrame([
            {"event_id": "2026-20", "official_name": "Formula 1 Past Grand Prix 2026", "circuit_id": "ring", "date": pd.Timestamp("2026-11-15")},
            {"event_id": "2026-21", "official_name": "Formula 1 Next Grand Prix 2026", "circuit_id": "ring", "date": pd.Timestamp("2026-11-29")},
        ])
        self.data.results = pd.DataFrame([{"event_id": "2026-20", "driver_id": d, "constructor_id": "team", "position": i + 1,
                                           "session_code": "R"} for i, d in enumerate(DRIVERS)])

    def race_weeks(self):
        return [{"event_id": "2026-20", "season": 2026, "round": 20, "name": "Formula 1 Past Grand Prix 2026", "circuit_id": "ring",
                 "date": "2026-11-15", "status": "past", "race_start_utc": "2026-11-15T14:00:00Z"},
                {"event_id": "2026-21", "season": 2026, "round": 21, "name": "Formula 1 Next Grand Prix 2026", "circuit_id": "ring",
                 "date": "2026-11-29", "status": "upcoming", "race_start_utc": "2026-11-29T14:00:00Z"}]

    def finishing_order(self, event_id):
        self.calls += 1
        order = list(reversed(DRIVERS))  # the model's order differs from the driver ids' order
        return {"event": {"event_id": event_id, "mode": "upcoming", "circuit_name": "Test Ring", "laps": 57},
                "field": [{"driver_id": d, "name": f"Driver {d[1:]}", "constructor_id": "team", "grid": i + 1, "base_pct": 0.1 * i,
                           "pace_rank": i + 1, "predicted_position": i + 1, "actual_position": None} for i, d in enumerate(order)],
                "pace_model": "production lap-pace model", "grid_source": "predicted from qualifying form", "blend_weight": 0.4,
                "blend_weight_races": 60, "weather": {"track_temp_c": 30.0, "rain_risk": 0.1, "wet_race_likely": False},
                "warnings": ["Upcoming race"], "data_as_of": "2026-11-15"}


@pytest.fixture
def game(tmp_settings):
    paths = DataPaths(tmp_settings.data_dir).ensure()
    strat = FakeStrategy()
    clock = {"now": pd.Timestamp("2026-11-20T10:00:00Z")}
    ai_calls = []

    def fake_ai(ctx):
        ai_calls.append(ctx)
        return {"status": "ok", "picks": DRIVERS[:10], "rationale": "I like low numbers", "model": "claude-test"}

    svc = GameService(paths, strategy=lambda: strat, now=lambda: clock["now"], ai_predictor=fake_ai,
                      spawn=lambda fn: fn(), refresh=lambda event_id, laps=True: {"f1db_updated": True})
    svc.clock, svc.strat, svc.ai_calls, svc.paths_ = clock, strat, ai_calls, paths
    return svc


def test_player_keys():
    assert player_key("  Akash  Saha ") == "akash-saha" == player_key("AKASH-saha!")
    assert player_key("!!!") == ""


def test_open_freezes_the_model_and_hides_it_until_you_predict(game):
    ev = game.events()
    assert [(e["event_id"], e["game_status"]) for e in ev] == [("2026-20", "unavailable"), ("2026-21", "open")]
    assert ev[1]["deadline_utc"] == "2026-11-29T14:00:00Z" and ev[1]["players"] == 0

    v = game.event("2026-21")
    assert v["status"] == "open" and not v["revealed"] and v["you"] is None
    assert [f["driver_id"] for f in v["field"]] == DRIVERS  # alphabetical by name, not the model's order
    model = next(e for e in v["entries"] if e["kind"] == "model")
    assert "picks" not in model and model["status"] == "ok"
    assert game.strat.calls == 1
    game.event("2026-21")  # opening again does not recompute
    assert game.strat.calls == 1
    stored = game.store.load("2026-21")
    assert stored["entries"][MODEL_KEY]["picks"] == list(reversed(DRIVERS))[:10]
    assert stored["entries"][MODEL_KEY]["data_as_of"] == "2026-11-15"

    with pytest.raises(GameError, match="already has its results"):
        game.event("2026-20")
    with pytest.raises(NotFound):
        game.event("2026-99")


def test_predict_reveals_the_bots_and_validates_picks(game):
    with pytest.raises(GameError, match="exactly 10"):
        game.submit("2026-21", "Ann", DRIVERS[:9])
    with pytest.raises(GameError, match="only once"):
        game.submit("2026-21", "Ann", [*DRIVERS[:9], "d01"])
    with pytest.raises(GameError, match="Not in this race"):
        game.submit("2026-21", "Ann", [*DRIVERS[:9], "zz"])
    with pytest.raises(GameError, match="bots"):
        game.submit("2026-21", "ApexLens", DRIVERS[:10])
    with pytest.raises(GameError, match="name"):
        game.submit("2026-21", "   ", DRIVERS[:10])
    assert game.ai_calls == []

    v = game.submit("2026-21", "Ann", DRIVERS[:10])
    assert v["revealed"] and v["you"] == "ann" and v["status"] == "open"
    by = {e["key"]: e for e in v["entries"]}
    assert [e["key"] for e in v["entries"]][:3] == ["ann", MODEL_KEY, AI_KEY]
    assert by["ann"]["picks"] == DRIVERS[:10] and by[MODEL_KEY]["picks"] == list(reversed(DRIVERS))[:10]
    assert by[AI_KEY]["status"] == "ok" and by[AI_KEY]["picks"] == DRIVERS[:10] and by[AI_KEY]["rationale"]
    assert "data up to 2026-11-15" in by[MODEL_KEY]["note"]
    # the AI was asked once, with the public context and without the model's order
    assert len(game.ai_calls) == 1
    ctx = game.ai_calls[0]
    assert ctx["race"]["name"].startswith("Formula 1 Next") and len(ctx["field"]) == 12
    assert ctx["recent_results"][0]["top_ten"][0] == {"position": 1, "driver_id": "d01", "constructor_id": "team"}
    assert ctx["previous_edition"]["race"] == "Formula 1 Past Grand Prix 2026" and "model" not in json.dumps(ctx)

    # a second player cannot see Ann's picks before the start, but does see the bots once they have predicted
    v2 = game.submit("2026-21", "Bob", list(reversed(DRIVERS))[:10])
    by2 = {e["key"]: e for e in v2["entries"]}
    assert "picks" not in by2["ann"] and by2["bob"]["picks"] and by2[MODEL_KEY]["picks"]
    assert len(game.ai_calls) == 1
    assert game.events()[1]["players"] == 2
    # a bystander sees names only
    v3 = game.event("2026-21")
    assert not v3["revealed"] and all("picks" not in e for e in v3["entries"])
    # changing your own entry is allowed and counted
    game.submit("2026-21", "ann", DRIVERS[1:11])
    e = game.store.load("2026-21")["entries"]["ann"]
    assert e["picks"] == DRIVERS[1:11] and e["changes"] == 1 and e["name"] == "ann"


def test_ai_failures_never_block_the_game(game):
    game.ai_predictor = lambda ctx: {"status": "error", "reason": "boom"}
    v = game.submit("2026-21", "Ann", DRIVERS[:10])
    ai = next(e for e in v["entries"] if e["kind"] == "ai")
    assert ai["status"] == "error" and ai["reason"] == "boom" and ai["picks"] is None
    # the next submission retries a failed AI; a successful one is kept
    game.ai_predictor = lambda ctx: {"status": "ok", "picks": DRIVERS[2:12], "rationale": "", "model": "m"}
    v = game.submit("2026-21", "Bob", DRIVERS[:10])
    assert next(e for e in v["entries"] if e["kind"] == "ai")["picks"] == DRIVERS[2:12]
    game.ai_predictor = lambda ctx: {"status": "error", "reason": "should not run"}
    v = game.submit("2026-21", "Cy", DRIVERS[:10])
    assert next(e for e in v["entries"] if e["kind"] == "ai")["picks"] == DRIVERS[2:12]


def test_lock_and_settle(game):
    game.submit("2026-21", "Ann", DRIVERS[:10])                # perfect
    game.submit("2026-21", "Bob", list(reversed(DRIVERS))[:10])  # same as the model
    with pytest.raises(GameError, match="not started"):
        game.settle("2026-21")

    game.clock["now"] = pd.Timestamp("2026-11-29T14:00:01Z")
    assert game.events()[1]["game_status"] == "locked"
    with pytest.raises(GameError, match="closed"):
        game.submit("2026-21", "Late", DRIVERS[:10])
    v = game.event("2026-21")
    assert v["revealed"] and all(e["picks"] for e in v["entries"])  # everyone's picks are public once locked
    with pytest.raises(GameError, match="No results"):
        game.settle("2026-21")
    assert [e["event_id"] for e in game.due()] == ["2026-21"]
    assert game.settle_due() == [{"event_id": "2026-21", "name": "Formula 1 Next Grand Prix 2026", "status": "skipped",
                                  "reason": game.settle_due()[0]["reason"]}]
    assert "No results" in game.settle_due()[0]["reason"]

    results = pd.DataFrame([{"event_id": "2026-21", "season": 2026, "session_code": "R", "driver_id": d, "position": p}
                            for d, p in ACTUAL.items()] + [{"event_id": "2026-21", "season": 2026, "session_code": "S",
                                                            "driver_id": "d01", "position": 1}])
    write_table(game.paths_.silver("race_results"), results)
    due = game.settle_due(fetch=True)
    assert [(r["event_id"], r["status"]) for r in due] == [("2026-21", "settled")] and game.due() == [] and game.settle_due() == []
    v = game.event("2026-21")
    assert v["status"] == "settled" and v["result"]["fetched"] == {"f1db_updated": True}
    assert [r["driver_id"] for r in v["result"]["classified"]][:3] == ["d01", "d02", "d03"] and v["result"]["not_classified"] == ["d12"]
    # the reversed order d12…d03: d12 not classified, d11 outside the top ten, d07/d06 one place off (6 each), six others
    # in the top ten (1 each) = 18; ties are broken by exact hits, then name
    assert [(s["name"], s["points"]) for s in v["standings"]] == [("Ann", 135), ("Claude (AI)", 135), ("ApexLens model", 18), ("Bob", 18)]
    assert game.events()[1]["game_status"] == "settled"
    with pytest.raises(GameError, match="closed"):
        game.submit("2026-21", "Late", DRIVERS[:10])

    lb = game.leaderboard(2026)
    assert [r["name"] for r in lb["rows"]] == ["Ann", "Claude (AI)", "ApexLens model", "Bob"]
    assert lb["rows"][0]["race_wins"] == 1 == lb["rows"][1]["race_wins"] and lb["races"][0]["leader"]["name"] == "Ann"
    assert game.leaderboard(2025)["rows"] == []
