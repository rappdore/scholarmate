import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import ebooklib
from ebooklib import epub

from app.models.epub_metadata import EPUBBasicMetadata, EPUBExtendedMetadata

from .epub_documents_service import EPUBDocumentsService

logger = logging.getLogger(__name__)


class EPUBCache:
    """
    In-memory cache for EPUB metadata with database backing.

    Caches:
    - Basic metadata (title, author, chapters, sizes, dates) - loaded on initialization
    - Thumbnail paths (pre-generated) - loaded on initialization
    - Extended metadata (subject, publisher, language) - lazy-loaded on first request

    Database backing ensures cache persists between service restarts.
    """

    def __init__(
        self,
        epub_dir: Path,
        thumbnails_dir: Path,
        epub_service: Any,
        db_path: str = "data/reading_progress.db",
    ):
        """
        Initialize the EPUB cache.

        Args:
            epub_dir: Directory containing EPUB files
            thumbnails_dir: Directory for thumbnail storage
            epub_service: Reference to EPUBService for thumbnail generation
            db_path: Path to SQLite database for persistent storage
        """
        self.epub_dir = epub_dir
        self.thumbnails_dir = thumbnails_dir
        self.epub_service = epub_service

        # Database service for persistence
        self._db_service = EPUBDocumentsService(db_path)

        # Cache storage: dict[filename, EPUBBasicMetadata | EPUBExtendedMetadata]
        self._cache: dict[str, EPUBBasicMetadata | EPUBExtendedMetadata] = {}

        # Cache metadata
        self._cache_built_at: str | None = None
        self._cache_epub_count: int = 0

        # Build cache on initialization
        logger.info("Initializing EPUB cache with database backing...")
        self._build_cache()
        logger.info(f"EPUB cache initialized with {self._cache_epub_count} EPUBs")

    def _extract_metadata_values(self, book, namespace: str, field: str) -> str:
        """
        Extract metadata values and handle multiple entries gracefully
        """
        try:
            metadata_list = book.get_metadata(namespace, field)
            if not metadata_list:
                return ""

            # Extract values from tuples and filter out empty ones
            values = []
            for item in metadata_list:
                if isinstance(item, tuple) and len(item) > 0:
                    value = str(item[0]).strip()
                    if value:
                        values.append(value)
                elif isinstance(item, str):
                    value = item.strip()
                    if value:
                        values.append(value)

            # Join multiple values appropriately
            if field == "creator":  # Authors
                return "; ".join(values) if values else "Unknown"
            elif field == "subject":  # Categories/tags
                return ", ".join(values) if values else ""
            else:  # Other fields like publisher, language - usually single value
                return values[0] if values else ""

        except Exception:
            return ""

    def _build_cache(self) -> None:
        """
        Build the cache by scanning filesystem and loading from database when possible.
        Only extracts metadata and generates thumbnails for new EPUBs not in database.

        Leverages database backing for fast cache initialization.
        """
        start_time = datetime.now()
        self._cache = {}

        logger.info(f"Scanning EPUB directory: {self.epub_dir}")

        epub_files = list(self.epub_dir.glob("*.epub"))
        logger.info(f"Found {len(epub_files)} EPUB files")

        db_hits = 0
        db_misses = 0

        for file_path in epub_files:
            filename = file_path.name

            # Check if EPUB exists in database
            db_record = self._db_service.get_by_filename(filename)

            if db_record:
                # Load from database (fast path)
                logger.debug(f"Loading from database: {filename}")

                # Get thumbnail path from database
                thumbnail_path_str = db_record.get("thumbnail_path", "")

                # Only generate thumbnail if DB has no path or file doesn't exist
                if not thumbnail_path_str or not Path(thumbnail_path_str).exists():
                    try:
                        thumbnail_path = self.epub_service.generate_thumbnail(filename)
                        thumbnail_path_str = str(thumbnail_path)

                        # Update database with new thumbnail path
                        try:
                            self._db_service.create_or_update(
                                filename=filename,
                                chapters=db_record.get("chapters", 0),
                                title=db_record.get("title"),
                                author=db_record.get("author"),
                                file_size=db_record.get("file_size"),
                                file_path=db_record.get("file_path"),
                                thumbnail_path=thumbnail_path_str,
                                created_date=db_record.get("created_date"),
                                modified_date=db_record.get("modified_date"),
                            )
                        except Exception as db_error:
                            logger.warning(
                                f"Failed to update thumbnail path in database for {filename}: {db_error}"
                            )
                    except Exception as thumb_error:
                        logger.warning(
                            f"Failed to generate thumbnail for {filename}: {thumb_error}"
                        )
                        thumbnail_path_str = ""

                epub_info = EPUBBasicMetadata(
                    filename=filename,
                    type="epub",
                    title=db_record.get("title", file_path.stem),
                    author=db_record.get("author", "Unknown"),
                    chapters=db_record.get("chapters", 0),
                    file_size=db_record.get("file_size", 0),
                    modified_date=db_record.get("modified_date", ""),
                    created_date=db_record.get("created_date", ""),
                    thumbnail_path=thumbnail_path_str,
                    error=None,
                )
                self._cache[filename] = epub_info
                db_hits += 1

            else:
                # Not in database - extract from file (slow path)
                logger.debug(f"Extracting metadata from file: {filename}")
                try:
                    # Get file stats
                    stat = file_path.stat()

                    # Extract basic metadata
                    book = epub.read_epub(str(file_path))

                    # Extract metadata using robust method
                    title = self._extract_metadata_values(book, "DC", "title")
                    if not title:
                        title = file_path.stem

                    author = self._extract_metadata_values(book, "DC", "creator")

                    # Count chapters (spine items that are documents)
                    chapter_count = len(
                        [
                            item
                            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
                        ]
                    )

                    # Pre-generate thumbnail
                    try:
                        thumbnail_path = self.epub_service.generate_thumbnail(
                            file_path.name
                        )
                        thumbnail_path_str = str(thumbnail_path)
                    except Exception as thumb_error:
                        logger.warning(
                            f"Failed to generate thumbnail for {file_path.name}: {thumb_error}"
                        )
                        thumbnail_path_str = ""

                    # Store basic metadata in cache
                    epub_info = EPUBBasicMetadata(
                        filename=file_path.name,
                        type="epub",
                        title=str(title),
                        author=str(author) if author else "Unknown",
                        chapters=chapter_count,
                        file_size=stat.st_size,
                        modified_date=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        created_date=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        thumbnail_path=thumbnail_path_str,
                        error=None,
                    )

                    self._cache[file_path.name] = epub_info

                    # Persist to database
                    try:
                        self._db_service.create_or_update(
                            filename=file_path.name,
                            title=epub_info.title,
                            author=epub_info.author,
                            chapters=chapter_count,
                            file_size=stat.st_size,
                            file_path=str(file_path),
                            thumbnail_path=thumbnail_path_str,
                            created_date=epub_info.created_date,
                            modified_date=epub_info.modified_date,
                        )
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to persist EPUB metadata to database for {file_path.name}: {db_error}"
                        )

                    db_misses += 1

                except Exception as e:
                    # If we can't read an EPUB, still include it but with limited info
                    logger.error(f"Error processing {file_path.name}: {e}")
                    stat = file_path.stat()
                    epub_info = EPUBBasicMetadata(
                        filename=file_path.name,
                        type="epub",
                        title=file_path.stem,
                        author="Unknown",
                        chapters=0,
                        file_size=stat.st_size,
                        modified_date=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        created_date=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        thumbnail_path="",
                        error=f"Could not read EPUB: {str(e)}",
                    )
                    self._cache[file_path.name] = epub_info
                    db_misses += 1

        # Update cache metadata
        self._cache_built_at = datetime.now().isoformat()
        self._cache_epub_count = len(self._cache)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Cache build completed in {elapsed_time:.2f}s - {self._cache_epub_count} EPUBs cached "
            f"(DB hits: {db_hits}, new: {db_misses})"
        )

    def get_all_epubs(self) -> list[EPUBBasicMetadata]:
        """
        Get all EPUBs with basic metadata from cache.

        Returns:
            List of EPUBBasicMetadata objects, sorted by modified_date (newest first)
        """
        # Convert cache dict to list
        epubs = list(self._cache.values())

        # Sort by modified date (newest first)
        epubs.sort(key=lambda x: x.modified_date, reverse=True)

        return epubs

    def get_epub_info(self, filename: str) -> EPUBExtendedMetadata:
        """
        Get detailed EPUB info with lazy-loaded extended metadata.

        First call: Reads extended metadata from filesystem and caches it
        Subsequent calls: Returns cached data

        Args:
            filename: Name of the EPUB file

        Returns:
            EPUBExtendedMetadata object with full EPUB metadata

        Raises:
            FileNotFoundError: If EPUB not found in cache
        """
        # Check if EPUB exists in cache
        if filename not in self._cache:
            raise FileNotFoundError(f"EPUB {filename} not found in cache")

        epub_info = self._cache[filename]

        # Check if extended metadata is already loaded by checking the type
        if isinstance(epub_info, EPUBExtendedMetadata):
            # Already has extended metadata, return it
            return epub_info

        # Need to lazy-load extended metadata
        logger.debug(f"Lazy-loading extended metadata for: {filename}")
        try:
            file_path = self.epub_dir / filename

            if not file_path.exists():
                raise FileNotFoundError(f"EPUB {filename} not found on filesystem")

            book = epub.read_epub(str(file_path))

            # Extract extended metadata
            extended_info = EPUBExtendedMetadata(
                **epub_info.model_dump(),
                subject=self._extract_metadata_values(book, "DC", "subject"),
                publisher=self._extract_metadata_values(book, "DC", "publisher"),
                language=self._extract_metadata_values(book, "DC", "language"),
            )

            # Update cache with extended metadata
            self._cache[filename] = extended_info

            logger.debug(f"Extended metadata cached for: {filename}")

            # Persist extended metadata to database
            try:
                self._db_service.create_or_update(
                    filename=filename,
                    chapters=extended_info.chapters,
                    title=extended_info.title,
                    author=extended_info.author,
                    subject=extended_info.subject,
                    publisher=extended_info.publisher,
                    language=extended_info.language,
                    file_size=extended_info.file_size,
                    file_path=str(file_path),
                    thumbnail_path=extended_info.thumbnail_path,
                    created_date=extended_info.created_date,
                    modified_date=extended_info.modified_date,
                )
            except Exception as db_error:
                logger.warning(
                    f"Failed to persist extended metadata to database for {filename}: {db_error}"
                )

            return extended_info

        except Exception as e:
            logger.error(f"Error loading extended metadata for {filename}: {e}")
            # Create extended metadata with empty values on error
            extended_info = EPUBExtendedMetadata(
                **epub_info.model_dump(),
                subject="",
                publisher="",
                language="",
            )
            # Update cache with extended metadata (even if empty)
            self._cache[filename] = extended_info
            return extended_info

    def get_thumbnail_path(self, filename: str) -> str:
        """
        Get cached thumbnail path for an EPUB.

        Args:
            filename: Name of the EPUB file

        Returns:
            Path to thumbnail (may be empty string if generation failed)

        Raises:
            FileNotFoundError: If EPUB not found in cache
        """
        if filename not in self._cache:
            raise FileNotFoundError(f"EPUB {filename} not found in cache")

        return self._cache[filename].thumbnail_path

    def refresh(self) -> None:
        """
        Refresh the cache by rebuilding from filesystem.
        Clears all cached data (including extended metadata) and regenerates.
        """
        logger.info("Refreshing EPUB cache...")
        self._build_cache()
        logger.info("EPUB cache refresh complete")

    def get_cache_info(self) -> dict[str, Any]:
        """
        Get metadata about the cache itself.

        Returns:
            Dictionary with cache metadata
        """
        return {
            "cache_built_at": self._cache_built_at,
            "epub_count": self._cache_epub_count,
            "cached_files": list(self._cache.keys()),
        }
