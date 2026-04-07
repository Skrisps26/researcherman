# ResearcherMan 🧪📚

An autonomous multi-agent research system powered by Ollama that takes a research question, plans a search strategy, executes web searches, evaluates findings for credibility, and produces a structured markdown report.

## Architecture

ResearcherMan uses a pipeline of specialized AI agents:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Planner  │ -> │ Searcher │ -> │  Critic  │ -> │  Writer  │ -> │  Report  │
│  Agent   │    │  Agent   │    │  Agent   │    │  Agent   │    │  (Markdown) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

- **Planner Agent** (`agents/planner.py`): Decomposes a research question into subtopics and targeted search queries. Output includes scope assessment (narrow/medium/broad).
- **Search Agent** (`agents/searcher.py`): Executes search queries via DuckDuckGo, scrapes web content, generates concise summaries with Ollama, and stores all findings in a ChromaDB vector store for sem-aware retrieval.
- **Critic Agent** (`agents/critic.py`): Cross-examines all collected findings, identifies contradictions between sources, flags weak or unsupported claims, and assigns a confidence score.
- **Writer Agent** (`agents/writer.py`): Synthesizes verified claims, contradictions, subtopic breakdowns, and source citations into a well-structured markdown research report.

## Project Structure

```
researcherman/
├── .env                    # Environment configuration (Ollama URL, model names)
├── requirements.txt        # Python dependencies
├── venv/                   # Python virtual environment
├── README.md               # This file
├── agents/
│   ├── __init__.py
│   ├── planner.py          # Planner Agent - question decomposition
│   ├── searcher.py         # Search Agent - web search & summarization
│   ├── critic.py           # Critic Agent - fact checking & validation
│   └── writer.py           # Writer Agent - report generation
├── core/
│   ├── __init__.py
│   ├── memory.py           # ChromaDB vector store wrapper
│   └── scraper.py          # Web content scraper (BS4-based)
├── data/
│   ├── chroma_db/          # ChromaDB persistent storage
│   └── reports/            # Generated markdown reports
└── frontend/
    └── src/
        ├── components/     # Frontend UI components
        └── styles/         # Frontend stylesheets
```

## Prerequisites

- **Python 3.10+**
- **Ollama** running locally with required models pulled:
  - `mistral:7b-instruct-q4_K_M` (default chat model)
  - `nomic-embed-text` (default embedding model)

Install and start Ollama:

```bash
# Install Ollama (Linux/macOS)
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull mistral:7b-instruct-q4_K_M
ollama pull nomic-embed-text

# Start Ollama server
ollama serve
```

## Quick Start

```bash
# 1. Activate virtual environment (already created)
source venv/bin/activate   # On Windows: venv\Scripts\activate

# 2. Dependencies already installed via pip install -r requirements.txt

# 3. Start the backend
python main.py

# 4. In another terminal, start the frontend
cd frontend && npm run dev
```

Open http://localhost:3000 in your browser. Enter a research question and hit Go~!

## Configuration

All settings are managed via `.env`:

| Variable         | Default                                  | Description                     |
|------------------|------------------------------------------|---------------------------------|
| `OLLAMA_BASE_URL`| `http://localhost:11434`                 | Ollama API endpoint             |
| `CHAT_MODEL`     | `mistral:7b-instruct-q4_K_M`             | LLM for reasoning & writing     |
| `EMBED_MODEL`    | `nomic-embed-text`                       | Embedding model for vector store|

### Using Different Models

You can swap in any Ollama-compatible model by editing `.env`:

```bash
# Larger model for accuracy
CHAT_MODEL=llama3:70b

# Faster model for quick results
CHAT_MODEL=phi3:3.8b
```

## Agent Details

### Planner Agent

Takes a free-form research question and returns:

```json
{
  "main_question": "Clear reformulation of the research question",
  "subtopics": ["topic1", "topic2", "topic3"],
  "search_queries": ["query1", "query2", "query3"],
  "scope": "narrow | medium | broad"
}
```

### Search Agent

- Performs DuckDuckGo searches for each query
- Scrapes top 3 results per query using BeautifulSoup4
- Summarizes each page's content with Ollama (keeps summaries concise)
- Stores findings in ChromaDB with embeddings for semantic search

### Critic Agent

Cross-examination outputs:

```json
{
  "verified_claims": ["well-supported claim 1", "..."],
  "contradictions": [
    {"claim_a": "...", "claim_b": "...", "note": "explanation"}
  ],
  "weak_sources": [{"url": "...", "issue": "reason"}],
  "overall_confidence": "high | medium | low",
  "recommendation": "proceed | needs_more_research"
}
```

### Writer Agent

Produces a markdown report with:
- Title and executive summary
- Findings organized by subtopic
- Contradictions and caveats section
- Source list with URLs
- Confidence assessment

## API Usage (FastAPI)

ResearcherMan can also run as a server with SSE (Server-Sent Events) streaming:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints:
- `POST /api/research` - Submit a research question, receive streaming progress updates
- `GET /api/reports` - List generated reports
- `GET /api/reports/{filename}` - Get a specific report's markdown content

## Development

```bash
# Run tests
pytest tests/

# Lint
ruff check .

# Format
ruff format .
```

## License

MIT
