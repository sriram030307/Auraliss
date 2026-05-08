"""
Auralis Knowledge Service
Document ingestion pipeline: load → chunk → embed → store in ChromaDB.
"""

import os
import uuid
from typing import List, Dict, Tuple
from app.core.config import settings
from app.core.logging import logger
from app.db.vector_store import vector_store
from app.services.rag_service import rag_service


class KnowledgeService:
    """
    Handles loading documents, chunking them intelligently,
    embedding with sentence-transformers, and persisting to ChromaDB.
    """

    def chunk_text(self, text: str, source: str) -> List[Dict]:
        """
        Split text into overlapping chunks while respecting sentence boundaries.
        Returns a list of chunk dicts with content and metadata.
        """
        chunk_size = settings.CHUNK_SIZE
        overlap = settings.CHUNK_OVERLAP
        chunks = []

        # Split on double newlines first (paragraph-aware)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current_chunk = ""

        for para in paragraphs:
            # If adding this paragraph would exceed chunk_size, save current chunk
            if current_chunk and len(current_chunk) + len(para) + 2 > chunk_size:
                chunks.append(current_chunk.strip())
                # Start next chunk with overlap from previous
                overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip() if current_chunk else para

        # Add the final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If no paragraphs, fall back to character-level chunking
        if not chunks:
            start = 0
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunks.append(text[start:end])
                start += chunk_size - overlap

        # Format with metadata
        return [
            {
                "content": chunk,
                "source": os.path.basename(source),
                "chunk_index": idx,
                "doc_id": str(uuid.uuid4()),
            }
            for idx, chunk in enumerate(chunks)
            if chunk.strip()
        ]

    def load_text_file(self, file_path: str) -> str:
        """Load a plain text file and return its contents."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def ingest_file(self, file_path: str) -> Dict:
        """
        Ingest a single file: load → chunk → embed → store.
        Returns ingestion stats.
        """
        logger.info(f"Ingesting file: {file_path}")

        # Load
        text = self.load_text_file(file_path)
        if not text.strip():
            logger.warning(f"File is empty: {file_path}")
            return {"file": file_path, "chunks": 0}

        # Chunk
        chunks = self.chunk_text(text, file_path)
        logger.info(f"Created {len(chunks)} chunks from {os.path.basename(file_path)}")

        # Embed
        contents = [c["content"] for c in chunks]
        embeddings = rag_service.embed_texts(contents)

        # Store
        vector_store.add_documents(
            documents=contents,
            embeddings=embeddings,
            metadatas=[
                {"source": c["source"], "chunk_index": c["chunk_index"]}
                for c in chunks
            ],
            ids=[c["doc_id"] for c in chunks],
        )

        return {
            "file": os.path.basename(file_path),
            "chunks_created": len(chunks),
            "characters": len(text),
        }

    def ingest_directory(self, directory: str) -> List[Dict]:
        """
        Ingest all .txt files from a directory.
        Returns list of per-file ingestion results.
        """
        results = []
        if not os.path.exists(directory):
            logger.error(f"Knowledge base directory not found: {directory}")
            return results

        txt_files = [
            os.path.join(directory, f)
            for f in os.listdir(directory)
            if f.endswith(".txt")
        ]

        if not txt_files:
            logger.warning(f"No .txt files found in: {directory}")
            return results

        logger.info(f"Ingesting {len(txt_files)} files from {directory}")
        for file_path in txt_files:
            try:
                result = self.ingest_file(file_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Error ingesting {file_path}: {e}")
                results.append({"file": file_path, "error": str(e)})

        total_chunks = sum(r.get("chunks_created", 0) for r in results)
        logger.info(f"Ingestion complete | Files: {len(results)} | Total chunks: {total_chunks}")
        return results

    def get_status(self) -> Dict:
        """Return knowledge base status."""
        stats = vector_store.get_stats()
        return {
            "status": "ready",
            "collection_name": stats["collection_name"],
            "total_chunks": stats["total_documents"],
            "persist_directory": stats["persist_directory"],
        }


# Singleton instance
knowledge_service = KnowledgeService()
