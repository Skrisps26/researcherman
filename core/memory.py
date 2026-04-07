"""ChromaDB-based persistent memory for research findings."""

import logging
from typing import Optional

import chromadb

logger = logging.getLogger(__name__)

# Default persistent path inside the project's data directory
DEFAULT_COLLECTION = "research_findings"
DEFAULT_PERSIST_DIR = "data/chroma_db"


class Memory:
    """Thin wrapper around a persistent ChromaDB collection for storing and querying research findings."""

    def __init__(
        self,
        persist_directory: str = DEFAULT_PERSIST_DIR,
        collection_name: str = DEFAULT_COLLECTION,
        embed_model: str = "nomic-embed-text",
        ollama_base_url: str = "http://localhost:11434",
    ) -> None:
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.embed_model = embed_model
        self.ollama_base_url = ollama_base_url.rstrip("/")

        # Initialise (or load) the persistent ChromaDB client
        self._client: chromadb.PersistentClient = chromadb.PersistentClient(
            path=self.persist_directory
        )

        # Ensure the collection exists
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ── write operations ───────────────────────────────────────────────

    def add(
        self,
        doc_id: str,
        document: str,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> None:
        """Add a single finding document to the collection.

        If no ``embedding`` is supplied it is generated on-the-fly via Ollama.
        """
        if embedding is None:
            embedding = self._embed(document)

        self._collection.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata or {}],
            embeddings=[embedding],
        )
        logger.debug("Added document id=%s", doc_id)

    def add_many(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> None:
        """Batch-add multiple finding documents."""
        if embeddings is None:
            embeddings = [self._embed(d) for d in documents]

        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas or [{} for _ in ids],
            embeddings=embeddings,
        )
        logger.debug("Batch-added %d documents", len(ids))

    # ── read operations ────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        n_results: int = 10,
    ) -> dict:
        """Semantic similarity search over stored findings."""
        query_embedding = self._embed(query_text)
        return self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    def get_all(self) -> dict:
        """Return every document stored in the collection."""
        return self._collection.get(
            include=["documents", "metadatas", "embeddings"]
        )

    def count(self) -> int:
        """Number of stored findings."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete and re-create the collection (⚠️  destroys all data)."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.warning("Collection %s has been reset", self.collection_name)

    # ── internal helpers ───────────────────────────────────────────────

    def _embed(self, text: str) -> list[float]:
        """Return a single embedding vector via Ollama."""
        import requests as _requests

        resp = _requests.post(
            f"{self.ollama_base_url}/api/embeddings",
            json={"model": self.embed_model, "prompt": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
