import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
        pdf_service: Any,
        db_path: str = "data/reading_progress.db",
    ):
        """
        Initialize the PDFCache, set up database-backed persistence, and build the in-memory cache of PDF metadata.
        
        Parameters:
            pdf_dir (Path): Directory containing PDF files to scan and cache.
            thumbnails_dir (Path): Directory where generated thumbnails are stored.
            pdf_service (Any): Service used to generate thumbnails and read PDF metadata.
            db_path (str): Path to the SQLite database file used to persist metadata (default: "data/reading_progress.db").
        
        Side effects:
            - Creates a PDFDocumentsService for persistence.
            - Builds the in-memory cache of basic PDF metadata and persists that basic metadata to the database.
        """
        self.pdf_dir = pdf_dir
        self.thumbnails_dir = thumbnails_dir
        self.pdf_service = pdf_service

        # Phase 1a: Database service for persistence
        self._db_service = PDFDocumentsService(db_path)

        # Cache storage: Dict[filename, metadata_dict]
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Cache metadata
        self._cache_built_at: Optional[str] = None
        self._cache_pdf_count: int = 0

        # Build cache on initialization
        logger.info("Initializing PDF cache with database backing...")
        self._build_cache()
        logger.info(f"PDF cache initialized with {self._cache_pdf_count} PDFs")

    def _build_cache(self) -> None:
        """
        Populate the in-memory PDF cache by scanning the configured pdf_dir and extracting each file's basic metadata.
        
        For each PDF file, basic metadata (filename, title, author, page count, size, creation and modification timestamps, and thumbnail path) is stored in the cache and a thumbnail is pre-generated. Basic metadata is also persisted to the configured database service; database write failures are non-fatal and do not stop the cache build. If a file cannot be read, a fallback cache entry with limited information and an error message is stored. After completion, cache metadata fields (_cache_built_at and _cache_pdf_count) are updated.
        """
        start_time = datetime.now()
        self._cache = {}

        logger.info(f"Scanning PDF directory: {self.pdf_dir}")

        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files")

        for file_path in pdf_files:
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
                    thumbnail_path = self.pdf_service.generate_thumbnail(file_path.name)
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
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "thumbnail_path": thumbnail_path_str,
                    "error": None,
                }

                self._cache[file_path.name] = pdf_info
                logger.debug(f"Cached metadata for: {file_path.name}")

                # Phase 1a: Persist to database
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
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "thumbnail_path": "",
                    "error": f"Could not read PDF: {str(e)}",
                }
                self._cache[file_path.name] = pdf_info

        # Update cache metadata
        self._cache_built_at = datetime.now().isoformat()
        self._cache_pdf_count = len(self._cache)

        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Cache build completed in {elapsed_time:.2f}s - {self._cache_pdf_count} PDFs cached"
        )

    def get_all_pdfs(self) -> List[Dict[str, Any]]:
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

    def get_pdf_info(self, filename: str) -> Dict[str, Any]:
        """
        Return detailed metadata for a cached PDF, lazily loading and caching extended fields on first access.
        
        If extended metadata is not present in the in-memory cache, reads the PDF file to extract subject, creator, producer, creation_date, and modification_date, stores those fields in the cache, and attempts to persist the extended metadata to the database (database errors are logged and ignored).
        
        Returns:
            dict: Full PDF metadata dictionary containing both basic fields (e.g., filename, title, author, num_pages, file_size, thumbnail_path, created_date, modified_date) and extended fields (subject, creator, producer, creation_date, modification_date).
        
        Raises:
            FileNotFoundError: If the specified filename is not present in the in-memory cache.
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

    def get_cache_info(self) -> Dict[str, Any]:
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