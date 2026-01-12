"""
Knowledge Database Service Module

This module manages the knowledge.db SQLite database for storing:
- Concepts (nodes in the knowledge graph)
- Relationships (edges between concepts)
- Flashcards (for spaced repetition learning)
- Extraction progress (tracking which sections have been processed)

This database is separate from reading_progress.db because:
1. Knowledge data can grow significantly larger
2. It's derived data that can be regenerated from source books
3. Different backup strategies may apply
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class KnowledgeDatabase:
    """
    Database service for knowledge graph storage.

    Manages concepts, relationships, flashcards, and extraction progress
    in a separate SQLite database from the main reading progress database.
    """

    def __init__(self, db_path: str = "data/knowledge.db"):
        """
        Initialize the knowledge database service.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._ensure_data_dir()
        self._init_database()

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists for the database file."""
        data_dir = os.path.dirname(self.db_path)
        if data_dir:
            os.makedirs(data_dir, exist_ok=True)

    def _init_database(self) -> None:
        """Initialize the database with required tables and indexes."""
        with sqlite3.connect(self.db_path) as conn:
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            # Create concepts table (nodes in the knowledge graph)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    book_type TEXT NOT NULL CHECK (book_type IN ('epub', 'pdf')),
                    nav_id TEXT,
                    page_num INTEGER,
                    name TEXT NOT NULL,
                    definition TEXT,
                    source_quote TEXT,
                    importance INTEGER DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(book_id, book_type, name)
                )
            """)

            # Create relationships table (edges between concepts)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                    target_concept_id INTEGER NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
                    relationship_type TEXT NOT NULL,
                    description TEXT,
                    weight REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source_concept_id, target_concept_id, relationship_type)
                )
            """)

            # Create flashcards table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_id INTEGER REFERENCES concepts(id) ON DELETE CASCADE,
                    relationship_id INTEGER REFERENCES relationships(id) ON DELETE CASCADE,
                    card_type TEXT NOT NULL CHECK (card_type IN ('qa', 'cloze', 'connection')),
                    front TEXT NOT NULL,
                    back TEXT NOT NULL,
                    source_text TEXT,
                    next_review TIMESTAMP,
                    interval_days INTEGER DEFAULT 1,
                    ease_factor REAL DEFAULT 2.5,
                    review_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create extraction progress tracking table (section-level)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extraction_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    book_type TEXT NOT NULL CHECK (book_type IN ('epub', 'pdf')),
                    nav_id TEXT,
                    page_num INTEGER,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(book_id, book_type, nav_id, page_num)
                )
            """)

            # Create chunk progress tracking table (for resumable extraction)
            # CHECK constraint enforces XOR: exactly one of nav_id or page_num must be set
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunk_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    book_type TEXT NOT NULL CHECK (book_type IN ('epub', 'pdf')),
                    nav_id TEXT,
                    page_num INTEGER,
                    chunk_index INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(book_id, book_type, nav_id, page_num, chunk_index),
                    CHECK ((nav_id IS NOT NULL AND page_num IS NULL) OR (nav_id IS NULL AND page_num IS NOT NULL))
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_concepts_book
                ON concepts(book_id, book_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_concepts_nav
                ON concepts(book_id, nav_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_concepts_name
                ON concepts(name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_source
                ON relationships(source_concept_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_relationships_target
                ON relationships(target_concept_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_flashcards_due
                ON flashcards(next_review)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_flashcards_concept
                ON flashcards(concept_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_extraction_book
                ON extraction_progress(book_id, book_type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunk_progress_section
                ON chunk_progress(book_id, book_type, nav_id, page_num)
            """)

            conn.commit()
            logger.info(f"Knowledge database initialized at {self.db_path}")

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with foreign keys enabled."""
        conn = sqlite3.connect(self.db_path)
        # Enable foreign key constraints (required for CASCADE deletes to work)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # ========================================
    # CONCEPT CRUD OPERATIONS
    # ========================================

    def create_concept(
        self,
        book_id: int,
        book_type: str,
        name: str,
        definition: str | None = None,
        source_quote: str | None = None,
        importance: int = 3,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> int | None:
        """
        Create a new concept in the knowledge graph.

        Args:
            book_id: ID of the book this concept belongs to
            book_type: Type of book ('epub' or 'pdf')
            name: Canonical name of the concept
            definition: 1-2 sentence explanation
            source_quote: Exact text where concept was found
            importance: 1-5 scale (5 = core concept)
            nav_id: Navigation section ID (for EPUBs)
            page_num: Page number (for PDFs)

        Returns:
            ID of the created concept, or None if creation failed
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO concepts
                    (book_id, book_type, name, definition, source_quote, importance, nav_id, page_num)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        book_type,
                        name,
                        definition,
                        source_quote,
                        importance,
                        nav_id,
                        page_num,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            logger.warning(f"Concept already exists: {name} for book {book_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating concept: {e}")
            return None

    def get_concept_by_id(self, concept_id: int) -> dict[str, Any] | None:
        """Get a concept by its ID."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM concepts WHERE id = ?",
                    (concept_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting concept {concept_id}: {e}")
            return None

    def get_concept_by_name(
        self, book_id: int, book_type: str, name: str
    ) -> dict[str, Any] | None:
        """Get a concept by its name within a specific book."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM concepts WHERE book_id = ? AND book_type = ? AND name = ?",
                    (book_id, book_type, name),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting concept by name: {e}")
            return None

    def get_concepts_for_book(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
        importance_min: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get concepts for a book, optionally filtered by section/page and importance.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Filter by navigation section (for EPUBs)
            page_num: Filter by page number (for PDFs)
            importance_min: Minimum importance level to include

        Returns:
            List of concept dictionaries
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row

                query = "SELECT * FROM concepts WHERE book_id = ? AND book_type = ?"
                params: list[Any] = [book_id, book_type]

                if nav_id is not None:
                    query += " AND nav_id = ?"
                    params.append(nav_id)

                if page_num is not None:
                    query += " AND page_num = ?"
                    params.append(page_num)

                if importance_min is not None:
                    query += " AND importance >= ?"
                    params.append(importance_min)

                query += " ORDER BY importance DESC, created_at DESC"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting concepts for book {book_id}: {e}")
            return []

    def search_concepts(
        self,
        query: str,
        book_id: int | None = None,
        book_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Search concepts by name or definition text.

        Uses LIKE queries for text matching with relevance ordering:
        - Exact name match (highest priority)
        - Name starts with query
        - Name contains query
        - Definition contains query (lowest priority)

        Args:
            query: Search query (searches name and definition)
            book_id: Filter by book (optional)
            book_type: Filter by book type (optional)
            limit: Maximum results

        Returns:
            List of matching concepts, ordered by relevance
        """
        if not query or not query.strip():
            return []

        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Escape special LIKE characters
                escaped_query = (
                    query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                )

                # Build base query with relevance scoring
                # Using CASE to order by: exact match > starts with > contains name > contains definition
                sql = """
                    SELECT *,
                        CASE
                            WHEN LOWER(name) = LOWER(?) THEN 1
                            WHEN LOWER(name) LIKE LOWER(?) ESCAPE '\\' THEN 2
                            WHEN LOWER(name) LIKE LOWER(?) ESCAPE '\\' THEN 3
                            WHEN LOWER(definition) LIKE LOWER(?) ESCAPE '\\' THEN 4
                            ELSE 5
                        END as relevance
                    FROM concepts
                    WHERE (
                        LOWER(name) LIKE LOWER(?) ESCAPE '\\'
                        OR LOWER(definition) LIKE LOWER(?) ESCAPE '\\'
                    )
                """
                params: list[Any] = [
                    query,  # exact match
                    f"{escaped_query}%",  # starts with
                    f"%{escaped_query}%",  # contains (name)
                    f"%{escaped_query}%",  # contains (definition)
                    f"%{escaped_query}%",  # WHERE clause (name)
                    f"%{escaped_query}%",  # WHERE clause (definition)
                ]

                if book_id is not None:
                    sql += " AND book_id = ?"
                    params.append(book_id)

                if book_type is not None:
                    sql += " AND book_type = ?"
                    params.append(book_type)

                sql += (
                    " ORDER BY relevance ASC, importance DESC, created_at DESC LIMIT ?"
                )
                params.append(limit)

                cursor = conn.execute(sql, params)
                results = [dict(row) for row in cursor.fetchall()]

                # Remove the relevance column from results
                for r in results:
                    r.pop("relevance", None)

                return results
        except Exception as e:
            logger.error(f"Error searching concepts: {e}")
            return []

    def update_concept(
        self,
        concept_id: int,
        definition: str | None = None,
        source_quote: str | None = None,
        importance: int | None = None,
    ) -> bool:
        """Update a concept's fields."""
        try:
            updates = []
            params: list[Any] = []

            if definition is not None:
                updates.append("definition = ?")
                params.append(definition)
            if source_quote is not None:
                updates.append("source_quote = ?")
                params.append(source_quote)
            if importance is not None:
                updates.append("importance = ?")
                params.append(importance)

            if not updates:
                return True

            params.append(concept_id)

            with self.get_connection() as conn:
                cursor = conn.execute(
                    f"UPDATE concepts SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating concept {concept_id}: {e}")
            return False

    def delete_concept(self, concept_id: int) -> bool:
        """Delete a concept and its related relationships."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM concepts WHERE id = ?",
                    (concept_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting concept {concept_id}: {e}")
            return False

    # ========================================
    # RELATIONSHIP CRUD OPERATIONS
    # ========================================

    def create_relationship(
        self,
        source_concept_id: int,
        target_concept_id: int,
        relationship_type: str,
        description: str | None = None,
        weight: float = 1.0,
    ) -> int | None:
        """
        Create a relationship between two concepts.

        If a relationship with the same source, target, and type already exists,
        the weight is accumulated (added) to represent stronger connections from
        multiple mentions. This operation is atomic using SQLite's ON CONFLICT
        clause to prevent race conditions.

        Args:
            source_concept_id: ID of the source concept
            target_concept_id: ID of the target concept
            relationship_type: Type of relationship (explains, contrasts, etc.)
            description: Explanation of the relationship
            weight: Strength to add to the connection (accumulates on duplicates)

        Returns:
            ID of the created/existing relationship, or None if creation failed
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                # Use ON CONFLICT to atomically insert or update weight
                # This prevents race conditions between concurrent writers
                conn.execute(
                    """
                    INSERT INTO relationships
                    (source_concept_id, target_concept_id, relationship_type, description, weight)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_concept_id, target_concept_id, relationship_type)
                    DO UPDATE SET weight = weight + excluded.weight
                    """,
                    (
                        source_concept_id,
                        target_concept_id,
                        relationship_type,
                        description,
                        weight,
                    ),
                )
                conn.commit()

                # Get the ID of the inserted/updated row
                cursor = conn.execute(
                    """
                    SELECT id FROM relationships
                    WHERE source_concept_id = ? AND target_concept_id = ? AND relationship_type = ?
                    """,
                    (source_concept_id, target_concept_id, relationship_type),
                )
                row = cursor.fetchone()
                return row["id"] if row else None
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return None

    def get_relationships_for_concept(
        self, concept_id: int, as_source: bool = True, as_target: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get relationships involving a concept.

        Args:
            concept_id: ID of the concept
            as_source: Include relationships where concept is the source
            as_target: Include relationships where concept is the target

        Returns:
            List of relationship dictionaries with joined concept info
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                results = []

                if as_source:
                    cursor = conn.execute(
                        """
                        SELECT r.*, c.name as target_name, c.definition as target_definition
                        FROM relationships r
                        JOIN concepts c ON r.target_concept_id = c.id
                        WHERE r.source_concept_id = ?
                        ORDER BY r.weight DESC
                        """,
                        (concept_id,),
                    )
                    results.extend([dict(row) for row in cursor.fetchall()])

                if as_target:
                    cursor = conn.execute(
                        """
                        SELECT r.*, c.name as source_name, c.definition as source_definition
                        FROM relationships r
                        JOIN concepts c ON r.source_concept_id = c.id
                        WHERE r.target_concept_id = ?
                        ORDER BY r.weight DESC
                        """,
                        (concept_id,),
                    )
                    results.extend([dict(row) for row in cursor.fetchall()])

                return results
        except Exception as e:
            logger.error(f"Error getting relationships for concept {concept_id}: {e}")
            return []

    def get_relationship_by_id(self, relationship_id: int) -> dict[str, Any] | None:
        """Get a relationship by its ID with joined concept info."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT r.*,
                           sc.name as source_name, sc.definition as source_definition,
                           tc.name as target_name, tc.definition as target_definition
                    FROM relationships r
                    JOIN concepts sc ON r.source_concept_id = sc.id
                    JOIN concepts tc ON r.target_concept_id = tc.id
                    WHERE r.id = ?
                    """,
                    (relationship_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting relationship {relationship_id}: {e}")
            return None

    def update_relationship(
        self,
        relationship_id: int,
        relationship_type: str | None = None,
        description: str | None = None,
        weight: float | None = None,
    ) -> bool:
        """Update a relationship's fields."""
        try:
            updates = []
            params: list[Any] = []

            if relationship_type is not None:
                updates.append("relationship_type = ?")
                params.append(relationship_type)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if weight is not None:
                updates.append("weight = ?")
                params.append(weight)

            if not updates:
                return True

            params.append(relationship_id)

            with self.get_connection() as conn:
                cursor = conn.execute(
                    f"UPDATE relationships SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating relationship {relationship_id}: {e}")
            return False

    def delete_relationship(self, relationship_id: int) -> bool:
        """Delete a relationship."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM relationships WHERE id = ?",
                    (relationship_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting relationship {relationship_id}: {e}")
            return False

    def get_graph_for_book(self, book_id: int, book_type: str) -> dict[str, Any]:
        """
        Get full graph data for a book (nodes and edges).

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')

        Returns:
            Dictionary with 'nodes' and 'edges' lists for visualization
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Get all concepts (nodes)
                cursor = conn.execute(
                    """
                    SELECT id, name, definition, importance, nav_id, page_num
                    FROM concepts
                    WHERE book_id = ? AND book_type = ?
                    ORDER BY importance DESC
                    """,
                    (book_id, book_type),
                )
                nodes = [dict(row) for row in cursor.fetchall()]

                # Get node IDs for filtering edges
                node_ids = {n["id"] for n in nodes}

                if not node_ids:
                    return {"nodes": [], "edges": []}

                # Get all relationships (edges) between these concepts
                placeholders = ",".join("?" * len(node_ids))
                cursor = conn.execute(
                    f"""
                    SELECT id, source_concept_id as source, target_concept_id as target,
                           relationship_type as type, description, weight
                    FROM relationships
                    WHERE source_concept_id IN ({placeholders})
                      AND target_concept_id IN ({placeholders})
                    ORDER BY weight DESC
                    """,
                    list(node_ids) + list(node_ids),
                )
                edges = [dict(row) for row in cursor.fetchall()]

                return {"nodes": nodes, "edges": edges}
        except Exception as e:
            logger.error(f"Error getting graph for book {book_id}: {e}")
            return {"nodes": [], "edges": []}

    # ========================================
    # EXTRACTION PROGRESS TRACKING
    # ========================================

    def mark_section_extracted(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> bool:
        """Mark a section/page as having been extracted.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            True if the section was marked as extracted, False on error.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO extraction_progress
                    (book_id, book_type, nav_id, page_num, extracted_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (book_id, book_type, nav_id, page_num, datetime.now().isoformat()),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking section extracted: {e}")
            return False

    def is_section_extracted(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> bool:
        """Check if a section/page has been extracted.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            True if the section has been extracted, False otherwise.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                if nav_id is not None:
                    cursor = conn.execute(
                        """
                        SELECT 1 FROM extraction_progress
                        WHERE book_id = ? AND book_type = ? AND nav_id = ?
                        """,
                        (book_id, book_type, nav_id),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT 1 FROM extraction_progress
                        WHERE book_id = ? AND book_type = ? AND page_num = ?
                        """,
                        (book_id, book_type, page_num),
                    )

                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Error checking extraction status: {e}")
            return False

    def get_extraction_progress(
        self, book_id: int, book_type: str
    ) -> list[dict[str, Any]]:
        """Get all extracted sections for a book."""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM extraction_progress
                    WHERE book_id = ? AND book_type = ?
                    ORDER BY extracted_at DESC
                    """,
                    (book_id, book_type),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting extraction progress: {e}")
            return []

    # ========================================
    # CHUNK PROGRESS TRACKING (for resumable extraction)
    # ========================================

    def mark_chunk_extracted(
        self,
        book_id: int,
        book_type: str,
        chunk_index: int,
        total_chunks: int,
        content_hash: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> bool:
        """Mark a chunk as having been extracted.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            chunk_index: Index of the chunk (0-based)
            total_chunks: Total number of chunks in the section
            content_hash: Hash of the content to detect changes
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            True if the chunk was marked as extracted, False on error.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chunk_progress
                    (book_id, book_type, nav_id, page_num, chunk_index, total_chunks, content_hash, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        book_id,
                        book_type,
                        nav_id,
                        page_num,
                        chunk_index,
                        total_chunks,
                        content_hash,
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking chunk extracted: {e}")
            return False

    def get_extracted_chunks(
        self,
        book_id: int,
        book_type: str,
        content_hash: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> set[int]:
        """Get the set of chunk indices that have been extracted for a section.

        Only returns chunks that match the current content_hash (to detect
        when content has changed and extraction needs to restart).

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            content_hash: Hash of the current content
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            Set of chunk indices that have been extracted.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                if nav_id is not None:
                    cursor = conn.execute(
                        """
                        SELECT chunk_index FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND nav_id = ? AND content_hash = ?
                        """,
                        (book_id, book_type, nav_id, content_hash),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT chunk_index FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND page_num = ? AND content_hash = ?
                        """,
                        (book_id, book_type, page_num, content_hash),
                    )

                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Error getting extracted chunks: {e}")
            return set()

    def get_chunk_progress_info(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> dict[str, Any] | None:
        """Get chunk progress info for a section.

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            Dictionary with 'extracted_chunks', 'total_chunks', 'content_hash',
            or None if no progress exists.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                if nav_id is not None:
                    cursor = conn.execute(
                        """
                        SELECT chunk_index, total_chunks, content_hash
                        FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND nav_id = ?
                        ORDER BY chunk_index
                        """,
                        (book_id, book_type, nav_id),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT chunk_index, total_chunks, content_hash
                        FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND page_num = ?
                        ORDER BY chunk_index
                        """,
                        (book_id, book_type, page_num),
                    )

                rows = cursor.fetchall()
                if not rows:
                    return None

                return {
                    "extracted_chunks": [row["chunk_index"] for row in rows],
                    "total_chunks": rows[0]["total_chunks"],
                    "content_hash": rows[0]["content_hash"],
                }
        except Exception as e:
            logger.error(f"Error getting chunk progress info: {e}")
            return None

    def clear_chunk_progress(
        self,
        book_id: int,
        book_type: str,
        nav_id: str | None = None,
        page_num: int | None = None,
    ) -> bool:
        """Clear chunk progress for a section (e.g., when content changes or force re-extract).

        Args:
            book_id: ID of the book
            book_type: Type of book ('epub' or 'pdf')
            nav_id: Navigation ID for EPUB sections (mutually exclusive with page_num)
            page_num: Page number for PDFs (mutually exclusive with nav_id)

        Returns:
            True if cleared successfully, False on error.

        Raises:
            ValueError: If neither or both nav_id and page_num are provided.
        """
        # Validate that exactly one of nav_id or page_num is provided
        if (nav_id is None) == (page_num is None):
            raise ValueError("Exactly one of nav_id or page_num must be provided")

        try:
            with self.get_connection() as conn:
                if nav_id is not None:
                    conn.execute(
                        """
                        DELETE FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND nav_id = ?
                        """,
                        (book_id, book_type, nav_id),
                    )
                else:
                    conn.execute(
                        """
                        DELETE FROM chunk_progress
                        WHERE book_id = ? AND book_type = ? AND page_num = ?
                        """,
                        (book_id, book_type, page_num),
                    )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error clearing chunk progress: {e}")
            return False

    # ========================================
    # FLASHCARD OPERATIONS (basic for Phase 1)
    # ========================================

    def create_flashcard(
        self,
        card_type: str,
        front: str,
        back: str,
        concept_id: int | None = None,
        relationship_id: int | None = None,
        source_text: str | None = None,
    ) -> int | None:
        """Create a new flashcard.

        Args:
            card_type: Type of flashcard (e.g., 'qa', 'cloze', 'connection')
            front: Front text of the flashcard
            back: Back text of the flashcard
            concept_id: ID of the associated concept (mutually exclusive with relationship_id)
            relationship_id: ID of the associated relationship (mutually exclusive with concept_id)
            source_text: Optional source text for the flashcard

        Returns:
            The ID of the created flashcard, or None if creation failed.

        Raises:
            ValueError: If neither or both concept_id and relationship_id are provided.
        """
        # Validate that exactly one of concept_id or relationship_id is provided
        if (concept_id is None) == (relationship_id is None):
            raise ValueError(
                "Exactly one of concept_id or relationship_id must be provided"
            )

        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO flashcards
                    (concept_id, relationship_id, card_type, front, back, source_text, next_review)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        concept_id,
                        relationship_id,
                        card_type,
                        front,
                        back,
                        source_text,
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating flashcard: {e}")
            return None

    def get_flashcards_due(
        self, book_id: int | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get flashcards that are due for review.

        Handles both concept-based flashcards (qa, cloze) and relationship-based
        flashcards (connection). For relationship-based cards, book_id is derived
        from the relationship's source concept.
        """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                now = datetime.now().isoformat()

                # Join to concepts directly (for qa/cloze cards) and through
                # relationships (for connection cards) to properly determine book_id
                base_query = """
                    SELECT f.*,
                           COALESCE(c.book_id, rc.book_id) as book_id,
                           COALESCE(c.name, rc.name) as concept_name
                    FROM flashcards f
                    LEFT JOIN concepts c ON f.concept_id = c.id
                    LEFT JOIN relationships r ON f.relationship_id = r.id
                    LEFT JOIN concepts rc ON r.source_concept_id = rc.id
                    WHERE f.next_review <= ?
                """

                if book_id is not None:
                    cursor = conn.execute(
                        base_query
                        + """
                        AND COALESCE(c.book_id, rc.book_id) = ?
                        ORDER BY f.next_review ASC
                        LIMIT ?
                        """,
                        (now, book_id, limit),
                    )
                else:
                    cursor = conn.execute(
                        base_query
                        + """
                        ORDER BY f.next_review ASC
                        LIMIT ?
                        """,
                        (now, limit),
                    )

                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting due flashcards: {e}")
            return []

    # ========================================
    # UTILITY METHODS
    # ========================================

    def get_stats(self) -> dict[str, int]:
        """Get statistics about the knowledge database."""
        try:
            with self.get_connection() as conn:
                stats = {}

                cursor = conn.execute("SELECT COUNT(*) FROM concepts")
                stats["total_concepts"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM relationships")
                stats["total_relationships"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM flashcards")
                stats["total_flashcards"] = cursor.fetchone()[0]

                cursor = conn.execute("SELECT COUNT(*) FROM extraction_progress")
                stats["sections_extracted"] = cursor.fetchone()[0]

                return stats
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def delete_book_knowledge(self, book_id: int, book_type: str) -> bool:
        """Delete all knowledge data for a specific book."""
        try:
            with self.get_connection() as conn:
                # Delete flashcards for concepts in this book
                conn.execute(
                    """
                    DELETE FROM flashcards
                    WHERE concept_id IN (
                        SELECT id FROM concepts WHERE book_id = ? AND book_type = ?
                    )
                    """,
                    (book_id, book_type),
                )

                # Delete relationships involving concepts in this book
                conn.execute(
                    """
                    DELETE FROM relationships
                    WHERE source_concept_id IN (
                        SELECT id FROM concepts WHERE book_id = ? AND book_type = ?
                    ) OR target_concept_id IN (
                        SELECT id FROM concepts WHERE book_id = ? AND book_type = ?
                    )
                    """,
                    (book_id, book_type, book_id, book_type),
                )

                # Delete concepts
                conn.execute(
                    "DELETE FROM concepts WHERE book_id = ? AND book_type = ?",
                    (book_id, book_type),
                )

                # Delete extraction progress
                conn.execute(
                    "DELETE FROM extraction_progress WHERE book_id = ? AND book_type = ?",
                    (book_id, book_type),
                )

                # Delete chunk progress
                conn.execute(
                    "DELETE FROM chunk_progress WHERE book_id = ? AND book_type = ?",
                    (book_id, book_type),
                )

                conn.commit()
                logger.info(
                    f"Deleted all knowledge data for book {book_id} ({book_type})"
                )
                return True
        except Exception as e:
            logger.error(f"Error deleting book knowledge: {e}")
            return False


# Global instance
knowledge_db = KnowledgeDatabase()
