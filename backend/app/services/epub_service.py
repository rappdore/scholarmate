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

    def list_epubs(self) -> List[Dict[str, Any]]:
        """
        List all EPUB files in the epubs directory with metadata
        """
        return self.metadata_extractor.list_epubs()

    def get_epub_info(self, filename: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific EPUB
        """
        file_path = self.get_epub_path(filename)
        return self.metadata_extractor.get_epub_info(file_path)

    def get_epub_path(self, filename: str) -> Path:
        """
        Get the full path to an EPUB file
        """
        file_path = self.epub_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"EPUB {filename} not found")

        if not file_path.suffix.lower() == ".epub":
            raise ValueError(f"{filename} is not an EPUB file")

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
        Get the path to the thumbnail for an EPUB file
        """
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
