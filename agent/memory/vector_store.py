"""
Semantic memory layer — ChromaDB for meaning-based search.
Enables searching by meaning rather than exact keywords.
'That conversation about the Tacloban budget' finds it even without exact words.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.memory.vector")


class VectorStore:
    """Semantic memory — everything searchable by meaning."""

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self.client = None
        self.collection = None

    def initialise(self):
        """Set up ChromaDB with local persistence."""
        try:
            import chromadb
            from chromadb.config import Settings

            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False),
            )
            self.collection = self.client.get_or_create_collection(
                name="mira_memory",
                metadata={"hnsw:space": "cosine"},
            )
            count = self.collection.count()
            logger.info(f"ChromaDB initialised. {count} embeddings loaded.")
        except ImportError:
            logger.warning("ChromaDB not installed. Semantic search disabled.")
            logger.warning("Install with: pip install chromadb")

    def add(
        self,
        text: str,
        memory_id: str,
        category: str = "general",
        source: str = "telegram",
        importance: int = 3,
        metadata: dict = None,
    ):
        """Add a text to the semantic store with metadata."""
        if not self.collection:
            logger.warning("ChromaDB not initialised. Skipping semantic store.")
            return

        meta = {
            "category": category,
            "source": source,
            "importance": importance,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            meta.update({k: str(v) for k, v in metadata.items()})

        self.collection.upsert(
            documents=[text],
            ids=[str(memory_id)],
            metadatas=[meta],
        )
        logger.debug(f"Semantic embedding stored for memory {memory_id}")

    def search(
        self,
        query: str,
        n_results: int = 10,
        category: str = None,
        min_importance: int = None,
    ) -> list[dict]:
        """Search by meaning. Returns similar memories ranked by relevance."""
        if not self.collection:
            logger.warning("ChromaDB not initialised. Cannot search.")
            return []

        where_filters = {}
        if category:
            where_filters["category"] = category
        if min_importance is not None:
            where_filters["importance"] = {"$gte": min_importance}

        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filters if where_filters else None,
        )

        memories = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                memories.append({
                    "id": results["ids"][0][i],
                    "content": doc,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return memories

    def delete(self, memory_id: str):
        """Remove a memory from semantic store."""
        if self.collection:
            self.collection.delete(ids=[str(memory_id)])

    def count(self) -> int:
        """How many embeddings are stored."""
        return self.collection.count() if self.collection else 0
