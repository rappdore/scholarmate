from datetime import datetime
from pathlib import Path
from typing import Any

import ebooklib
from ebooklib import epub


class EPUBMetadataExtractor:
    def __init__(self, epub_dir: str = "epubs"):
        self.epub_dir = Path(epub_dir)

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

    def list_epubs(self) -> list[dict[str, Any]]:
        """
        List all EPUB files in the epubs directory with metadata
        """
        epubs = []

        for file_path in self.epub_dir.glob("*.epub"):
            try:
                # Get file stats
                stat = file_path.stat()

                # Get basic EPUB info
                book = epub.read_epub(str(file_path))

                # Extract metadata using robust method
                title = self._extract_metadata_values(book, "DC", "title")
                if not title:
                    title = file_path.stem

                author = self._extract_metadata_values(book, "DC", "creator")

                # Count chapters (spine items that are not navigation)
                chapter_count = len(
                    [item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
                )

                epub_info = {
                    "filename": file_path.name,
                    "type": "epub",
                    "title": str(title),
                    "author": str(author) if author else "Unknown",
                    "chapters": chapter_count,
                    "file_size": stat.st_size,
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                }

                epubs.append(epub_info)

            except Exception as e:
                # If we can't read an EPUB, still include it but with limited info
                stat = file_path.stat()
                epub_info = {
                    "filename": file_path.name,
                    "type": "epub",
                    "title": file_path.stem,
                    "author": "Unknown",
                    "chapters": 0,
                    "file_size": stat.st_size,
                    "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "error": f"Could not read EPUB: {str(e)}",
                }
                epubs.append(epub_info)

        # Sort by modified date (newest first)
        epubs.sort(key=lambda x: x["modified_date"], reverse=True)

        return epubs

    def get_epub_info(self, file_path: Path) -> dict[str, Any]:
        """
        Get detailed information about a specific EPUB
        """
        if not file_path.exists():
            raise FileNotFoundError(f"EPUB {file_path.name} not found")

        if not file_path.suffix.lower() == ".epub":
            raise ValueError(f"{file_path.name} is not an EPUB file")

        stat = file_path.stat()

        book = epub.read_epub(str(file_path))

        # Extract metadata using robust method
        title = self._extract_metadata_values(book, "DC", "title")
        if not title:
            title = file_path.stem

        author = self._extract_metadata_values(book, "DC", "creator")
        subject = self._extract_metadata_values(book, "DC", "subject")
        publisher = self._extract_metadata_values(book, "DC", "publisher")
        language = self._extract_metadata_values(book, "DC", "language")

        # Count chapters
        chapter_count = len(
            [item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        )

        epub_info = {
            "filename": file_path.name,
            "type": "epub",
            "title": str(title),
            "author": str(author) if author else "Unknown",
            "subject": str(subject),
            "publisher": str(publisher),
            "language": str(language),
            "chapters": chapter_count,
            "file_size": stat.st_size,
            "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }

        return epub_info
