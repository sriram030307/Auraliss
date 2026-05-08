"""
Auralis RAG Service
Retrieval-Augmented Generation pipeline:
  1. Embed the user query via sentence-transformers
  2. Retrieve top-K relevant chunks from ChromaDB
  3. Augment the LLM prompt with retrieved context
  4. Return both the augmented prompt and source citations
"""

from typing import List, Dict, Tuple, Optional
from app.core.config import settings
from app.core.logging import logger
from app.db.vector_store import vector_store


class RAGService:
    """Handles embedding queries and retrieving relevant knowledge chunks."""

    def __init__(self):
        self._embedding_model = None
        logger.info(f"RAG Service initialized | Embedding model: {settings.EMBEDDING_MODEL}")

    def _get_embedding_model(self):
        """Lazy-load the sentence-transformer embedding model."""
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                logger.info(f"Embedding model loaded: {settings.EMBEDDING_MODEL}")
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. Run: pip install sentence-transformers"
                )
        return self._embedding_model

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string into a vector."""
        model = self._get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts efficiently."""
        model = self._get_embedding_model()
        embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32, show_progress_bar=False)
        return [e.tolist() for e in embeddings]

    def retrieve(self, query: str, n_results: Optional[int] = None) -> List[Dict]:
        """
        Retrieve the top-K most relevant document chunks for a query.
        Returns a list of dicts with 'content', 'source', 'score'.
        """
        if n_results is None:
            n_results = settings.TOP_K_RESULTS

        # Check if knowledge base has any docs
        if vector_store.collection.count() == 0:
            logger.warning("Knowledge base is empty – RAG retrieval skipped")
            return []

        # Embed the query
        query_embedding = self.embed_text(query)

        # Query the vector store
        results = vector_store.query(
            query_embedding=query_embedding,
            n_results=min(n_results, vector_store.collection.count()),
        )

        # Parse results
        sources = []
        if results and results.get("documents") and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                similarity = 1.0 - dist  # Convert cosine distance → similarity
                sources.append({
                    "content": doc,
                    "source": meta.get("source", "Unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "similarity": round(similarity, 4),
                })

        # Filter out low-relevance results (threshold: 0.25)
        sources = [s for s in sources if s["similarity"] >= 0.25]

        logger.info(
            f"RAG retrieval | Query: '{query[:50]}...' | "
            f"Retrieved: {len(sources)} chunks"
        )
        return sources

    def build_augmented_prompt(
        self,
        user_query: str,
        retrieved_sources: List[Dict],
    ) -> str:
        """
        Build a RAG-augmented user message that includes retrieved context.
        """
        if not retrieved_sources:
            return user_query

        context_parts = []
        for i, src in enumerate(retrieved_sources, 1):
            context_parts.append(
                f"[Source {i}: {src['source']}]\n{src['content']}"
            )

        context_block = "\n\n".join(context_parts)

        augmented = (
            f"Use the following context from the knowledge base to answer the question. "
            f"If the context doesn't fully address the question, supplement with your own knowledge "
            f"and clearly indicate what comes from the provided context.\n\n"
            f"--- KNOWLEDGE BASE CONTEXT ---\n{context_block}\n"
            f"--- END CONTEXT ---\n\n"
            f"User Question: {user_query}"
        )
        return augmented

    async def retrieve_and_augment(
        self, query: str
    ) -> Tuple[str, List[Dict]]:
        """
        Full RAG pipeline: retrieve relevant docs and return augmented prompt + sources.
        Returns (augmented_prompt, sources_list).
        """
        import asyncio
        loop = asyncio.get_event_loop()

        # Run retrieval in executor (CPU-bound embedding)
        sources = await loop.run_in_executor(None, self.retrieve, query)
        augmented_prompt = self.build_augmented_prompt(query, sources)

        return augmented_prompt, sources


# Singleton instance
rag_service = RAGService()
