"""Planner Agent — decomposes a research question into a structured plan."""

import json
import logging
from typing import Optional

import ollama

logger = logging.getLogger(__name__)

_PLANNER_SYSTEM = (
    "You are a research planner. Given a research question, produce a JSON object "
    "with exactly these keys:\n"
    '  "main_question" (string) — a clear reformulation of the user\'s question,\n'
    '  "subtopics" (list of strings) — 3-5 distinct aspects to investigate,\n'
    '  "search_queries" (list of strings) — 3-5 specific DuckDuckGo queries, one per subtopic,\n'
    '  "scope" (string) — one of "narrow", "medium", or "broad".\n'
    "Return ONLY valid JSON. No explanations, no markdown code fences, no YAML."
)

_STRICT_SYSTEM = (
    _PLANNER_SYSTEM
    + "\n\nCRITICAL: You must return nothing but a single JSON object. "
    "Do NOT wrap it in markdown. Do NOT include any text before or after the JSON."
)


async def plan(question: str, model: str) -> dict:
    """Break *question* into a structured research plan.

    Parameters
    ----------
    question : str
        The user's research question.
    model : str
        Ollama model name to use (e.g. "mistral:7b-instruct-q4_K_M").

    Returns
    -------
    dict
        Keys: main_question, subtopics, search_queries, scope.

    Raises
    ------
    RuntimeError
        If the LLM response cannot be parsed as JSON after a retry.
    """
    result = await _call(question, model, _PLANNER_SYSTEM)
    if result is not None:
        return result

    # retry with stricter prompt
    result = await _call(question, model, _STRICT_SYSTEM)
    if result is not None:
        return result

    raise RuntimeError("Planner failed to produce valid JSON after 2 attempts.")


# ── internal helpers ────────────────────────────────────────────────────────


async def _call(question: str, model: str, system_prompt: str) -> Optional[dict]:
    """Send a single planning request to Ollama, return parsed dict or None."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    client = ollama.AsyncClient()
    response = await client.chat(
        model=model,
        messages=messages,
        format="json",
    )

    raw: str = response["message"]["content"].strip()

    # strip possible markdown code fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Planner JSON parse error (retry will follow): %s — raw=[%s]", exc, raw[:200])
        return None

    # validate required keys
    for key in ("main_question", "subtopics", "search_queries", "scope"):
        if key not in data:
            logger.warning("Planner missing required key '%s'", key)
            return None

    return {"main_question": data["main_question"],
            "subtopics": list(data["subtopics"]),
            "search_queries": list(data["search_queries"]),
            "scope": data["scope"]}
