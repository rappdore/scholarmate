import io
import re
import zipfile
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

            # Try to find cover image using EPUB specification methods
            cover_image = self._find_cover_image(book)

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

    def _find_cover_image(self, book):
        """
        Find cover image using EPUB specification methods:
        1. Parse OPF directly to find cover metadata and manifest
        2. Fall back to largest image
        3. Fall back to first image
        """
        from xml.etree import ElementTree as ET

        # Method 1: Parse OPF file directly - most reliable
        try:
            # Find the EPUB file path by reconstructing from epub_dir
            epub_path = None

            # Get all EPUB files and find the one we're working with
            for epub_file in self.epub_dir.glob("*.epub"):
                try:
                    # Quick check - compare first item name to see if it matches
                    test_book = epub.read_epub(str(epub_file))
                    test_items = list(test_book.get_items())
                    book_items = list(book.get_items())

                    if (
                        test_items
                        and book_items
                        and len(test_items) == len(book_items)
                        and test_items[0].get_name() == book_items[0].get_name()
                    ):
                        epub_path = str(epub_file)
                        break
                except Exception:
                    continue

            if epub_path:
                with zipfile.ZipFile(epub_path, "r") as zip_file:
                    # Read container.xml to find OPF file
                    container_xml = zip_file.read("META-INF/container.xml").decode(
                        "utf-8"
                    )
                    container_root = ET.fromstring(container_xml)

                    # Find OPF path
                    opf_path = None
                    for rootfile in container_root.findall(
                        ".//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile"
                    ):
                        opf_path = rootfile.get("full-path")
                        break

                    if opf_path:
                        opf_content = zip_file.read(opf_path).decode("utf-8")
                        opf_root = ET.fromstring(opf_content)

                        # Look for <meta name="cover" content="cover_id"/>
                        cover_metas = opf_root.findall(
                            './/{http://www.idpf.org/2007/opf}meta[@name="cover"]'
                        )
                        for meta in cover_metas:
                            cover_id = meta.get("content")
                            if cover_id:
                                # First try to find the book item with this ID
                                for item in book.get_items():
                                    if (
                                        item.get_id() == cover_id
                                        and item.get_type() == ebooklib.ITEM_IMAGE
                                    ):
                                        return item

                                # If ebooklib can't provide it, try to create a custom item from ZIP
                                cover_item = self._create_image_item_from_zip(
                                    zip_file, opf_root, cover_id, opf_path
                                )
                                if cover_item:
                                    return cover_item

                        # Look for items with properties="cover-image"
                        manifest_items = opf_root.findall(
                            ".//{http://www.idpf.org/2007/opf}item"
                        )
                        for item_elem in manifest_items:
                            props = item_elem.get("properties", "")
                            if "cover-image" in props:
                                item_id = item_elem.get("id")
                                # First try ebooklib
                                for item in book.get_items():
                                    if (
                                        item.get_id() == item_id
                                        and item.get_type() == ebooklib.ITEM_IMAGE
                                    ):
                                        return item

                                # If ebooklib can't provide it, try to create from ZIP
                                cover_item = self._create_image_item_from_zip(
                                    zip_file, opf_root, item_id, opf_path
                                )
                                if cover_item:
                                    return cover_item

        except Exception as e:
            print(f"OPF parsing failed: {e}")

        # Method 2: Fall back to largest image (covers are usually largest)
        largest_image = None
        largest_size = 0

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                try:
                    content = item.get_content()
                    size = len(content)
                    if size > largest_size:
                        largest_size = size
                        largest_image = item
                except Exception:
                    continue

        # Return largest if it's substantial (> 50KB, likely a cover not a small icon)
        if largest_image and largest_size > 50000:
            return largest_image

        # Method 3: Filename-based detection
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE:
                if "cover" in item.get_name().lower():
                    return item

        # Method 4: Return largest image even if small
        if largest_image:
            return largest_image

        # Method 5: Fall back to first image
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            return item

        return None

    def _create_image_item_from_zip(self, zip_file, opf_root, item_id, opf_path):
        """
        Create a custom image item from ZIP file when ebooklib can't provide it
        """
        try:
            # Find the manifest item with this ID
            manifest_items = opf_root.findall(".//{http://www.idpf.org/2007/opf}item")
            for item_elem in manifest_items:
                if item_elem.get("id") == item_id:
                    href = item_elem.get("href")
                    media_type = item_elem.get("media-type", "")

                    if href and media_type.startswith("image/"):
                        # Build full path to the image in ZIP
                        # OPF path might be OEBPS/content.opf, so image is relative to OEBPS/
                        opf_dir = "/".join(
                            opf_path.split("/")[:-1]
                        )  # Remove content.opf
                        if opf_dir:
                            image_path = f"{opf_dir}/{href}"
                        else:
                            image_path = href

                        try:
                            # Try to read the image from ZIP
                            image_data = zip_file.read(image_path)

                            # Create a custom item-like object
                            class CustomImageItem:
                                def __init__(self, id, name, content):
                                    self._id = id
                                    self._name = name
                                    self._content = content

                                def get_id(self):
                                    return self._id

                                def get_name(self):
                                    return self._name

                                def get_content(self):
                                    return self._content

                                def get_type(self):
                                    return ebooklib.ITEM_IMAGE

                            return CustomImageItem(item_id, href, image_data)

                        except KeyError:
                            # Image file not found in ZIP
                            continue

            return None

        except Exception:
            return None

    def get_thumbnail_path(self, filename: str) -> Path:
        """
        Get the path to the thumbnail for an EPUB file
        """
        file_path = self.get_epub_path(filename)
        thumbnail_filename = f"{file_path.stem}_thumb.png"
        return self.thumbnails_dir / thumbnail_filename

    def get_navigation_tree(self, filename: str) -> Dict[str, Any]:
        """
        Get the hierarchical navigation structure of an EPUB
        Returns full table of contents with nested structure
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        # Get the navigation document
        nav_items = []

        # Try to get navigation from toc (table of contents)
        if hasattr(book, "toc") and book.toc:
            nav_items = self._process_toc_items(book.toc, book)
        else:
            # Fallback: create navigation from spine (reading order)
            spine_items = []
            for item_id, _ in book.spine:
                item = book.get_item_with_id(item_id)
                if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                    spine_items.append(
                        {
                            "id": item.get_id(),
                            "title": item.get_name()
                            .replace(".xhtml", "")
                            .replace(".html", "")
                            .replace("_", " ")
                            .title(),
                            "level": 1,
                            "children": [],
                        }
                    )
            nav_items = spine_items

        return {
            "navigation": nav_items,
            "spine_length": len(book.spine),
            "has_toc": bool(hasattr(book, "toc") and book.toc),
        }

    def _process_toc_items(self, toc_items, book, level=1):
        """
        Recursively process table of contents items
        """
        processed_items = []

        for item in toc_items:
            if isinstance(item, tuple):
                # This is a nested section
                section, children = item
                if hasattr(section, "title") and hasattr(section, "href"):
                    nav_id = self._get_nav_id_from_href(section.href, book)
                    processed_item = {
                        "id": nav_id,
                        "title": str(section.title),
                        "href": section.href,
                        "level": level,
                        "children": self._process_toc_items(children, book, level + 1),
                    }
                    processed_items.append(processed_item)
            elif hasattr(item, "title") and hasattr(item, "href"):
                # This is a direct navigation item
                nav_id = self._get_nav_id_from_href(item.href, book)
                processed_item = {
                    "id": nav_id,
                    "title": str(item.title),
                    "href": item.href,
                    "level": level,
                    "children": [],
                }
                processed_items.append(processed_item)

        return processed_items

    def _get_nav_id_from_href(self, href, book):
        """
        Convert href to navigation ID by finding the corresponding spine item
        """
        # Remove fragment identifier (anchor)
        base_href = href.split("#")[0] if "#" in href else href

        # Find the item in the book
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_name() == base_href or item.get_name().endswith(base_href):
                return item.get_id()

        # Fallback: use href as ID (cleaned)
        return base_href.replace("/", "_").replace(".", "_")

    def get_content_by_nav_id(self, filename: str, nav_id: str) -> Dict[str, Any]:
        """
        Get HTML content for a specific navigation section
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        # Find the item with the given ID
        target_item = None
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_id() == nav_id:
                target_item = item
                break

        if not target_item:
            # Try to find by name if ID doesn't match
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                if (
                    nav_id in item.get_name()
                    or item.get_name().replace(".", "_").replace("/", "_") == nav_id
                ):
                    target_item = item
                    break

        if not target_item:
            raise ValueError(f"Navigation section '{nav_id}' not found")

        # Get the content
        content = target_item.get_content().decode("utf-8")

        # Sanitize HTML content for security
        content = self._sanitize_html(content)

        # Rewrite image paths to point to our image serving endpoint
        content = self._rewrite_image_paths(content, filename)

        # Find position in spine for navigation context
        spine_position = 0
        total_spine = len(book.spine)

        for idx, (item_id, _) in enumerate(book.spine):
            if item_id == target_item.get_id():
                spine_position = idx
                break

        # Get navigation context (previous/next)
        prev_nav_id = None
        next_nav_id = None

        if spine_position > 0:
            prev_item_id, _ = book.spine[spine_position - 1]
            prev_nav_id = prev_item_id

        if spine_position < total_spine - 1:
            next_item_id, _ = book.spine[spine_position + 1]
            next_nav_id = next_item_id

        return {
            "nav_id": nav_id,
            "title": target_item.get_name()
            .replace(".xhtml", "")
            .replace(".html", "")
            .replace("_", " ")
            .title(),
            "content": content,
            "spine_position": spine_position,
            "total_sections": total_spine,
            "progress_percentage": round(
                (spine_position / max(total_spine - 1, 1)) * 100, 1
            ),
            "previous_nav_id": prev_nav_id,
            "next_nav_id": next_nav_id,
        }

    def get_epub_styles(self, filename: str) -> Dict[str, Any]:
        """
        Extract and return CSS styles from an EPUB
        Returns sanitized CSS content for safe browser rendering
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        styles = []

        # Get all CSS items from the EPUB
        for item in book.get_items_of_type(ebooklib.ITEM_STYLE):
            try:
                css_content = item.get_content().decode("utf-8")
                # Sanitize CSS to remove potentially harmful content
                sanitized_css = self._sanitize_css(css_content)
                styles.append(
                    {
                        "id": item.get_id(),
                        "name": item.get_name(),
                        "content": sanitized_css,
                    }
                )
            except Exception:
                # Skip problematic CSS files
                continue

        return {"styles": styles, "count": len(styles)}

    def _sanitize_css(self, css_content: str) -> str:
        """
        Sanitize CSS content to remove potentially harmful elements
        """
        # Remove @import statements to prevent loading external resources
        css_content = re.sub(r"@import\s+[^;]+;", "", css_content, flags=re.IGNORECASE)

        # Remove url() functions that could load external resources
        css_content = re.sub(
            r'url\s*\(\s*[\'"]?[^\'")]*[\'"]?\s*\)',
            "url(about:blank)",
            css_content,
            flags=re.IGNORECASE,
        )

        # Remove javascript: protocols
        css_content = re.sub(r"javascript\s*:", "", css_content, flags=re.IGNORECASE)

        # Remove expression() functions (IE-specific but potentially harmful)
        css_content = re.sub(
            r"expression\s*\([^)]*\)", "", css_content, flags=re.IGNORECASE
        )

        return css_content

    def _sanitize_html(self, html_content: str) -> str:
        """
        Sanitize HTML content to remove potentially harmful elements
        and extract only the body content for proper container styling
        """
        # Remove script tags and their content
        html_content = re.sub(
            r"<script[^>]*>.*?</script>",
            "",
            html_content,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Remove inline event handlers
        html_content = re.sub(
            r'\s+on\w+\s*=\s*[\'"][^\'"]*[\'"]', "", html_content, flags=re.IGNORECASE
        )
        html_content = re.sub(
            r"\s+on\w+\s*=\s*[^\s>]+", "", html_content, flags=re.IGNORECASE
        )

        # Remove javascript: protocols from href and src attributes
        html_content = re.sub(
            r'(href|src)\s*=\s*[\'"]javascript:[^\'"]*[\'"]',
            "",
            html_content,
            flags=re.IGNORECASE,
        )

        # Extract content from body tag if it exists
        # This prevents EPUB body/html styles from interfering with our container
        body_match = re.search(
            r"<body[^>]*>(.*?)</body>", html_content, flags=re.DOTALL | re.IGNORECASE
        )

        if body_match:
            # Use only the content inside the body tag
            html_content = body_match.group(1)
        else:
            # If no body tag, remove html and head tags if present
            # Remove head section entirely
            html_content = re.sub(
                r"<head[^>]*>.*?</head>",
                "",
                html_content,
                flags=re.DOTALL | re.IGNORECASE,
            )

            # Remove html and body opening/closing tags but keep content
            html_content = re.sub(
                r"</?html[^>]*>",
                "",
                html_content,
                flags=re.IGNORECASE,
            )
            html_content = re.sub(
                r"</?body[^>]*>",
                "",
                html_content,
                flags=re.IGNORECASE,
            )

        # Remove any remaining doctype declarations
        html_content = re.sub(
            r"<!DOCTYPE[^>]*>",
            "",
            html_content,
            flags=re.IGNORECASE,
        )

        # Clean up extra whitespace
        html_content = html_content.strip()

        return html_content

    def get_epub_image(self, filename: str, image_path: str) -> bytes:
        """
        Extract and return a specific image from an EPUB file
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        # Try to find the image by path
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            if item.get_name() == image_path or item.get_name().endswith(image_path):
                return item.get_content()

        # If not found, try with different path variations
        clean_path = image_path.lstrip("./")
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_name = item.get_name()
            if (
                item_name == clean_path
                or item_name.endswith("/" + clean_path)
                or item_name.split("/")[-1] == clean_path.split("/")[-1]
            ):
                return item.get_content()

        raise FileNotFoundError(f"Image {image_path} not found in EPUB")

    def get_epub_images_list(self, filename: str) -> List[Dict[str, str]]:
        """
        Get a list of all images in an EPUB file
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        images = []
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            images.append(
                {"id": item.get_id(), "name": item.get_name(), "path": item.get_name()}
            )

        return images

    def _rewrite_image_paths(self, content: str, filename: str) -> str:
        """
        Rewrite image paths in HTML content to point to our image serving endpoint
        """
        import re

        # Pattern to match img src attributes
        img_pattern = r'<img([^>]*?)src\s*=\s*["\']([^"\']*?)["\']([^>]*?)>'

        def replace_img_src(match):
            before_src = match.group(1)
            src_path = match.group(2)
            after_src = match.group(3)

            # Skip if already an absolute URL
            if src_path.startswith(("http://", "https://", "data:")):
                return match.group(0)

            # Clean up the path
            clean_path = src_path.lstrip("./")

            # Create new URL pointing to our image endpoint
            new_src = f"http://localhost:8000/epub/{filename}/image/{clean_path}"

            return f'<img{before_src}src="{new_src}"{after_src}>'

        return re.sub(img_pattern, replace_img_src, content, flags=re.IGNORECASE)
