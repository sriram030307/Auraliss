"""
Auralis Vector Store
ChromaDB persistent client for storing and retrieving document embeddings.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logging import logger
import os


class VectorStore:
    """Singleton wrapper around ChromaDB persistent client."""

    _instance = None
    _client = None
    _collection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        """Initialize the ChromaDB client and collection."""
        try:
            # Ensure persist directory exists
            os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR
            )

            self._collection = self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

            doc_count = self._collection.count()
            logger.info(
                f"ChromaDB initialized | Collection: {settings.CHROMA_COLLECTION_NAME} | "
                f"Documents: {doc_count} | Path: {settings.CHROMA_PERSIST_DIR}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise

    @property
    def collection(self):
        """Get the active ChromaDB collection."""
        if self._collection is None:
            self.initialize()
        return self._collection

    @property
    def client(self):
        """Get the ChromaDB client."""
        if self._client is None:
            self.initialize()
        return self._client

    def add_documents(
        self,
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        ids: list[str],
    ):
        """Add documents with embeddings to the collection."""
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Added {len(documents)} documents to vector store")

    def query(
        self,
        query_embedding: list[float],
        n_results: int = None,
    ) -> dict:
        """Query the vector store for similar documents."""
        if n_results is None:
            n_results = settings.TOP_K_RESULTS

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        return {
            "collection_name": settings.CHROMA_COLLECTION_NAME,
            "total_documents": self.collection.count(),
            "persist_directory": settings.CHROMA_PERSIST_DIR,
        }

    def reset(self):
        """Reset the collection (delete all documents)."""
        self._client.delete_collection(settings.CHROMA_COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Vector store reset – all documents deleted")


# Singleton instance
vector_store = VectorStore()
