"""Critic Agent — cross-examines findings for contradictions and credibility."""

import json
import logging
from typing import Optional

import ollama

logger = logging.getLogger(__name__)

_CRITIC_SYSTEM = (
    "You are a rigorous research critic. You are given a list of findings "
    "(each with a summary, source URL, and optional title) and the subtopics "
    "the research was targeting.\n\n"
    "Your task: analyse the findings and return a JSON object with exactly "
    "these keys:\n"
    '  "verified_claims": [list of strings — claims that are well-supported across sources],\n'
    '  "contradictions": [list of {{"claim_a": string, "claim_b": string, "note": string}}],\n'
    '  "weak_sources": [list of {{"url": string, "issue": string}}],\n'
    '  "overall_confidence": one of "high", "medium", "low",\n'
    '  "recommendation": one of "proceed", "needs_more_research".\n\n'
    "Base your analysis strictly on the text provided. Flag contradictions, "
    "out-of-date information, unsourced claims, and source bias. "
    "Return ONLY valid JSON — no markdown, no explanations."
)


async def critique(findings: list, subtopics: list, model: str) -> dict:
    """Cross-examine *findings* for contradictions, weak sources, and overall confidence.

    Parameters
    ----------
    findings : list[dict]
        Each dict should contain at least: id, url, title, summary.
    subtopics : list[str]
        Target subtopics from the Planner.
    model : str
        Ollama chat model name.

    Returns
    -------
    dict
        Keys: verified_claims, contradictions, weak_sources,
        overall_confidence, recommendation.

    Raises
    ------
    RuntimeError
        If the LLM response cannot be parsed as JSON after a retry.
    """
    data = await _call(findings, subtopics, model, _CRITIC_SYSTEM)
    if data is not None:
        return data

    # retry with stricter instructions
    data = await _call(findings, subtopics, model, _CRITIC_SYSTEM + "\n\n"
                       "CRITICAL: Output MUST be a single JSON object. No extra text.")
    if data is not None:
        return data

    raise RuntimeError("Critic failed to produce valid JSON after 2 attempts.")


# ── internal helpers ────────────────────────────────────────────────────

async def _call(findings: list, subtopics: list, model: str, system: str) -> Optional[dict]:
    # Build a compact representation of the findings for the prompt
    lines = []
    for f in findings:
        lines.append(
            f"- [{f.get('title', 'Untitled')}]({f.get('url', '?')})\n"
            f"  Summary: {f.get('summary', 'N/A')}"
        )
    findings_text = "\n\n".join(lines)

    subtopics_text = "\n".join(f"- {t}" for t in subtopics)

    user_prompt = (
        f"Subtopics to investigate:\n{subtopics_text}\n\n"
        f"Findings to evaluate:\n{findings_text}"
    )

    client = ollama.AsyncClient()
    response = await client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
        format="json",
    )

    raw: str = response["message"]["content"].strip()

    # strip possible markdown fences
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Critic JSON parse error (retry will follow): %s — raw=[%s]", exc, raw[:200])
        return None

    required = {"verified_claims", "contradictions", "weak_sources", "overall_confidence", "recommendation"}
    if not required.issubset(data.keys()):
        logger.warning("Critic response missing required keys. Found: %s", list(data.keys()))
        return None

    return data
