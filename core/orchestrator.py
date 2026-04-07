"""Orchestrator — sequential agent pipeline manager for research sessions."""

import asyncio
import json
import logging
from typing import AsyncGenerator

from agents import planner, searcher, critic, writer
from core.memory import Memory

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs agents in sequence, manages state, yields SSE-style events."""

    def __init__(
        self,
        model: str,
        embed_model: str,
        ollama_base_url: str,
        max_search_retries: int = 1,
    ) -> None:
        self.model = model
        self.embed_model = embed_model
        self.ollama_base_url = ollama_base_url
        self.max_search_retries = max_search_retries

    async def run(
        self,
        question: str,
        session_id: str,
    ) -> AsyncGenerator[dict, None]:
        """Execute the full research pipeline for *question*.

        Yields event dicts:
            {"agent": "...", "status": "...", "message": "...", "data": {...}}
        """

        def _event(agent: str, status: str, message: str, data: dict | None = None) -> dict:
            evt = {"agent": agent, "status": status, "message": message}
            if data is not None:
                evt["data"] = data
            return evt

        memory = Memory(
            persist_directory=f"data/chroma_db/{session_id}",
            collection_name=f"findings_{session_id}",
            embed_model=self.embed_model,
            ollama_base_url=self.ollama_base_url,
        )

        state: dict = {
            "session_id": session_id,
            "question": question,
            "plan": None,
            "findings": [],
            "critic": None,
            "report": None,
            "state": "running",
        }

        try:
            # ── 1. Planner ──────────────────────────────────────
            logger.info("[%s] Planner starting", session_id)
            yield _event("planner", "started", f"Planning research on: {question}")

            plan_result = await planner.plan(question, self.model)
            state["plan"] = plan_result

            yield _event(
                "planner",
                "done",
                f"Plan complete — {len(plan_result['subtopics'])} subtopics, {len(plan_result['search_queries'])} queries.",
                {"subtopics": plan_result["subtopics"], "queries": plan_result["search_queries"]},
            )

            # ── 2. Search (with optional retry) ─────────────────
            search_retries = 0
            while True:
                queries = plan_result["search_queries"]
                total_q = len(queries)

                yield _event("searcher", "started", f"Starting search — {total_q} queries")

                for i, q in enumerate(queries):
                    yield _event(
                        "searcher",
                        "working",
                        f"Searching: {q} ({i + 1}/{total_q})",
                    )

                findings = await searcher.search(queries, memory, self.model, self.embed_model)
                state["findings"] = findings

                yield _event(
                    "searcher",
                    "done",
                    f"Search complete — {len(findings)} findings stored.",
                )

                # --- Critic ---
                yield _event("critic", "started", "Cross-checking findings...")

                critic_result = await critic.critique(
                    findings, plan_result["subtopics"], self.model,
                )
                state["critic"] = critic_result

                yield _event(
                    "critic",
                    "done",
                    f"Critique complete — confidence: {critic_result['overall_confidence']}",
                    {
                        "confidence": critic_result["overall_confidence"],
                        "recommendation": critic_result["recommendation"],
                    },
                )

                # Decision: retry search?
                if (
                    critic_result.get("recommendation") == "needs_more_research"
                    and search_retries < self.max_search_retries
                ):
                    search_retries += 1
                    logger.info(
                        "[%s] Critic recommends more research — retry %d/%d",
                        session_id,
                        search_retries,
                        self.max_search_retries,
                    )
                    yield _event(
                        "system",
                        "working",
                        f"Running additional research pass ({search_retries}/{self.max_search_retries})...",
                    )
                    continue  # loop back to search
                else:
                    break  # proceed to writing

            # ── 3. Writer ───────────────────────────────────────
            yield _event("writer", "started", "Writing final report...")

            report = await writer.write_report(
                state["critic"],
                state["plan"],
                state["findings"],
                self.model,
            )
            state["report"] = report
            state["state"] = "done"

            yield _event(
                "writer",
                "done",
                f"Report written — {len(report)} characters.",
                {"report": report},
            )

            # Save report to disk
            from pathlib import Path
            reports_dir = Path("data/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = reports_dir / f"report_{session_id}_{ts}.md"
            report_path.write_text(report, encoding="utf-8")
            state["report_path"] = str(report_path)

            yield _event(
                "system",
                "done",
                f"Research complete. Report saved to {report_path}",
            )

        except Exception as exc:
            logger.exception("[%s] Pipeline failed", session_id)
            state["state"] = "error"
            state["error"] = str(exc)
            yield _event("system", "error", f"Research failed: {exc}")
