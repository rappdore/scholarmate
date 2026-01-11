"""
Embedding Service Module

This module handles vector embeddings for concepts using ChromaDB and sentence-transformers.
It provides:
- Embedding generation for concept text
- Storage and retrieval of embeddings
- Similarity search for deduplication and related concept discovery
"""

import logging
import os
import threading
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Lock for thread-safe singleton initialization
_singleton_lock = threading.Lock()

# Default embedding model - good balance of quality and speed
DEFAULT_MODEL = "all-MiniLM-L6-v2"


class EmbeddingService:
    """
    Service for managing concept embeddings using ChromaDB.

    Handles embedding generation, storage, and similarity search
    for concept deduplication and related concept discovery.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "concept_embeddings",
        model_name: str = DEFAULT_MODEL,
    ):
        """
        Initialize the embedding service.

        Args:
            persist_directory: Directory for ChromaDB persistence.
                              If None, uses default path relative to backend root.
            collection_name: Name of the ChromaDB collection
            model_name: Sentence transformer model to use for embeddings
        """
        # Use absolute path computed from project root
        if persist_directory is None:
            # Default to data/chroma_data relative to backend directory
            backend_dir = Path(__file__).parent.parent.parent.parent
            persist_directory = str(backend_dir / "data" / "chroma_data")

        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.model_name = model_name

        # Ensure directory exists (atomic operation, handles race condition)
        os.makedirs(persist_directory, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )

        # Lazy-load the embedding model (thread-safe)
        self._model: SentenceTransformer | None = None
        self._model_lock = threading.Lock()

        logger.info(
            f"EmbeddingService initialized with model={model_name}, "
            f"persist_directory={persist_directory}"
        )

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load the sentence transformer model with thread-safe double-checked locking."""
        if self._model is None:
            with self._model_lock:
                # Double-check after acquiring lock
                if self._model is None:
                    logger.info(
                        f"Loading sentence transformer model: {self.model_name}"
                    )
                    self._model = SentenceTransformer(self.model_name)
                    logger.info("Model loaded successfully")
        return self._model

    def generate_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def generate_concept_text(self, name: str, definition: str | None = None) -> str:
        """
        Generate the text to embed for a concept.

        Combines name and definition for richer semantic representation.

        Args:
            name: Concept name
            definition: Concept definition (optional)

        Returns:
            Combined text for embedding
        """
        if definition:
            return f"{name}: {definition}"
        return name

    def store_concept_embedding(
        self,
        concept_id: int,
        name: str,
        definition: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Store an embedding for a concept.

        Args:
            concept_id: ID of the concept in the database
            name: Concept name
            definition: Concept definition
            metadata: Additional metadata to store (book_id, book_type, etc.)
        """
        text = self.generate_concept_text(name, definition)
        embedding = self.generate_embedding(text)

        # Prepare metadata (ChromaDB requires string/int/float/bool values)
        # Copy to avoid mutating caller-provided dict
        doc_metadata = dict(metadata) if metadata else {}
        doc_metadata["name"] = name
        if definition:
            doc_metadata["definition"] = definition[:500]  # Truncate for storage

        try:
            # Use upsert to handle updates
            self._collection.upsert(
                ids=[str(concept_id)],
                embeddings=[embedding],
                metadatas=[doc_metadata],
                documents=[text],
            )
            logger.debug(f"Stored embedding for concept {concept_id}: {name}")
        except Exception as e:
            logger.error(f"Error storing embedding for concept {concept_id}: {e}")
            raise

    def delete_concept_embedding(self, concept_id: int) -> None:
        """Delete the embedding for a concept."""
        try:
            self._collection.delete(ids=[str(concept_id)])
            logger.debug(f"Deleted embedding for concept {concept_id}")
        except Exception as e:
            logger.error(f"Error deleting embedding for concept {concept_id}: {e}")

    def find_similar(
        self,
        text: str,
        n_results: int = 5,
        book_id: int | None = None,
        book_type: str | None = None,
        threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find concepts similar to the given text.

        Args:
            text: Text to find similar concepts for
            n_results: Maximum number of results to return
            book_id: Filter by book ID (optional)
            book_type: Filter by book type (optional)
            threshold: Minimum similarity score (0-1, where 1 is identical)
                      Note: ChromaDB returns distances, so we convert to similarity

        Returns:
            List of dictionaries with concept_id, name, similarity score, etc.
        """
        embedding = self.generate_embedding(text)

        # Build filter if specified
        where_filter = None
        if book_id is not None or book_type is not None:
            conditions = []
            if book_id is not None:
                conditions.append({"book_id": book_id})
            if book_type is not None:
                conditions.append({"book_type": book_type})

            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}

        try:
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=where_filter,
                include=["metadatas", "distances", "documents"],
            )

            # Convert results to list of dicts
            similar_concepts = []
            if results["ids"] and results["ids"][0]:
                for i, concept_id in enumerate(results["ids"][0]):
                    # Convert distance to similarity (cosine distance to similarity)
                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance  # Cosine distance to similarity

                    # Apply threshold filter if specified
                    if threshold is not None and similarity < threshold:
                        continue

                    metadata = (
                        results["metadatas"][0][i] if results["metadatas"] else {}
                    )
                    similar_concepts.append(
                        {
                            "concept_id": int(concept_id),
                            "name": metadata.get("name", ""),
                            "definition": metadata.get("definition", ""),
                            "similarity": similarity,
                            "distance": distance,
                            "metadata": metadata,
                        }
                    )

            return similar_concepts
        except Exception as e:
            logger.error(f"Error finding similar concepts: {e}")
            return []

    def find_similar_to_concept(
        self,
        concept_id: int,
        n_results: int = 5,
        exclude_same_book: bool = False,
        book_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Find concepts similar to an existing concept.

        Args:
            concept_id: ID of the concept to find similar concepts for
            n_results: Maximum number of results to return
            exclude_same_book: Whether to exclude concepts from the same book
            book_id: The book ID of the source concept (needed if exclude_same_book=True)

        Returns:
            List of similar concepts (excluding the source concept)
        """
        try:
            # Get the embedding for the source concept
            result = self._collection.get(
                ids=[str(concept_id)],
                include=["embeddings", "metadatas"],
            )

            if not result["embeddings"] or not result["embeddings"][0]:
                logger.warning(f"No embedding found for concept {concept_id}")
                return []

            embedding = result["embeddings"][0]

            # Build filter to exclude same book if requested
            where_filter = None
            if exclude_same_book and book_id is not None:
                where_filter = {"book_id": {"$ne": book_id}}

            # Query for similar concepts
            results = self._collection.query(
                query_embeddings=[embedding],
                n_results=n_results + 1,  # +1 to account for the source concept
                where=where_filter,
                include=["metadatas", "distances"],
            )

            # Convert and filter results
            similar_concepts = []
            if results["ids"] and results["ids"][0]:
                for i, cid in enumerate(results["ids"][0]):
                    # Skip the source concept itself
                    if int(cid) == concept_id:
                        continue

                    distance = results["distances"][0][i] if results["distances"] else 0
                    similarity = 1 - distance

                    metadata = (
                        results["metadatas"][0][i] if results["metadatas"] else {}
                    )
                    similar_concepts.append(
                        {
                            "concept_id": int(cid),
                            "name": metadata.get("name", ""),
                            "similarity": similarity,
                            "metadata": metadata,
                        }
                    )

                    if len(similar_concepts) >= n_results:
                        break

            return similar_concepts
        except Exception as e:
            logger.error(f"Error finding similar concepts for {concept_id}: {e}")
            return []

    def check_duplicate(
        self,
        name: str,
        definition: str | None,
        book_id: int,
        book_type: str,
        similarity_threshold: float = 0.9,
    ) -> dict[str, Any] | None:
        """
        Check if a concept is a duplicate of an existing concept.

        Args:
            name: Concept name
            definition: Concept definition
            book_id: Book ID to search within
            book_type: Book type to search within
            similarity_threshold: Minimum similarity to consider as duplicate

        Returns:
            The existing concept info if duplicate found, None otherwise
        """
        text = self.generate_concept_text(name, definition)
        similar = self.find_similar(
            text=text,
            n_results=1,
            book_id=book_id,
            book_type=book_type,
            threshold=similarity_threshold,
        )

        if similar:
            return similar[0]
        return None

    def get_collection_count(self) -> int:
        """Get the total number of embeddings in the collection."""
        return self._collection.count()

    def delete_book_embeddings(self, book_id: int, book_type: str) -> int:
        """
        Delete all embeddings for a specific book.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')

        Returns:
            Number of embeddings deleted
        """
        try:
            # Get all concept IDs for this book
            results = self._collection.get(
                where={"$and": [{"book_id": book_id}, {"book_type": book_type}]},
                include=[],
            )

            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                logger.info(
                    f"Deleted {len(results['ids'])} embeddings for book {book_id} ({book_type})"
                )
                return len(results["ids"])
            return 0
        except Exception as e:
            logger.error(f"Error deleting book embeddings: {e}")
            return 0


# Global instance (lazy initialization with thread-safe double-checked locking)
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance (thread-safe)."""
    global _embedding_service
    if _embedding_service is None:
        with _singleton_lock:
            # Double-check after acquiring lock
            if _embedding_service is None:
                _embedding_service = EmbeddingService()
    return _embedding_service
