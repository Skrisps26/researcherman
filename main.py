"""Researcherman — FastAPI backend for the multi-agent research assistant."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

import ollama
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import StreamingResponse

from agents import planner, searcher, critic, writer
from core.memory import Memory

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemma4:e2b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Researcherman", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Session state: session_id -> dict with report text and memory
_sessions: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_ollama():
    """Return an Ollama client (for non-chat checks)."""
    return ollama.Client(host=OLLAMA_BASE_URL)


def _ensure_models() -> list[str]:
    """Check required models are available, pull them if not."""
    client = _get_ollama()
    needed = [CHAT_MODEL, EMBED_MODEL]
    resp = client.list()
    available = []
    for m in resp.models:
        available.append(getattr(m, 'name', None) or getattr(m, 'model', ''))
    missing = []
    for model in needed:
        if not any(model in a for a in available):
            missing.append(model)
    return missing


async def _run_research(session_id: str, question: str) -> AsyncGenerator[str, None]:
    """Run the full agent pipeline and yield SSE events."""
    session = _sessions[session_id]

    def _event(agent: str, status: str, message: str, data: dict | None = None):
        payload = {"agent": agent, "status": status, "message": message}
        if data is not None:
            payload["data"] = data
        return json.dumps(payload)

    try:
        # check models exist
        missing = _ensure_models()
        if missing:
            for m in missing:
                yield f"event: message\ndata: {_event('system', 'error', f'Missing model: {m}. Run: ollama pull {m}')}\n\n"

        # --- Planner ---
        session["state"] = "planning"
        yield f"event: message\ndata: {_event('planner', 'started', f'Planning research on: {question}')}\n\n"

        plan_result = await planner.plan(question, CHAT_MODEL)
        session["plan"] = plan_result
        yield f"event: message\ndata: {_event('planner', 'done', 'Plan created.', {'subtopics': plan_result['subtopics'], 'queries': plan_result['search_queries']})}\n\n"

        # --- Search ---
        memory = Memory(
            persist_directory=f"data/chroma_db/{session_id}",
            collection_name=f"research_findings_{session_id}",
            embed_model=EMBED_MODEL,
            ollama_base_url=OLLAMA_BASE_URL,
        )
        session["memory"] = memory

        queries = plan_result["search_queries"]
        for i, q in enumerate(queries):
            yield f"event: message\ndata: {_event('searcher', 'working', f'Searching: {q} ({i + 1}/{len(queries)})')}\n\n"

        findings = await searcher.search(queries, memory, CHAT_MODEL, EMBED_MODEL)
        session["findings"] = findings
        yield f"event: message\ndata: {_event('searcher', 'done', f'Search complete — {len(findings)} findings stored.', {'count': len(findings)})}\n\n"

        # --- Critic ---
        session["state"] = "critiquing"
        yield f"event: message\ndata: {_event('critic', 'started', 'Cross-checking findings...')}\n\n"

        critic_result = await critic.critique(findings, plan_result["subtopics"], CHAT_MODEL)
        session["critic"] = critic_result
        yield f"event: message\ndata: {_event('critic', 'done', f'Critique complete — confidence: {critic_result["overall_confidence"]}.', {
            'confidence': critic_result['overall_confidence'],
            'recommendation': critic_result['recommendation'],
        })}\n\n"

        # --- Optional second search loop ---
        if critic_result["recommendation"] == "needs_more_research":
            yield f"event: message\ndata: {_event('system', 'working', 'Running additional research pass...')}\n\n"
            # Second pass with same queries (could be refined)
            findings2 = await searcher.search(queries, memory, CHAT_MODEL, EMBED_MODEL)
            all_findings = findings + [f for f in findings2 if f not in findings]
            session["findings"] = all_findings
            critic_result = await critic.critique(all_findings, plan_result["subtopics"], CHAT_MODEL)
            session["critic"] = critic_result
            yield f"event: message\ndata: {_event('critic', 'done', 'Second critique complete.')}\n\n"

        # --- Writer ---
        session["state"] = "writing"
        yield f"event: message\ndata: {_event('writer', 'started', 'Writing report...')}\n\n"

        report = await writer.write_report(critic_result, plan_result, findings, CHAT_MODEL)
        session["report"] = report
        session["state"] = "done"
        yield f"event: message\ndata: {_event('writer', 'done', 'Report complete.')}\n\n"

        # Save report to disk
        reports_dir = Path("data/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"report_{session_id}_{timestamp}.md"
        report_path.write_text(report, encoding="utf-8")
        session["report_path"] = str(report_path)

        yield f"event: message\ndata: {_event('system', 'done', 'Done.', {'report': report})}\n\n"

    except Exception as exc:
        logger.exception("Research failed for session %s", session_id)
        session["state"] = "error"
        session["error"] = str(exc)
        yield f"event: message\ndata: {_event('system', 'error', f'Research failed: {exc}')}\n\n"


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------
@app.post("/research")
async def start_research(body: dict):
    """POST /research { "question": "..." } → { "session_id": "..." }"""
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question' in request body.")

    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = {"state": "pending", "question": question, "error": None, "report": None}

    # Start the research pipeline in the background
    asyncio.create_task(_consume_pipeline(session_id, question))

    return {"session_id": session_id}


async def _consume_pipeline(session_id: str, question: str):
    """Consume the SSE generator and store the final report in session state."""
    async for _ in _run_research(session_id, question):
        pass  # Pipeline stores state in _sessions directly


@app.get("/stream/{session_id}")
async def stream_research(session_id: str):
    """GET /stream/{session_id} — SSE feed of agent activity."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    return StreamingResponse(
        _run_research(session_id, _sessions[session_id]["question"]),
        media_type="text/event-stream",
    )


