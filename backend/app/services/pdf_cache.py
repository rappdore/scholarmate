import logging
from datetime import datetime
from pathlib import Path

from PyPDF2 import PdfReader

from .pdf_documents_service import PDFDocumentsService

logger = logging.getLogger(__name__)


class PDFCache:
    """
    In-memory cache for PDF metadata with database backing.

    Caches:
    - Basic metadata (title, author, pages, sizes, dates) - loaded on initialization
    - Thumbnail paths (pre-generated) - loaded on initialization
    - Extended metadata (subject, creator, producer) - lazy-loaded on first request

    Database backing (Phase 1a):
    - All cache data is also persisted to the pdf_documents table
    - Ensures metadata survives service restarts
    """

    def __init__(
        self,
        pdf_dir: Path,
        thumbnails_dir: Path,
        pdf_service: object,
        db_path: str = "data/reading_progress.db",
    ) -> None:
        """
        Initialize the PDF cache with database backing.

        Args:
            pdf_dir: Directory containing PDF files
            thumbnails_dir: Directory for thumbnail storage
            pdf_service: Reference to PDFService for thumbnail generation
            db_path: Path to SQLite database file (default: "data/reading_progress.db")
        """
        self.pdf_dir = pdf_dir
        self.thumbnails_dir = thumbnails_dir
        self.pdf_service = pdf_service

        # Phase 1a: Database service for persistence
        self._db_service = PDFDocumentsService(db_path)

        # Cache storage: dict[filename, metadata_dict]
        self._cache: dict[str, dict[str, object]] = {}

        # Cache metadata
        self._cache_built_at: str | None = None
        self._cache_pdf_count: int = 0

        # Build cache on initialization
        logger.info("Initializing PDF cache with database backing...")
        self._build_cache()
        logger.info(f"PDF cache initialized with {self._cache_pdf_count} PDFs")

    def _build_cache(self) -> None:
        """
        Build the cache by scanning filesystem and loading from database when possible.
        Only extracts metadata and generates thumbnails for new PDFs not in database.

        Phase 1a: Leverages database backing for fast cache initialization.
        """
        start_time = datetime.now()
        self._cache = {}

        logger.info(f"Scanning PDF directory: {self.pdf_dir}")

        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        db_hits = 0
        db_misses = 0

        for file_path in pdf_files:
            filename = file_path.name

            # Check if PDF exists in database
            db_record = self._db_service.get_by_filename(filename)

            if db_record:
                # Load from database (fast path)
                logger.debug(f"Loading from database: {filename}")

                # Get thumbnail path from database
                thumbnail_path_str = db_record.get("thumbnail_path", "")

                # Only generate thumbnail if DB has no path or file doesn't exist
                if not thumbnail_path_str or not Path(thumbnail_path_str).exists():
                    try:
                        thumbnail_path = self.pdf_service.generate_thumbnail(filename)
                        thumbnail_path_str = str(thumbnail_path)

                        # Update database with new thumbnail path
                        try:
                            self._db_service.create_or_update(
                                filename=filename,
                                num_pages=db_record.get("num_pages", 0),
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

                pdf_info = {
                    "filename": filename,
                    "type": "pdf",
                    "title": db_record.get("title", file_path.stem),
                    "author": db_record.get("author", "Unknown"),
                    "num_pages": db_record.get("num_pages", 0),
                    "file_size": db_record.get("file_size", 0),
                    "modified_date": db_record.get("modified_date", ""),
                    "created_date": db_record.get("created_date", ""),
                    "thumbnail_path": thumbnail_path_str,
                    "error": None,
                }
                self._cache[filename] = pdf_info
                db_hits += 1

            else:
                # Not in database - extract from file (slow path)
                logger.debug(f"Extracting metadata from file: {filename}")
                try:
                    # Get file stats
                    stat = file_path.stat()

                    # Extract basic metadata
                    with open(file_path, "rb") as file:
                        reader = PdfReader(file)
                        num_pages = len(reader.pages)

                        # Try to get metadata
                        metadata = reader.metadata or {}
                        title = metadata.get("/Title", file_path.stem)
                        author = metadata.get("/Author", "Unknown")

                    # Pre-generate thumbnail
                    try:
                        thumbnail_path = self.pdf_service.generate_thumbnail(
                            file_path.name
                        )
                        thumbnail_path_str = str(thumbnail_path)
                    except Exception as thumb_error:
                        logger.warning(
                            f"Failed to generate thumbnail for {file_path.name}: {thumb_error}"
                        )
                        thumbnail_path_str = ""

                    # Store basic metadata in cache
                    pdf_info = {
                        "filename": file_path.name,
                        "type": "pdf",
                        "title": str(title) if title else file_path.stem,
                        "author": str(author) if author else "Unknown",
                        "num_pages": num_pages,
                        "file_size": stat.st_size,
                        "modified_date": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "created_date": datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat(),
                        "thumbnail_path": thumbnail_path_str,
                        "error": None,
                    }

                    self._cache[file_path.name] = pdf_info

                    # Persist to database
                    try:
                        self._db_service.create_or_update(
                            filename=file_path.name,
                            title=pdf_info["title"],
                            author=pdf_info["author"],
                            num_pages=num_pages,
                            file_size=stat.st_size,
                            file_path=str(file_path),
                            thumbnail_path=thumbnail_path_str,
                            created_date=pdf_info["created_date"],
                            modified_date=pdf_info["modified_date"],
                        )
                    except Exception as db_error:
                        logger.error(
                            f"Error persisting {file_path.name} to database: {db_error}"
                        )
                        # Continue even if DB write fails - cache still works

                    db_misses += 1

                except Exception as e:
                    # If we can't read a PDF, still include it but with limited info
                    logger.error(f"Error processing {file_path.name}: {e}")
                    stat = file_path.stat()
                    pdf_info = {
                        "filename": file_path.name,
                        "type": "pdf",
                        "title": file_path.stem,
                        "author": "Unknown",
                        "num_pages": 0,
                        "file_size": stat.st_size,
                        "modified_date": datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "created_date": datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat(),
                        "thumbnail_path": "",
                        "error": f"Could not read PDF: {str(e)}",
                    }
                    self._cache[file_path.name] = pdf_info
                    db_misses += 1

        # Update cache metadata
        self._cache_built_at = datetime.now().isoformat()
        self._cache_pdf_count = len(self._cache)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Cache build completed in {elapsed_time:.2f}s - {self._cache_pdf_count} PDFs cached "
            f"(DB hits: {db_hits}, new: {db_misses})"
        )

    def get_all_pdfs(self) -> list[dict[str, object]]:
        """
        Get all PDFs with basic metadata from cache.

        Returns:
            List of PDF metadata dictionaries, sorted by modified_date (newest first)
        """
        # Convert cache dict to list
        pdfs = list(self._cache.values())

        # Sort by modified date (newest first)
        pdfs.sort(key=lambda x: x["modified_date"], reverse=True)

        return pdfs

    def get_pdf_info(self, filename: str) -> dict[str, object]:
        """
        Get detailed PDF info with lazy-loaded extended metadata.

        First call: Reads extended metadata from filesystem and caches it
        Subsequent calls: Returns cached data

        Phase 1a: Also persists extended metadata to database when lazy-loaded.

        Args:
            filename: Name of the PDF file

        Returns:
            Dictionary with full PDF metadata

        Raises:
            FileNotFoundError: If PDF not found in cache
        """
        # Check if PDF exists in cache
        if filename not in self._cache:
            raise FileNotFoundError(f"PDF {filename} not found in cache")

        pdf_info = self._cache[filename]

        # Check if extended metadata is already loaded
        # Extended metadata fields: subject, creator, producer, creation_date, modification_date
        if "subject" not in pdf_info:
            # Lazy-load extended metadata
            logger.debug(f"Lazy-loading extended metadata for: {filename}")
            try:
                file_path = self.pdf_dir / filename

                if not file_path.exists():
                    raise FileNotFoundError(f"PDF {filename} not found on filesystem")

                with open(file_path, "rb") as file:
                    reader = PdfReader(file)
                    metadata = reader.metadata or {}

                    # Extract extended metadata
                    pdf_info["subject"] = str(metadata.get("/Subject", ""))
                    pdf_info["creator"] = str(metadata.get("/Creator", ""))
                    pdf_info["producer"] = str(metadata.get("/Producer", ""))
                    pdf_info["creation_date"] = str(metadata.get("/CreationDate", ""))
                    pdf_info["modification_date"] = str(metadata.get("/ModDate", ""))

                    logger.debug(f"Extended metadata cached for: {filename}")

                    # Phase 1a: Persist extended metadata to database
                    try:
                        self._db_service.create_or_update(
                            filename=filename,
                            num_pages=pdf_info["num_pages"],
                            title=pdf_info["title"],
                            author=pdf_info["author"],
                            subject=pdf_info["subject"],
                            creator=pdf_info["creator"],
                            producer=pdf_info["producer"],
                            file_size=pdf_info.get("file_size"),
                            file_path=str(file_path),
                            thumbnail_path=pdf_info.get("thumbnail_path", ""),
                            created_date=pdf_info.get("created_date"),
                            modified_date=pdf_info.get("modified_date"),
                        )
                    except Exception as db_error:
                        logger.error(
                            f"Error persisting extended metadata for {filename} to database: {db_error}"
                        )
                        # Continue even if DB write fails

            except Exception as e:
                logger.error(f"Error loading extended metadata for {filename}: {e}")
                # Set empty values on error
                pdf_info["subject"] = ""
                pdf_info["creator"] = ""
                pdf_info["producer"] = ""
                pdf_info["creation_date"] = ""
                pdf_info["modification_date"] = ""

        return pdf_info

    def get_thumbnail_path(self, filename: str) -> str:
        """
        Get cached thumbnail path for a PDF.

        Args:
            filename: Name of the PDF file

        Returns:
            Path to thumbnail (may be empty string if generation failed)

        Raises:
            FileNotFoundError: If PDF not found in cache
        """
        if filename not in self._cache:
            raise FileNotFoundError(f"PDF {filename} not found in cache")

        return self._cache[filename].get("thumbnail_path", "")

    def refresh(self) -> None:
        """
        Refresh the cache by rebuilding from filesystem.
        Clears all cached data (including extended metadata) and regenerates.
        """
        logger.info("Refreshing PDF cache...")
        self._build_cache()
        logger.info("PDF cache refresh complete")

    def get_cache_info(self) -> dict[str, object]:
        """
        Get metadata about the cache itself.

        Returns:
            Dictionary with cache metadata
        """
        return {
            "cache_built_at": self._cache_built_at,
            "pdf_count": self._cache_pdf_count,
            "cached_files": list(self._cache.keys()),
        }
