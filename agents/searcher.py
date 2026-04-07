"""Search Agent — web search, scraping, LLM summarisation, ChromaDB storage."""

import logging
import hashlib
from typing import Optional

from duckduckgo_search import DDGS
import ollama

from core.scraper import scrape
from core.memory import Memory

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM = (
    "You are a research assistant. Summarise the following excerpt from a web page "
    "in 3-5 concise sentences, focusing on factual claims, data points, and key "
    "arguments. Strip opinion and fluff. Keep the summary self-contained."
)

_MAX_SUMMARY_CHARS = 500


async def search(
    queries: list,
    memory: Memory,
    model: str,
    embed_model: str,
    max_results: int = 3,
) -> list:
    """Execute a batch of search queries, scrape, summarise, and store findings.

    Parameters
    ----------
    queries : list[str]
        DuckDuckGo search queries (from the Planner).
    memory : Memory
        ChromaDB-backed memory instance for persisting findings.
    model : str
        Ollama chat model for summarisation.
    embed_model : str
        Ollama embedding model name (used internally by Memory for embeddings).
    max_results : int
        Number of search results to fetch and scrape per query (default 3).

    Returns
    -------
    list[dict]
        Each dict has keys: id, query, url, title, summary.
    """
    findings: list[dict] = []

    with DDGS() as ddgs:
        for query in queries:
            logger.info("Searching for: %s", query)
            try:
                results = list(ddgs.text(query, max_results=max_results))
            except Exception as exc:
                logger.error("DuckDuckGo search failed for query '%s': %s", query, exc)
                results = []

            for hit in results:
                url: str = hit.get("href") or hit.get("link", "")
                title: str = hit.get("title", "")
                snippet: str = hit.get("body", "")

                # skip if already stored
                doc_id = _stable_id(url)
                if memory.count() > 0:
                    existing = memory.get_all()
                    if doc_id in existing.get("ids", []):
                        logger.debug("Already have finding for %s — skipping", url)
                        continue

                # scrape full page
                page_text = scrape(url)
                content = page_text or snippet  # fallback to snippet

                if not content.strip():
                    logger.debug("No text content for %s — skipping", url)
                    continue

                # summarise via Ollama
                summary = await _summarise(content, title, query, model)
                if not summary:
                    summary = snippet[:_MAX_SUMMARY_CHARS]  # last-ditch fallback

                # store in ChromaDB
                meta = {"url": url, "title": title, "query": query}
                memory.add(doc_id=doc_id, document=summary, metadata=meta)

                finding = {"id": doc_id, "query": query, "url": url, "title": title, "summary": summary}
                findings.append(finding)
                logger.info("Stored finding: %s — %s", title, url)

    logger.info("search() complete — %d findings stored", len(findings))
    return findings


# ── internal helpers ────────────────────────────────────────────────────


async def _summarise(content: str, title: str, query: str, model: str) -> str:
    """Ask Ollama to summarise *content* in the context of the original query."""
    prompt = (
        f"Research query: {query}\n"
        f"Page title: {title}\n"
        f"---\n"
        f"{content[:3000]}"
    )

    client = ollama.AsyncClient()
    response = await client.chat(
        model=model,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return response["message"]["content"].strip()


def _stable_id(url: str) -> str:
    """Deterministic short hex id from a URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]
