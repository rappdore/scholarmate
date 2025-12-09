from pathlib import Path
from typing import Any, Dict, List

from ebooklib import epub

from .epub import (
    EPUBContentProcessor,
    EPUBImageService,
    EPUBMetadataExtractor,
    EPUBNavigationService,
    EPUBStyleProcessor,
)
from .epub.epub_url_helper import EPUBURLHelper
from .epub_cache import EPUBCache


class EPUBService:
    def __init__(self, epub_dir: str = "epubs", base_url: str = None):
        self.epub_dir = Path(epub_dir)
        self.thumbnails_dir = Path("thumbnails")
        # Make base URL configurable for different deployment environments
        self.base_url = base_url or "http://localhost:8000"

        if not self.epub_dir.exists():
            self.epub_dir.mkdir(exist_ok=True)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

        # Initialize component services
        self.metadata_extractor = EPUBMetadataExtractor(epub_dir)
        self.navigation_service = EPUBNavigationService()
        self.content_processor = EPUBContentProcessor(self.base_url)
        self.image_service = EPUBImageService("thumbnails")
        self.style_processor = EPUBStyleProcessor()

        # Initialize cache (must be after other services are initialized)
        self.cache = EPUBCache(self.epub_dir, self.thumbnails_dir, self)

    def list_epubs(self) -> List[Dict[str, Any]]:
        """
        List all EPUB files in the epubs directory with metadata (from cache)
        """
        return self.cache.get_all_epubs()

    def get_epub_info(self, filename: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific EPUB (with lazy-loaded extended metadata)
        """
        # Decode filename to handle URL-encoded filenames
        decoded_filename = EPUBURLHelper.decode_filename_from_url(filename)
        return self.cache.get_epub_info(decoded_filename)

    def get_epub_path(self, filename: str) -> Path:
        """
        Get the full path to an EPUB file
        Handles URL decoding for filenames with special characters
        """
        # Decode the filename in case it's URL-encoded
        decoded_filename = EPUBURLHelper.decode_filename_from_url(filename)

        file_path = self.epub_dir / decoded_filename

        if not file_path.exists():
            raise FileNotFoundError(f"EPUB {decoded_filename} not found")

        if not file_path.suffix.lower() == ".epub":
            raise ValueError(f"{decoded_filename} is not an EPUB file")

        return file_path

    def generate_thumbnail(
        self,
        filename: str,
        width: int = 200,
        height: int = 280,
        background_color: str = "white",
        strategy: str = "center",
    ) -> Path:
        """
        Generate a thumbnail image of the EPUB cover
        Returns the path to the generated thumbnail
        """
        file_path = self.get_epub_path(filename)
        return self.image_service.generate_thumbnail(
            file_path, width, height, background_color, strategy
        )

    def get_thumbnail_path(
        self, filename: str, width: int = 200, height: int = 280
    ) -> Path:
        """
        Get the path to the thumbnail for an EPUB file (from cache, pre-generated)
        """
        # Try to get from cache first
        decoded_filename = EPUBURLHelper.decode_filename_from_url(filename)
        try:
            thumbnail_path_str = self.cache.get_thumbnail_path(decoded_filename)
            if thumbnail_path_str:
                return Path(thumbnail_path_str)
        except FileNotFoundError:
            pass

        # Fallback: generate if not in cache (shouldn't happen normally)
        file_path = self.get_epub_path(filename)
        return self.image_service.get_thumbnail_path(file_path, width, height)

    def get_navigation_tree(self, filename: str) -> Dict[str, Any]:
        """
        Get the hierarchical navigation structure of an EPUB
        Returns full table of contents with nested structure
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.navigation_service.get_navigation_tree(book)

    def get_content_by_nav_id(self, filename: str, nav_id: str) -> Dict[str, Any]:
        """
        Get HTML content for a specific navigation section
        Enhanced to handle chapters that span multiple spine items
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.content_processor.get_content_by_nav_id(book, nav_id, filename)

    def extract_section_text(self, filename: str, nav_id: str) -> str:
        """
        Extracts plain text content for a specific navigation section.
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.content_processor.extract_section_text(book, nav_id, filename)

    def get_epub_styles(self, filename: str) -> Dict[str, Any]:
        """
        Extract and return CSS styles from an EPUB
        Returns sanitized CSS content for safe browser rendering
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.style_processor.get_epub_styles(book)

    def get_epub_image(self, filename: str, image_path: str) -> bytes:
        """
        Extract and return a specific image from an EPUB file
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.image_service.get_epub_image(book, image_path)

    def get_epub_images_list(self, filename: str) -> List[Dict[str, str]]:
        """
        Get a list of all images in an EPUB file
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))
        return self.image_service.get_epub_images_list(book)

    def refresh_cache(self) -> Dict[str, Any]:
        """
        Refresh the EPUB cache by rebuilding from filesystem
        """
        self.cache.refresh()
        return self.cache.get_cache_info()

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get metadata about the EPUB cache
        """
        return self.cache.get_cache_info()
