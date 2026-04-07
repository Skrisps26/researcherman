# Multi-Agent Research Assistant — Build Spec

## Project Overview

A locally-running multi-agent research assistant that accepts a research question, autonomously breaks it down, searches the web, fact-checks findings, and synthesizes a final structured report — all powered by local Ollama models. Everything runs in a single self-contained folder with no external cloud dependencies.

---

## Hardware Constraints

> ⚠️ **Critical: Only 4GB VRAM is available.** All model choices and pipeline decisions must respect this limit.

- Use **only one model loaded at a time**. Do not attempt to run multiple Ollama models simultaneously — swap models between agent steps instead.
- Recommended model: **mistral:7b-instruct-q4_K_M** (~4GB RAM, runs comfortably within 4GB VRAM at 4-bit quantization). This is the default for all agents.
- Alternatively: **phi3:mini** (~2.3GB) if mistral is too slow on the hardware — faster inference, slightly weaker reasoning.
- **Do not use**: llama3:70b, mixtral, or any model above 7B parameters.
- For embeddings: use **nomic-embed-text** via Ollama (very lightweight, CPU-friendly, does not compete for VRAM).
- Each agent call should be **stateless and sequential** — one agent runs, finishes, hands off output, then the next agent runs. No parallel model inference.

---

## Folder Structure

> ⚠️ **Everything must live in a single folder.** No installs outside the project directory. No global dependencies except Ollama itself (which must already be installed on the machine).

```
research-agent/
│
├── main.py                  # Entry point — starts the FastAPI backend
├── requirements.txt         # All Python dependencies
├── .env                     # Ollama base URL, model name, config
│
├── agents/
│   ├── __init__.py
│   ├── planner.py           # Planner Agent
│   ├── searcher.py          # Search Agent
│   ├── critic.py            # Critic Agent
│   └── writer.py            # Writer Agent
│
├── core/
│   ├── __init__.py
│   ├── orchestrator.py      # Runs agents in sequence, manages state
│   ├── memory.py            # ChromaDB vector store wrapper
│   └── scraper.py           # Web scraping utility (BeautifulSoup)
│
├── data/
│   ├── chroma_db/           # Persistent ChromaDB storage (auto-created)
│   └── reports/             # Final generated reports saved as .md files
│
└── frontend/
    ├── index.html
    ├── main.jsx             # React entry point
    ├── components/
    │   ├── QueryInput.jsx       # Research question input
    │   ├── AgentFeed.jsx        # Live agent activity log
    │   ├── MemoryPanel.jsx      # Shows what's been stored in memory
    │   └── ReportViewer.jsx     # Final report with markdown rendering
    └── styles/
        └── index.css
```

---

## Agent Roster

All agents use the same underlying Ollama model (`mistral:7b-instruct-q4_K_M`). They are differentiated by their **system prompt** and the **shape of their input/output**. The orchestrator calls them one by one.

---

### 1. 🗺️ Planner Agent
**File:** `agents/planner.py`

**Purpose:** Takes the user's raw research question and breaks it down into a structured search plan.

**Input:** Raw research question string

**Output:** JSON object:
```json
{
  "main_question": "...",
  "subtopics": ["...", "...", "..."],
  "search_queries": ["...", "...", "..."],
  "scope": "narrow | medium | broad"
}
```

**System Prompt Guidance:**
- Instruct the model to act as a research strategist
- Tell it to produce 3–5 subtopics and 3–5 concrete web search queries
- Output must be valid JSON only — no preamble, no markdown fences
- Keep subtopics atomic and non-overlapping

**Notes:**
- This is the first agent to run — its output gates everything downstream
- If JSON parsing fails, retry once with a stricter prompt before raising an error

---

### 2. 🌐 Search Agent
**File:** `agents/searcher.py`

**Purpose:** Takes each search query from the Planner, scrapes web results, extracts meaningful content, and stores findings in ChromaDB.

**Input:** List of search queries from Planner output

**Output:** List of finding objects stored in ChromaDB:
```json
{
  "query": "...",
  "source_url": "...",
  "raw_excerpt": "...",
  "summary": "..."
}
```

**System Prompt Guidance:**
- Instruct the model to summarise a scraped web excerpt in 3–5 sentences
- Focus on factual claims only — no opinions, no fluff
- Tag each summary with a confidence level: `high | medium | low` based on source quality

**Scraping Notes (`core/scraper.py`):**
- Use `DuckDuckGo Search API` (via `duckduckgo-search` Python package) — no API key needed
- Fetch top 3 results per query using `requests` + `BeautifulSoup`
- Strip nav, footer, ads — extract only `<p>` and `<article>` tags
- Truncate extracted text to 2000 characters before sending to Ollama (to stay within context window)
- Skip URLs that return non-200 or timeout after 5 seconds

**Memory Notes (`core/memory.py`):**
- Use `chromadb` with a persistent local client pointed at `data/chroma_db/`
- Embed summaries using `nomic-embed-text` via Ollama
- Collection name: `research_findings`
- Metadata fields: `query`, `source_url`, `confidence`, `timestamp`

---

### 3. 🕵️ Critic Agent
**File:** `agents/critic.py`

**Purpose:** Retrieves all stored findings from ChromaDB and cross-examines them for contradictions, weak sources, and unsupported claims.

**Input:** All ChromaDB documents for the current research session

