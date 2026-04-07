"""Writer Agent — generates a structured markdown research report."""

import logging

import ollama

logger = logging.getLogger(__name__)

_WRITER_SYSTEM = (
    "You are a professional research writer. You will be given the following "
    "inputs:\n"
    "  - A planner result with the main question, subtopics, and scope.\n"
    "  - A critic result with verified claims, contradictions, weak sources, "
    "    and a confidence assessment.\n"
    "  - A list of raw findings (each with url, title, summary).\n\n"
    "Produce a comprehensive Markdown research report with these sections:\n\n"
    "1. A clear title (H1) and an executive summary (H2).\n"
    "2. Findings organised by subtopic (H2 for each subtopic, with bullet or paragraph content).\n"
    "3. Contradictions and Caveats (H2) — explain any conflicting findings.\n"
    "4. Sources (H2) — numbered list with title and URL.\n"
    "5. Confidence Assessment (H2) — quote the critic's overall confidence and note limitations.\n\n"
    "Write clearly and objectively. Use markdown throughout. "
    "Return the report as plain markdown text — no JSON, no code fences."
)


async def write_report(
    critic_result: dict,
    planner_result: dict,
    findings: list,
    model: str,
) -> str:
    """Generate a structured Markdown report from all previous agent outputs.

    Parameters
    ----------
    critic_result : dict
        From Critic Agent: verified_claims, contradictions, weak_sources,
        overall_confidence, recommendation.
    planner_result : dict
        From Planner Agent: main_question, subtopics, search_queries, scope.
    findings : list[dict]
        Each dict has keys: id, query, url, title, summary.
    model : str
        Ollama chat model name.

    Returns
    -------
    str
        Full Markdown report.
    """
    # Build a readable prompt for the writer
    planner_block = (
        f"Main Question: {planner_result.get('main_question', 'N/A')}\n"
        f"Scope: {planner_result.get('scope', 'N/A')}\n"
        f"Subtopics:\n"
        + "\n".join(f"  - {t}" for t in planner_result.get("subtopics", []))
    )

    critic_block = (
        f"Overall Confidence: {critic_result.get('overall_confidence', 'N/A')}\n"
        f"Recommendation: {critic_result.get('recommendation', 'N/A')}\n"
        f"Verified Claims:\n"
        + "\n".join(f"  ✓ {c}" for c in critic_result.get("verified_claims", []))
        + "\n\n"
        f"Contradictions:\n"
        + "\n".join(
            f"  ⚠ {c.get('claim_a', '?')} vs {c.get('claim_b', '?')} — {c.get('note', '')}"
            for c in critic_result.get("contradictions", [])
        )
        + "\n\n"
        f"Weak Sources:\n"
        + "\n".join(
            f"  ❌ {s.get('url', '?')} — {s.get('issue', 'Unknown issue')}"
            for s in critic_result.get("weak_sources", [])
        )
    )

    findings_block = ""
    for f in findings:
        findings_block += (
            f"- [{f.get('title', 'Untitled')}]({f.get('url', '?')})\n"
            f"  {f.get('summary', 'N/A')}\n\n"
        )

    user_prompt = (
        f"### PLANNER OUTPUT\n{planner_block}\n\n"
        f"### CRITIC OUTPUT\n{critic_block}\n\n"
        f"### RAW FINDINGS\n{findings_block}"
    )

    client = ollama.AsyncClient()
    response = await client.chat(
        model=model,
        messages=[
            {"role": "system", "content": _WRITER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
    )

    report: str = response["message"]["content"].strip()
    logger.info("write_report() complete — %d chars generated", len(report))
    return report
