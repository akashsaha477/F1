"""Prediction game service.

Lifecycle of a race in the game:

* **open** — the race has no timing data yet and its start is in the future. The first time it is opened the
  field and the ApexLens model's finishing order are frozen into the race's record (``data_as_of`` says what the
  model had seen), so the model can never be re-run later with the actual grid. Players submit or change a top
  ten until the deadline; the AI entrant is asked once, when the first prediction arrives. A player sees the two
  bots' picks only after submitting; other players' picks stay hidden until the race starts.
* **locked** — the race has started; nothing can be changed. ``settle`` fetches the results (optionally) and
  scores every entrant.
* **settled** — scores and the race's standings are stored; the leaderboard sums them over the season.
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable

import pandas as pd

from apexlens.config.settings import get_settings
from apexlens.game import ai as AI
from apexlens.game import refresh as REFRESH
from apexlens.game.scoring import N_PICKS, RULES, leaderboard, score_picks
from apexlens.game.store import GameStore
from apexlens.services.data_service import NotFound
from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

MODEL_KEY, AI_KEY = "apexlens", "claude"
MODEL_NAME, AI_NAME = "ApexLens model", "Claude (AI)"
RESERVED = {MODEL_KEY, AI_KEY}
AI_RETRY_AFTER_S = 180
MAX_NAME = 40


class GameError(ValueError):
    """A request the game cannot accept (closed race, bad picks, nothing to settle)."""


class Forbidden(PermissionError):
    """Settling over the API without the configured admin token."""


def player_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _iso(ts) -> str:
    return _utc(ts).isoformat(timespec="seconds").replace("+00:00", "Z")


class GameService:
    def __init__(self, paths: DataPaths, strategy: Callable, *, now: Callable[[], pd.Timestamp] | None = None,
                 ai_predictor: Callable[[dict], dict] | None = None, spawn: Callable[[Callable[[], None]], None] | None = None,
                 refresh: Callable[..., dict] | None = None, after_refresh: Callable[[], None] | None = None):
        self.paths = paths
        self.store = GameStore(paths.root)
        self._strategy = strategy
        self.now = now or (lambda: pd.Timestamp.now(tz="UTC"))
        self.ai_predictor = ai_predictor or AI.predict
        self.spawn = spawn or _in_thread
        self.refresh = refresh or REFRESH.refresh_event
        self.after_refresh = after_refresh or (lambda: None)

    # -- catalogue -----------------------------------------------------------------------------
    def rules(self) -> dict:
        return {**RULES, "entrants": [{"key": MODEL_KEY, "name": MODEL_NAME, "kind": "model"},
                                      {"key": AI_KEY, "name": AI_NAME, "kind": "ai"}],
                "settle_protected": bool(get_settings().game_admin_token)}

    def events(self, season: int | None = None) -> list[dict]:
        out = []
        for w in self._strategy().race_weeks():
            if season is not None and w["season"] != season:
                continue
            out.append(self._summary(w, self.store.load(w["event_id"])))
        return out

    def _week(self, event_id: str) -> dict:
        for w in self._strategy().race_weeks():
            if w["event_id"] == event_id:
                return w
        raise NotFound(f"unknown race {event_id}")

    @staticmethod
    def _deadline(w: dict) -> str:
        return w.get("race_start_utc") or f"{w['date']}T00:00:00Z"

    def _status(self, w: dict, g: dict | None) -> str:
        if g and g.get("result"):
            return "settled"
        before_start = self.now() < _utc(self._deadline(w))
        if g:
            return "open" if before_start else "locked"
        if w["status"] == "past":
            return "unavailable"  # results were ingested before anyone predicted
        return "open" if before_start else "unavailable"

    def _summary(self, w: dict, g: dict | None) -> dict:
        players = [e for e in (g or {}).get("entries", {}).values() if e["kind"] == "player"]
        return {**w, "deadline_utc": self._deadline(w), "game_status": self._status(w, g), "players": len(players)}

    # -- opening a race ------------------------------------------------------------------------
    def event(self, event_id: str, player: str | None = None) -> dict:
        w = self._week(event_id)
        g = self.store.load(event_id)
        if g is None:
            if self._status(w, None) != "open":
                raise GameError(self._why_unavailable(w))
            g = self._open(w)
        return self._view(w, g, player_key(player) if player else None)

    def _why_unavailable(self, w: dict) -> str:
        if w["status"] == "past":
            return f"{w['name']} already has its results ingested; the game only takes predictions before a race."
        return f"{w['name']} has started (deadline {self._deadline(w)}) and nobody predicted it."

    def _open(self, w: dict) -> dict:
        with self.store.lock:
            g = self.store.load(w["event_id"])
            if g is not None:
                return g
            fo = self._strategy().finishing_order(w["event_id"])
            if fo["event"]["mode"] != "upcoming":
                raise GameError(f"{w['name']} already has timing data; predictions must be made before the race.")
            order = sorted(fo["field"], key=lambda f: f["predicted_position"])
            field = sorted(({"driver_id": f["driver_id"], "name": f["name"], "constructor_id": f["constructor_id"]}
                            for f in fo["field"]), key=lambda f: f["name"])
            now = _iso(self.now())
            g = {
                "event_id": w["event_id"], "season": w["season"], "round": w["round"], "name": w["name"],
                "circuit_id": w["circuit_id"], "circuit_name": fo["event"]["circuit_name"], "date": w["date"],
                "laps": fo["event"]["laps"], "deadline_utc": self._deadline(w), "opened_at": now,
                "field": field, "weather": fo.get("weather"),
                "entries": {MODEL_KEY: {
                    "kind": "model", "name": MODEL_NAME, "status": "ok", "submitted_at": now,
                    "picks": [f["driver_id"] for f in order[:N_PICKS]],
                    "full_order": [{"driver_id": f["driver_id"], "predicted_position": f["predicted_position"], "grid": f["grid"],
                                    "pace_rank": f["pace_rank"]} for f in order],
                    "note": f"{fo['pace_model']}; grid {fo['grid_source']}; "
                            f"{round(100 * fo['blend_weight'])}% grid / {round(100 * (1 - fo['blend_weight']))}% pace; "
                            f"data up to {fo['data_as_of']}",
                    "data_as_of": fo["data_as_of"], "warnings": fo.get("warnings", []),
                }},
                "result": None,
            }
            self.store.save(g)
            log.info("prediction game opened for %s (model order frozen, data up to %s)", w["event_id"], fo["data_as_of"])
            return g

    # -- predictions ---------------------------------------------------------------------------
    def submit(self, event_id: str, player: str, picks: list[str]) -> dict:
        name = " ".join(player.split())
        key = player_key(name)
        if not name or len(name) > MAX_NAME or not key:
            raise GameError(f"Give a name of 1–{MAX_NAME} characters.")
        if key in RESERVED:
            raise GameError(f"{name!r} is taken by one of the bots; choose another name.")
        w = self._week(event_id)
        g = self.store.load(event_id)
        if g is None:
            if self._status(w, None) != "open":
                raise GameError(self._why_unavailable(w))
            g = self._open(w)
        if self._status(w, g) != "open":
            raise GameError(f"Predictions for {w['name']} closed at {self._deadline(w)}.")
        ids = {f["driver_id"] for f in g["field"]}
        picks = [str(p) for p in picks]
        if len(picks) != N_PICKS:
            raise GameError(f"Pick exactly {N_PICKS} drivers, P1 to P{N_PICKS}.")
        if len(set(picks)) != N_PICKS:
            raise GameError("Each driver can appear only once.")
        unknown = [p for p in picks if p not in ids]
        if unknown:
            raise GameError(f"Not in this race's field: {', '.join(unknown)}.")
        with self.store.lock:
            g = self.store.load(event_id) or g
            prev = g["entries"].get(key)
            g["entries"][key] = {"kind": "player", "name": name, "status": "ok", "picks": picks,
                                 "submitted_at": _iso(self.now()),
                                 "first_submitted_at": prev["first_submitted_at"] if prev else _iso(self.now()),
                                 "changes": (prev["changes"] + 1) if prev else 0}
            self.store.save(g)
        self._ensure_ai(event_id)
        return self._view(w, self.store.load(event_id), key)

    def _ensure_ai(self, event_id: str) -> None:
        with self.store.lock:
            g = self.store.load(event_id)
            e = g["entries"].get(AI_KEY)
            if e and e["status"] == "ok":
                return
            if e and e["status"] == "pending":
                started = _utc(e["submitted_at"])
                if (self.now() - started).total_seconds() < AI_RETRY_AFTER_S:
                    return
            if e and e["status"] == "unavailable":
                return
            g["entries"][AI_KEY] = {"kind": "ai", "name": AI_NAME, "status": "pending", "picks": None,
                                    "submitted_at": _iso(self.now())}
            self.store.save(g)
        self.spawn(lambda: self._run_ai(event_id))

    def _run_ai(self, event_id: str) -> None:
        g = self.store.load(event_id)
        try:
            out = self.ai_predictor(self._ai_context(g))
        except Exception as exc:  # noqa: BLE001
            log.exception("AI entrant crashed for %s", event_id)
            out = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"[:300]}
        with self.store.lock:
            g = self.store.load(event_id)
            e = {"kind": "ai", "name": AI_NAME, "status": out["status"], "picks": out.get("picks"),
                 "submitted_at": _iso(self.now()), "rationale": out.get("rationale"), "model": out.get("model"),
                 "reason": out.get("reason")}
            if out["status"] == "ok":
                e["note"] = f"{out.get('model') or 'Claude'}: line-up, recent results and last year's race, no model output"
            g["entries"][AI_KEY] = e
            self.store.save(g)

    def _ai_context(self, g: dict) -> dict:
        d = self._strategy().data
        res = d.results.copy()
        res["position"] = pd.to_numeric(res["position"], errors="coerce")
        ev = d.events[d.events["date"] < pd.Timestamp(g["date"])].sort_values("date")
        ev = ev[ev["event_id"].isin(set(res["event_id"]))]

        def block(e) -> dict:
            r = res[(res["event_id"] == e.event_id) & res["position"].notna()].sort_values("position").head(N_PICKS)
            return {"race": e.official_name, "date": str(e.date.date()),
                    "top_ten": [{"position": int(x.position), "driver_id": x.driver_id, "constructor_id": x.constructor_id}
                                for x in r.itertuples()]}

        prev = ev[ev["circuit_id"] == g["circuit_id"]].tail(1)
        return {"race": {"name": g["name"], "circuit_name": g.get("circuit_name") or g["circuit_id"], "date": g["date"],
                         "season": g["season"], "round": g["round"], "laps": g.get("laps")},
                "field": g["field"], "recent_results": [block(e) for e in ev.tail(3).itertuples()],
                "previous_edition": block(next(prev.itertuples())) if len(prev) else None, "weather": g.get("weather")}

    # -- views ---------------------------------------------------------------------------------
    def _view(self, w: dict, g: dict, me: str | None) -> dict:
        status = self._status(w, g)
        public = status in ("locked", "settled")          # the race has started: every pick is on the table
        committed = me is not None and me in g["entries"]  # you have submitted: you see your own and the bots' picks
        rows = []
        for key, e in g["entries"].items():
            row = {"key": key, "kind": e["kind"], "name": e["name"], "status": e.get("status", "ok"),
                   "submitted_at": e.get("submitted_at"), "reason": e.get("reason")}
            if public or key == me or (committed and e["kind"] != "player"):
                row.update({"picks": e.get("picks"), "note": e.get("note"), "rationale": e.get("rationale"),
                            "data_as_of": e.get("data_as_of")})
            if e.get("score"):
                row["score"] = e["score"]
            rows.append(row)
        rows.sort(key=lambda r: (0 if r["key"] == me else 1 if r["kind"] == "model" else 2 if r["kind"] == "ai" else 3,
                                 -(r.get("score") or {}).get("points", 0), r["name"].lower()))
        return {
            "event": {"event_id": g["event_id"], "name": g["name"], "season": g["season"], "round": g["round"],
                      "circuit_id": g["circuit_id"], "circuit_name": g.get("circuit_name"), "date": g["date"],
                      "laps": g.get("laps")},
            "status": status, "deadline_utc": g["deadline_utc"], "opened_at": g["opened_at"],
            "field": g["field"], "entries": rows, "revealed": public or committed, "you": me if committed else None,
            "model_warnings": g["entries"][MODEL_KEY].get("warnings", []),
            "result": g.get("result"), "standings": g.get("standings"),
            "ai_pending": any(e.get("status") == "pending" for e in g["entries"].values()),
        }

    # -- settling ------------------------------------------------------------------------------
    def classified_positions(self, event_id: str) -> dict[str, int | None] | None:
        """Classified positions from the silver results table, read fresh so an external refresh is seen."""
        r = read_table(self.paths.silver("race_results"), filters={"event_id": [event_id], "session_code": ["R"]})
        if r.empty:
            return None
        pos = pd.to_numeric(r["position"], errors="coerce")
        return {d: (int(p) if pd.notna(p) else None) for d, p in zip(r["driver_id"], pos, strict=True)}

    def settle(self, event_id: str, fetch: bool = False, laps: bool = True) -> dict:
        w = self._week(event_id)
        g = self.store.load(event_id)
        if g is None:
            raise GameError(f"Nobody predicted {w['name']}; there is nothing to score.")
        if self.now() < _utc(self._deadline(w)):
            raise GameError(f"{w['name']} has not started yet (deadline {self._deadline(w)}).")
        fetched = None
        if fetch:
            fetched = self.refresh(event_id, laps=laps)
            self.after_refresh()
        actual = self.classified_positions(event_id)
        if actual is None:
            raise GameError(f"No results for {w['name']} yet. Fetch them (F1DB publishes results within a day or two "
                            f"of the race), or run `python scripts/game.py settle {event_id} --fetch`.")
        names = {f["driver_id"]: f for f in g["field"]}
        with self.store.lock:
            g = self.store.load(event_id)
            for e in g["entries"].values():
                e["score"] = score_picks(e["picks"], actual) if e.get("picks") else None
            classified = sorted(((d, p) for d, p in actual.items() if p is not None), key=lambda x: x[1])
            g["result"] = {
                "settled_at": _iso(self.now()), "fetched": fetched,
                "classified": [{"position": p, "driver_id": d, "name": names.get(d, {}).get("name", d),
                                "constructor_id": names.get(d, {}).get("constructor_id")} for d, p in classified],
                "not_classified": [d for d, p in actual.items() if p is None],
                "not_in_field": [d for d in actual if d not in names],
            }
            scored = [(k, e) for k, e in g["entries"].items() if e.get("score")]
            scored.sort(key=lambda ke: (-ke[1]["score"]["points"], -ke[1]["score"]["exact"], ke[1]["name"].lower()))
            g["standings"] = [{"rank": i, "key": k, "name": e["name"], "kind": e["kind"], "points": e["score"]["points"],
                               "exact": e["score"]["exact"]} for i, (k, e) in enumerate(scored, 1)]
            self.store.save(g)
        log.info("prediction game settled for %s: %s", event_id, [(s["name"], s["points"]) for s in g["standings"]])
        return self._view(w, g, None)

    def due(self) -> list[dict]:
        """Races that have started, were predicted, and are not scored yet."""
        return [e for e in self.events() if e["game_status"] == "locked"]

    def settle_due(self, fetch: bool = False, laps: bool = True) -> list[dict]:
        """Settle every due race (for a weekly job); a race whose results are not out yet is skipped, not an error."""
        out = []
        for e in self.due():
            try:
                v = self.settle(e["event_id"], fetch=fetch, laps=laps)
                out.append({"event_id": e["event_id"], "name": e["name"], "status": "settled", "standings": v["standings"]})
            except GameError as exc:
                out.append({"event_id": e["event_id"], "name": e["name"], "status": "skipped", "reason": str(exc)})
        return out

    # -- leaderboard ---------------------------------------------------------------------------
    def leaderboard(self, season: int | None = None) -> dict:
        settled = [g for g in self.store.all() if g.get("result") and (season is None or g["season"] == season)]
        races = [{"event_id": g["event_id"], "name": g["name"], "round": g["round"], "season": g["season"], "date": g["date"],
                  "leader": g["standings"][0] if g.get("standings") else None,
                  "points": {s["key"]: s["points"] for s in g.get("standings", [])}} for g in settled]
        return {"season": season, "races": races, "rows": leaderboard(settled)}


def _in_thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="apexlens-game-ai", daemon=True).start()