**Output:** JSON object:
```json
{
  "verified_claims": ["..."],
  "contradictions": [
    { "claim_a": "...", "claim_b": "...", "note": "..." }
  ],
  "weak_sources": ["..."],
  "overall_confidence": "high | medium | low",
  "recommendation": "proceed | needs_more_research"
}
```

**System Prompt Guidance:**
- Instruct the model to act as a skeptical academic reviewer
- Look for internal contradictions between findings from different sources
- Flag any claims that appear only once with no corroboration
- If `recommendation` is `needs_more_research`, the orchestrator should loop back and trigger the Search Agent with refined queries (max 1 retry loop to avoid infinite loops)

---

### 4. ✍️ Writer Agent
**File:** `agents/writer.py`

**Purpose:** Takes verified claims, contradictions, and confidence levels from the Critic and writes a final structured research report in Markdown.

**Input:** Critic Agent output + original Planner subtopics

**Output:** A Markdown string with the following structure:
```markdown
# Research Report: [Main Question]

## Summary
...

## Findings by Subtopic
### [Subtopic 1]
...

### [Subtopic 2]
...

## Contradictions & Caveats
...

## Sources
- [url] — [confidence]

## Confidence Assessment
Overall confidence: [high | medium | low]
Generated: [timestamp]
```

**System Prompt Guidance:**
- Instruct the model to write in a clear, academic but accessible tone
- Every claim must trace back to a source URL
- Do not hallucinate — if something is uncertain, say so explicitly in the report
- Output must be pure Markdown, nothing else

**Notes:**
- Save the final report as a `.md` file in `data/reports/` with a timestamped filename
- Also return the Markdown string via the API for the frontend to render

---

## Orchestrator

**File:** `core/orchestrator.py`

Manages the full agent pipeline and streams status events to the frontend via **Server-Sent Events (SSE)**.

**Pipeline:**
```
User Query
    │
    ▼
[Planner Agent]         → emits: "Planning research..."
    │
    ▼
[Search Agent]          → emits: "Searching: <query>" for each query
    │
    ▼
[Critic Agent]          → emits: "Cross-checking findings..."
    │
    └─► if needs_more_research → [Search Agent again] (once only)
    │
    ▼
[Writer Agent]          → emits: "Writing report..."
    │
    ▼
Final Report            → emits: "Done." + report content
```

**SSE Event Shape:**
```json
{
  "agent": "planner | searcher | critic | writer | system",
  "status": "started | working | done | error",
  "message": "Human-readable status string",
  "data": { }
}
```

---

## Backend API

**File:** `main.py` — FastAPI app

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/research` | Starts a new research run, returns `session_id` |
| `GET` | `/stream/{session_id}` | SSE stream of agent activity events |
| `GET` | `/report/{session_id}` | Returns the final Markdown report |
| `GET` | `/memory/{session_id}` | Returns all ChromaDB findings for a session |
| `DELETE` | `/memory/{session_id}` | Clears ChromaDB findings for a session |

---

## Frontend UI

**Stack:** React (via Vite) + Tailwind CSS

**Layout:** Two-panel design

```
┌──────────────────────┬────────────────────────────────┐
│   🧠 Agent Feed      │   📄 Report Viewer             │
│                      │                                │
│  ● Planner: Done     │  # Research Report: ...        │
│  ● Searcher: 3/5     │                                │
│  ● Critic: Working..│  ## Summary                    │
│  ○ Writer: Waiting   │  ...                           │
│                      │                                │
│  📦 Memory Panel     │  ## Findings                   │
│  12 chunks stored    │  ...                           │
│  3 sources           │                                │
│                      │  [Copy] [Download .md]         │
└──────────────────────┴────────────────────────────────┘
        [ Enter your research question...        ] [Go]
```

**Key UI behaviours:**
- Agent Feed updates in real time via SSE — each agent has a spinner while active, checkmark when done
- Memory Panel shows a live count of chunks stored and source URLs found
- Report Viewer renders Markdown with syntax highlighting
- "Download .md" button saves the report locally
- Disable the input field while a run is in progress
- Show a clear error state if Ollama is unreachable (with instructions to run `ollama serve`)

---

## Dependencies

**`requirements.txt`**
```
fastapi
uvicorn
requests
beautifulsoup4
chromadb
ollama
duckduckgo-search
python-dotenv
sse-starlette
```

**`.env`**
```
OLLAMA_BASE_URL=http://localhost:11434
CHAT_MODEL=mistral:7b-instruct-q4_K_M
EMBED_MODEL=nomic-embed-text
```

---

## Setup Instructions (for the agent to include in README)

```bash
# 1. Make sure Ollama is running
ollama serve

# 2. Pull required models
ollama pull mistral:7b-instruct-q4_K_M
ollama pull nomic-embed-text

# 3. Install Python dependencies
cd research-agent
pip install -r requirements.txt

# 4. Start the backend
python main.py

# 5. Start the frontend
cd frontend
npm install
npm run dev
```

---

## Key Design Decisions to Follow

- **Never load two models at once** — always sequential, never parallel
- **Always validate JSON outputs** from agents before passing downstream — use a retry with a stricter prompt if parsing fails
- **Truncate scraped content** to 2000 chars before sending to Ollama — the 4GB VRAM constraint means shorter contexts are safer
- **ChromaDB collections are session-scoped** — use `session_id` as a namespace so multiple runs don't pollute each other
- **SSE over WebSockets** — simpler to implement, sufficient for one-way streaming
- **All file I/O relative to project root** — no absolute paths, so the folder is fully portable
