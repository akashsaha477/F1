"""The AI entrant: Claude predicts the top ten from the field, recent results and its own knowledge.

It is given the same public information a person would look at (the line-up, the last races, last year's race
here, the expected weather) and *not* the ApexLens model's order, so the two bots are independent entrants.
The ``anthropic`` SDK is an optional dependency (``pip install -e ".[ai]"``); without it, or without
credentials, the entrant reports itself unavailable and the game carries on without it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from apexlens.config.settings import Settings, get_settings
from apexlens.game.scoring import N_PICKS

log = logging.getLogger(__name__)

SYSTEM = (
    "You are a Formula 1 analyst entering a prediction game. Before each race you predict the classified top ten "
    "finishers in order. Use the line-up, the recent results and last year's race given to you, together with what "
    "you know about the drivers, the teams, this circuit and the season's form. Favour the likely outcome over a "
    "bold one: retirements are rare per driver, overtaking is hard at some circuits, and the fastest cars usually "
    "finish at the front. Answer with the requested JSON only."
)


def schema(field_ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "picks": {"type": "array", "items": {"type": "string", "enum": list(field_ids)},
                      "minItems": N_PICKS, "maxItems": N_PICKS,
                      "description": "driver_id of the predicted P1 to P10, in finishing order, no repeats"},
            "rationale": {"type": "string", "description": "two or three sentences on the main calls"},
        },
        "required": ["picks", "rationale"],
        "additionalProperties": False,
    }


def _top_ten(block: dict | None) -> str:
    if not block:
        return "none on record"
    rows = ", ".join(f"P{r['position']} {r['driver_id']} ({r['constructor_id']})" for r in block["top_ten"])
    return f"{block['race']} ({block['date']}): {rows}"


def build_prompt(context: dict) -> str:
    race = context["race"]
    lines = [
        f"Race: {race['name']} — {race['circuit_name']}, {race['date']}, round {race['round']} of the {race['season']} season, "
        f"{race['laps']} laps.",
        "",
        "Line-up (driver_id — name — team):",
        *[f"- {f['driver_id']} — {f['name']} — {f['constructor_id']}" for f in context["field"]],
        "",
        "Most recent races (classified top ten):",
        *([f"- {_top_ten(r)}" for r in context["recent_results"]] or ["- none ingested yet"]),
        "",
        f"Last race at this circuit: {_top_ten(context.get('previous_edition'))}",
    ]
    w = context.get("weather") or {}
    if w:
        lines += ["", f"Expected weather: track {w.get('track_temp_c', '?')} °C, rain risk "
                      f"{round(100 * float(w.get('rain_risk', 0)))}%{' — a wet race is likely' if w.get('wet_race_likely') else ''}."]
    lines += ["", f"Predict the classified top {N_PICKS} in finishing order using the driver_id values above."]
    return "\n".join(lines)


def parse_response(text: str, field_ids: list[str]) -> tuple[list[str], str]:
    data = json.loads(text)
    picks = data.get("picks")
    if not isinstance(picks, list) or len(picks) != N_PICKS:
        raise ValueError(f"expected {N_PICKS} picks, got {picks!r}")
    picks = [str(p) for p in picks]
    unknown = [p for p in picks if p not in set(field_ids)]
    if unknown:
        raise ValueError(f"picks not in the field: {unknown}")
    if len(set(picks)) != N_PICKS:
        raise ValueError("picks contain a repeated driver")
    return picks, str(data.get("rationale", "")).strip()


def _call_claude(prompt: str, field_ids: list[str], s: Settings) -> tuple[str, str]:
    """(JSON text, model id). Raises on any API problem; the caller turns it into an entrant status."""
    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)  # None -> the SDK's own credential resolution
    resp = client.beta.messages.create(
        model=s.game_ai_model, max_tokens=4096,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        system=SYSTEM, messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema(field_ids)}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"the model declined the request ({getattr(resp.stop_details, 'category', None)})")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text, str(resp.model)


def predict(context: dict, *, settings: Settings | None = None,
            caller: Callable[[str, list[str], Settings], tuple[str, str]] | None = None) -> dict:
    """Entrant record: ``{"status": "ok", "picks", "rationale", "model"}`` or ``{"status": "unavailable"|"error", "reason"}``."""
    s = settings or get_settings()
    if not s.game_ai_enabled:
        return {"status": "unavailable", "reason": "AI entrant disabled (APEXLENS_GAME_AI_ENABLED=false)"}
    field_ids = [f["driver_id"] for f in context["field"]]
    prompt = build_prompt(context)
    if caller is None:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return {"status": "unavailable", "reason": "anthropic SDK not installed: pip install -e \".[ai]\""}
        caller = _call_claude
    try:
        text, model = caller(prompt, field_ids, s)
        picks, rationale = parse_response(text, field_ids)
    except Exception as exc:  # noqa: BLE001 - the AI must never break the game
        name = type(exc).__name__
        # the SDK raises AuthenticationError for a bad key and TypeError when no credentials are configured at all
        if name == "AuthenticationError" or "resolve authentication" in str(exc):
            log.warning("AI entrant unavailable: no usable Anthropic credentials")
            return {"status": "unavailable", "reason": "no Anthropic credentials: set ANTHROPIC_API_KEY or run `ant auth login`"}
        log.warning("AI entrant failed: %s: %s", name, exc)
        return {"status": "error", "reason": f"{name}: {exc}"[:300]}
    return {"status": "ok", "picks": picks, "rationale": rationale, "model": model}
