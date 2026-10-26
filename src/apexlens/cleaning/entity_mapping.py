"""Canonical identity resolution across sources.

Canonical IDs are F1DB identifiers. Lap-level sources identify drivers by car number and
three-letter abbreviation and teams by display name, both of which change between seasons, so they
are resolved *per session* against F1DB's per-event entries:

1. (event, session, car number) in the F1DB results of that very session;
2. (event, any session, car number);
3. (season, car number) where the abbreviation also matches;
4. abbreviation among drivers who raced that season.

Every resolution records its method so ambiguous mappings stay auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from apexlens.cleaning.parsing import normalize_text

# Lap-source event names that do not equal F1DB grand-prix full names.
EVENT_NAME_OVERRIDES = {
    "mexico city grand prix": "mexico",
    "sao paulo grand prix": "sao-paulo",
    "brazilian grand prix": "brazil",
    "70th anniversary grand prix": "70th-anniversary",
    "styrian grand prix": "styria",
    "tuscan grand prix": "tuscany",
    "eifel grand prix": "eifel",
    "sakhir grand prix": "sakhir",
    "portuguese grand prix": "portugal",
    "turkish grand prix": "turkey",
    "qatar grand prix": "qatar",
    "united states grand prix": "united-states",
    "british grand prix": "great-britain",
}


def match_event(event_name: str, season_events: pd.DataFrame, grands_prix: pd.DataFrame) -> tuple[str | None, str]:
    """Return (event_id, method) for a lap-source event name within one season.

    ``season_events`` needs columns event_id, grand_prix_id; ``grands_prix`` needs grand_prix_id,
    name, full_name, short_name.
    """
    norm = normalize_text(event_name)
    gp = grands_prix.set_index("grand_prix_id")
    candidates = season_events[["event_id", "grand_prix_id"]].copy()
    if candidates.empty:
        return None, "no_events"

    def names(gid: str) -> set[str]:
        if gid not in gp.index:
            return set()
        row = gp.loc[gid]
        vals = {row.get("full_name"), row.get("short_name"), f"{row.get('name')} grand prix"}
        return {normalize_text(v) for v in vals if isinstance(v, str)}

    exact = [r.event_id for r in candidates.itertuples() if norm in names(r.grand_prix_id)]
    if len(exact) == 1:
        return exact[0], "full_name"
    override = EVENT_NAME_OVERRIDES.get(norm)
    if override:
        hit = candidates[candidates.grand_prix_id == override]
        if len(hit) == 1:
            return hit.event_id.iloc[0], "override"
    # token overlap fallback
    tokens = set(norm.replace("grand prix", "").split())
    best, best_score = None, 0.0
    for r in candidates.itertuples():
        for n in names(r.grand_prix_id):
            t = set(n.replace("grand prix", "").split())
            if not t or not tokens:
                continue
            score = len(tokens & t) / len(tokens | t)
            if score > best_score:
                best, best_score = r.event_id, score
    if best is not None and best_score >= 0.5:
        return best, f"token_overlap:{best_score:.2f}"
    return None, "unresolved"


@dataclass
class DriverResolution:
    driver_id: str | None
    constructor_id: str | None
    method: str


class DriverResolver:
    """Resolve (event, session, car number, abbreviation) to F1DB driver/constructor IDs."""

    def __init__(self, participants: pd.DataFrame, drivers: pd.DataFrame):
        """``participants``: event_id, season, session_code, driver_number, driver_id, constructor_id.
        ``drivers``: driver_id, abbreviation."""
        p = participants.dropna(subset=["driver_id"]).copy()
        p["driver_number"] = p["driver_number"].astype("Int64").astype(str)
        self.p = p
        self.abbr = drivers.set_index("driver_id")["abbreviation"].to_dict()

    def resolve(self, event_id: str, season: int, session_code: str, number, abbreviation: str | None) -> DriverResolution:
        num = str(int(float(number))) if number not in (None, "", "None") and pd.notna(number) else None
        abbr = (abbreviation or "").upper() or None
        p = self.p
        if num is not None:
            hit = p[(p.event_id == event_id) & (p.session_code == session_code) & (p.driver_number == num)]
            if len(hit["driver_id"].unique()) == 1:
                return DriverResolution(hit.driver_id.iloc[0], hit.constructor_id.iloc[0], "session_number")
            hit = p[(p.event_id == event_id) & (p.driver_number == num)]
            if len(hit["driver_id"].unique()) == 1:
                return DriverResolution(hit.driver_id.iloc[0], hit.constructor_id.iloc[0], "event_number")
            hit = p[(p.season == season) & (p.driver_number == num)]
            ids = hit["driver_id"].unique()
            if abbr:
                ids = [i for i in ids if self.abbr.get(i) == abbr]
            if len(ids) == 1:
                row = hit[hit.driver_id == ids[0]].iloc[-1]
                return DriverResolution(ids[0], row.constructor_id, "season_number_abbr")
        if abbr:
            season_ids = p[p.season == season]["driver_id"].unique()
            ids = [i for i in season_ids if self.abbr.get(i) == abbr]
            if len(ids) == 1:
                ev = p[(p.event_id == event_id) & (p.driver_id == ids[0])]
                cons = ev.constructor_id.iloc[0] if len(ev) else p[(p.season == season) & (p.driver_id == ids[0])].constructor_id.iloc[-1]
                return DriverResolution(ids[0], cons, "season_abbr")
        return DriverResolution(None, None, "unresolved")
