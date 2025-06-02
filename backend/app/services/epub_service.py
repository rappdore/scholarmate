import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import ebooklib
from ebooklib import epub
from PIL import Image


class EPUBService:
    def __init__(self, epub_dir: str = "epubs"):
        self.epub_dir = Path(epub_dir)
        self.thumbnails_dir = Path("thumbnails")
        if not self.epub_dir.exists():
            self.epub_dir.mkdir(exist_ok=True)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

    def list_epubs(self) -> List[Dict[str, Any]]:
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

                # Try to get metadata
                title = (
                    book.get_metadata("DC", "title")[0][0]
                    if book.get_metadata("DC", "title")
                    else file_path.stem
                )
                author_list = book.get_metadata("DC", "creator")
                author = author_list[0][0] if author_list else "Unknown"

                # Count chapters (spine items that are not navigation)
                chapter_count = len(
                    [item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
                )

                epub_info = {
                    "filename": file_path.name,
                    "type": "epub",
                    "title": str(title) if title else file_path.stem,
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

    def get_epub_info(self, filename: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific EPUB
        """
        file_path = self.epub_dir / filename

        if not file_path.exists():
            raise FileNotFoundError(f"EPUB {filename} not found")

        if not file_path.suffix.lower() == ".epub":
            raise ValueError(f"{filename} is not an EPUB file")

        stat = file_path.stat()

        book = epub.read_epub(str(file_path))

        # Get metadata
        title = (
            book.get_metadata("DC", "title")[0][0]
            if book.get_metadata("DC", "title")
            else file_path.stem
        )
        author_list = book.get_metadata("DC", "creator")
        author = author_list[0][0] if author_list else "Unknown"

        subject_list = book.get_metadata("DC", "subject")
        subject = subject_list[0][0] if subject_list else ""

        publisher_list = book.get_metadata("DC", "publisher")
        publisher = publisher_list[0][0] if publisher_list else ""

        language_list = book.get_metadata("DC", "language")
        language = language_list[0][0] if language_list else ""

        # Count chapters
        chapter_count = len(
            [item for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT)]
        )

        epub_info = {
            "filename": file_path.name,
            "type": "epub",
            "title": str(title),
            "author": str(author),
            "subject": str(subject),
            "publisher": str(publisher),
            "language": str(language),
            "chapters": chapter_count,
            "file_size": stat.st_size,
            "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        }

        return epub_info

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
        self, filename: str, width: int = 200, height: int = 280
    ) -> Path:
        """
        Generate a thumbnail image of the EPUB cover
        Returns the path to the generated thumbnail
        """
        file_path = self.get_epub_path(filename)

        # Create thumbnail filename
        thumbnail_filename = f"{file_path.stem}_thumb.png"
        thumbnail_path = self.thumbnails_dir / thumbnail_filename

        # Check if thumbnail already exists and is newer than the EPUB
        if thumbnail_path.exists():
            epub_mtime = file_path.stat().st_mtime
            thumb_mtime = thumbnail_path.stat().st_mtime
            if thumb_mtime > epub_mtime:
                return thumbnail_path

        try:
            # Open EPUB
            book = epub.read_epub(str(file_path))

            # Try to find cover image
            cover_image = None
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE:
                    # Check if this might be a cover image
                    if "cover" in item.get_name().lower():
                        cover_image = item
                        break

            # If no cover found, try to get the first image
            if not cover_image:
                for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
                    cover_image = item
                    break

            if cover_image:
                # Convert image data to PIL Image
                image_data = io.BytesIO(cover_image.get_content())
                img = Image.open(image_data)

                # Resize to thumbnail size while maintaining aspect ratio
                img.thumbnail((width, height), Image.Resampling.LANCZOS)

                # Create a new image with the exact target size and paste the thumbnail
                # This ensures consistent thumbnail sizes
                thumb = Image.new("RGB", (width, height), "white")

                # Calculate position to center the image
                x = (width - img.width) // 2
                y = (height - img.height) // 2

                thumb.paste(img, (x, y))

                # Save thumbnail
                thumb.save(str(thumbnail_path), "PNG")

                return thumbnail_path
            else:
                # No cover image found, create a default thumbnail
                thumb = Image.new("RGB", (width, height), "#f0f0f0")
                # Could add text here for the book title
                thumb.save(str(thumbnail_path), "PNG")
                return thumbnail_path

        except Exception:
            # If thumbnail generation fails, create a default thumbnail
            thumb = Image.new("RGB", (width, height), "#f0f0f0")
            thumb.save(str(thumbnail_path), "PNG")
            return thumbnail_path

    def get_thumbnail_path(self, filename: str) -> Path:
        """
        Get the path to the thumbnail for an EPUB file
        """
        file_path = self.get_epub_path(filename)
        thumbnail_filename = f"{file_path.stem}_thumb.png"
        return self.thumbnails_dir / thumbnail_filename
