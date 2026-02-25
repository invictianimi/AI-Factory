"""
The LLM Report — ChromaDB Vector Store
Stores embeddings for collected items and published articles.
Embedding model: all-MiniLM-L6-v2 (local, zero API cost)
Chunking: 512 tokens per chunk, 50-token overlap
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils import embedding_functions

CHROMA_PATH = Path(
    os.environ.get(
        "CHROMA_PATH",
        str(Path(__file__).parent.parent.parent.parent / "data/chroma"),
    )
)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 512  # tokens (approximate as words for now)
CHUNK_OVERLAP = 50

_client: Optional[chromadb.PersistentClient] = None
_embed_fn: Optional[embedding_functions.SentenceTransformerEmbeddingFunction] = None


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return _client


def _get_embed_fn() -> embedding_functions.SentenceTransformerEmbeddingFunction:
    global _embed_fn
    if _embed_fn is None:
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    return _embed_fn


def _get_collection(name: str) -> chromadb.Collection:
    client = _get_client()
    return client.get_or_create_collection(
        name=name,
        embedding_function=_get_embed_fn(),
        metadata={"hnsw:space": "cosine"},
    )


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by approximate token count (words)."""
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def embed_item(item_id: str, title: str, content: str, metadata: dict) -> None:
    """
    Embed a collected item into the vector store.
    Chunks long content, stores each chunk with item metadata.
    """
    collection = _get_collection("source_items")
    text = f"{title}\n\n{content}"
    chunks = _chunk_text(text)
    ids = [f"{item_id}__chunk{i}" for i in range(len(chunks))]
    metadatas = [{**metadata, "item_id": item_id, "chunk_index": i} for i in range(len(chunks))]

    # Add or update
    collection.upsert(
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )


def embed_article(article_id: str, title: str, content: str, metadata: dict) -> None:
    """Embed a published article into the vector store."""
    collection = _get_collection("published_articles")
    text = f"{title}\n\n{content}"
    chunks = _chunk_text(text)
    ids = [f"{article_id}__chunk{i}" for i in range(len(chunks))]
    metadatas = [{**metadata, "article_id": article_id, "chunk_index": i} for i in range(len(chunks))]
    collection.upsert(ids=ids, documents=chunks, metadatas=metadatas)


def search_similar_items(query: str, n_results: int = 5) -> list[dict]:
    """
    Search for items similar to the query.
    Returns list of {id, document, metadata, distance} dicts.
    """
    collection = _get_collection("source_items")
    count = collection.count()
    if count == 0:
        return []
    n = min(n_results, count)
    results = collection.query(
        query_texts=[query],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    items = []
    for i, doc in enumerate(results["documents"][0]):
        items.append({
            "id": results["ids"][0][i],
            "document": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
            "similarity": 1 - results["distances"][0][i],
        })
    return items


def search_similar_articles(query: str, n_results: int = 5) -> list[dict]:
    """Search published articles for KB context injection."""
    collection = _get_collection("published_articles")
    count = collection.count()
    if count == 0:
        return []
    n = min(n_results, count)
    results = collection.query(
        query_texts=[query],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    items = []
    for i, doc in enumerate(results["documents"][0]):
        items.append({
            "id": results["ids"][0][i],
            "document": doc,
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
            "similarity": 1 - results["distances"][0][i],
        })
    return items


def get_item_count() -> int:
    return _get_collection("source_items").count()


def get_article_count() -> int:
    return _get_collection("published_articles").count()


def compute_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using the embedding model."""
    fn = _get_embed_fn()
    embeddings = fn([text_a, text_b])
    import numpy as np
    a, b = np.array(embeddings[0]), np.array(embeddings[1])
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