@app.get("/report/{session_id}")
async def get_report(session_id: str):
    """GET /report/{session_id} — Return the final Markdown report."""
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")
    if sess.get("state") != "done":
        raise HTTPException(status_code=202, detail="Report not ready yet.")
    return {"report": sess["report"], "path": sess.get("report_path", "")}


@app.get("/memory/{session_id}")
async def get_memory(session_id: str):
    """GET /memory/{session_id} — Return all ChromaDB findings for a session."""
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")
    memory = sess.get("memory")
    if not memory:
        return {"count": 0, "findings": []}
    all_data = memory.get_all()
    findings = []
    for i, doc_id in enumerate(all_data.get("ids", [])):
        findings.append({
            "id": doc_id,
            "document": all_data.get("documents", [])[i] if i < len(all_data.get("documents", [])) else "",
            "metadata": all_data.get("metadatas", [])[i] if i < len(all_data.get("metadatas", [])) else {},
        })
    return {"count": memory.count(), "findings": findings}


@app.delete("/memory/{session_id}")
async def clear_memory(session_id: str):
    """DELETE /memory/{session_id} — Clear ChromaDB findings for a session."""
    sess = _sessions.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")
    memory = sess.get("memory")
    if memory:
        memory.reset()
    return {"status": "cleared"}


@app.get("/health")
async def health_check():
    """GET /health — Check if Ollama is reachable and models are available."""
    try:
        client = _get_ollama()
        resp = client.list()
        # Newer ollama package returns a Pydantic ListResponse with '.models' (root model, iterable)
        model_names = []
        for m in resp.models:
            name = getattr(m, 'name', None) or getattr(m, 'model', '')
            model_names.append(name)
        chat_available = any(CHAT_MODEL in m for m in model_names)
        embed_available = any(EMBED_MODEL in m for m in model_names)
        return {
            "status": "ok",
            "ollama": "connected",
            "chat_model": {"name": CHAT_MODEL, "available": chat_available},
            "embed_model": {"name": EMBED_MODEL, "available": embed_available},
        }
    except Exception as exc:
        return {"status": "error", "ollama": "disconnected", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
