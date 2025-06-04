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
    def __init__(self, epub_dir: str = "epubs", base_url: str = None):
        self.epub_dir = Path(epub_dir)
        self.thumbnails_dir = Path("thumbnails")
        # Make base URL configurable for different deployment environments
        self.base_url = base_url or "http://localhost:8000"
        if not self.epub_dir.exists():
            self.epub_dir.mkdir(exist_ok=True)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

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

        Args:
            filename: EPUB filename
            width: Target thumbnail width
            height: Target thumbnail height
            background_color: Background color for padding (white, #f0f0f0, etc.)
            strategy: Sizing strategy - "center" (default) or "fill"
        """
        file_path = self.get_epub_path(filename)

        # Create thumbnail filename with dimensions for caching
        thumbnail_filename = f"{file_path.stem}_thumb_{width}x{height}.png"
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
            cover_image = self._find_cover_image(book, str(file_path))

            if cover_image:
                # Convert image data to PIL Image
                image_data = io.BytesIO(cover_image.get_content())
                img = Image.open(image_data)

                if strategy == "fill":
                    # Fill strategy: crop to exact aspect ratio, then resize
                    target_ratio = width / height
                    img_ratio = img.width / img.height

                    if img_ratio > target_ratio:
                        # Image is wider - crop width
                        new_width = int(img.height * target_ratio)
                        left = (img.width - new_width) // 2
                        img = img.crop((left, 0, left + new_width, img.height))
                    else:
                        # Image is taller - crop height
                        new_height = int(img.width / target_ratio)
                        top = (img.height - new_height) // 2
                        img = img.crop((0, top, img.width, top + new_height))

                    # Resize to exact target size
                    thumb = img.resize((width, height), Image.Resampling.LANCZOS)
                else:
                    # Center strategy: maintain aspect ratio with padding
                    img.thumbnail((width, height), Image.Resampling.LANCZOS)

                    # Create background with specified color
                    thumb = Image.new("RGB", (width, height), background_color)

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

    def _find_cover_image(self, book, epub_path: str = None):
        """
        Find cover image using EPUB specification methods:
        1. Parse OPF directly to find cover metadata and manifest
        2. Fall back to largest image
        3. Fall back to filename-based detection
        4. Fall back to first image
        """
        from xml.etree import ElementTree as ET

        # Method 1: Parse OPF file directly - most reliable
        if epub_path:
            try:
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

        # Method 2: Filename-based detection (more reliable than size-based)
        cover_candidates = []
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_name = item.get_name().lower()
            # Common cover image naming patterns
            if any(
                pattern in item_name
                for pattern in ["cover", "front", "title", "jacket", "poster"]
            ):
                # Prioritize by how specific the match is
                if "cover" in item_name:
                    cover_candidates.append((item, 3))  # Highest priority
                elif "front" in item_name or "title" in item_name:
                    cover_candidates.append((item, 2))  # Medium priority
                else:
                    cover_candidates.append((item, 1))  # Lower priority

        # Return the highest priority cover candidate
        if cover_candidates:
            cover_candidates.sort(key=lambda x: x[1], reverse=True)
            return cover_candidates[0][0]

        # Method 3: Size-based detection (covers are usually largest)
        largest_image = None
        largest_size = 0
        size_candidates = []

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            try:
                content = item.get_content()
                size = len(content)
                size_candidates.append((item, size))
                if size > largest_size:
                    largest_size = size
                    largest_image = item
            except Exception:
                continue

        # Return largest if it's substantial (> 20KB, likely a cover not a small icon)
        # and significantly larger than other images
        if largest_image and largest_size > 20000:
            # Check if this image is significantly larger than others
            size_candidates.sort(key=lambda x: x[1], reverse=True)
            if len(size_candidates) > 1:
                second_largest_size = size_candidates[1][1]
                # If largest is at least 2x bigger than second largest, likely a cover
                if largest_size >= second_largest_size * 2:
                    return largest_image
            else:
                # Only one image, assume it's the cover
                return largest_image

        # Method 4: Fall back to first image as last resort
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

    def get_thumbnail_path(
        self, filename: str, width: int = 200, height: int = 280
    ) -> Path:
        """
        Get the path to the thumbnail for an EPUB file
        """
        file_path = self.get_epub_path(filename)
        thumbnail_filename = f"{file_path.stem}_thumb_{width}x{height}.png"
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
        and including fragment identifiers for uniqueness
        """
        # Split href into base and fragment
        if "#" in href:
            base_href, fragment = href.split("#", 1)
        else:
            base_href = href
            fragment = None

        # Find the item in the book
        spine_item_id = None
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_name() == base_href or item.get_name().endswith(base_href):
                spine_item_id = item.get_id()
                break

        # Create unique ID by combining spine item ID with fragment
        if spine_item_id:
            if fragment:
                # Include fragment to ensure uniqueness
                return f"{spine_item_id}#{fragment}"
            else:
                return spine_item_id
        else:
            # Fallback: use href as ID (cleaned but preserving fragments for uniqueness)
            return href.replace("/", "_").replace(".", "_")

    def get_content_by_nav_id(self, filename: str, nav_id: str) -> Dict[str, Any]:
        """
        Get HTML content for a specific navigation section
        Enhanced to handle chapters that span multiple spine items
        """
        file_path = self.get_epub_path(filename)
        book = epub.read_epub(str(file_path))

        # Handle navigation IDs that might contain fragments
        if "#" in nav_id:
            base_nav_id, fragment = nav_id.split("#", 1)
        else:
            base_nav_id = nav_id

        # Find the item with the given ID
        target_item = None
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            if item.get_id() == base_nav_id:
                target_item = item
                break

        if not target_item:
            # Try to find by name if ID doesn't match
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                if (
                    base_nav_id in item.get_name()
                    or item.get_name().replace(".", "_").replace("/", "_")
                    == base_nav_id
                ):
                    target_item = item
                    break

        if not target_item:
            raise ValueError(f"Navigation section '{nav_id}' not found")

        # Find position in spine for the starting item
        spine_position = 0
        total_spine = len(book.spine)

        for idx, (item_id, _) in enumerate(book.spine):
            if item_id == target_item.get_id():
                spine_position = idx
                break

        # Get the complete chapter content (potentially spanning multiple spine items)
        combined_content, spine_items_used = self._get_complete_chapter_content(
            book, spine_position, filename
        )

        # Calculate progress based on the last spine item used
        last_spine_position = spine_position + spine_items_used - 1
        progress_percentage = round(
            (last_spine_position / max(total_spine - 1, 1)) * 100, 1
        )

        # Get navigation context (previous/next) based on chapter boundaries
        prev_nav_id = None
        next_nav_id = None

        if spine_position > 0:
            prev_item_id, _ = book.spine[spine_position - 1]
            prev_nav_id = prev_item_id

        # Next nav_id should point to the item after the complete chapter
        next_spine_pos = spine_position + spine_items_used
        if next_spine_pos < total_spine:
            next_item_id, _ = book.spine[next_spine_pos]
            next_nav_id = next_item_id

        return {
            "nav_id": nav_id,
            "title": target_item.get_name()
            .replace(".xhtml", "")
            .replace(".html", "")
            .replace("_", " ")
            .title(),
            "content": combined_content,
            "spine_position": spine_position,
            "total_sections": total_spine,
            "progress_percentage": progress_percentage,
            "previous_nav_id": prev_nav_id,
            "next_nav_id": next_nav_id,
            "spine_items_used": spine_items_used,  # New field for debugging
        }

    def _get_complete_chapter_content(
        self, book, start_spine_position: int, filename: str
    ) -> tuple[str, int]:
        """
        Get complete chapter content that may span multiple spine items.
        Uses EPUB's native navigation structure to determine logical boundaries.
        Returns (combined_content, number_of_spine_items_used)
        """
        # Get the navigation structure to understand logical boundaries
        spine_to_nav_mapping = self._build_spine_to_nav_mapping(book)

        # Find the logical chapter/section that contains this spine position
        current_nav_entry = spine_to_nav_mapping.get(start_spine_position)

        if not current_nav_entry:
            # Fallback: just return single spine item if no TOC mapping
            return self._get_single_spine_content(
                book, start_spine_position, filename
            ), 1

        # Find all spine items that belong to the same logical chapter
        chapter_spine_items = self._get_chapter_spine_items(
            spine_to_nav_mapping, current_nav_entry, start_spine_position, book
        )

        # Combine content from all spine items in this logical chapter
        combined_content = ""
        for spine_pos in chapter_spine_items:
            item_id, _ = book.spine[spine_pos]
            current_item = book.get_item_with_id(item_id)

            if current_item and current_item.get_type() == ebooklib.ITEM_DOCUMENT:
                try:
                    raw_content = current_item.get_content().decode("utf-8")
                    sanitized_content = self._sanitize_html(raw_content)
                    processed_content = self._rewrite_image_paths(
                        sanitized_content, filename
                    )
                    combined_content += processed_content
                except Exception:
                    continue

        return combined_content, len(chapter_spine_items)

    def _build_spine_to_nav_mapping(self, book) -> Dict[int, Dict[str, Any]]:
        """
        Build a mapping from spine position to navigation entry.
        This tells us which logical chapter/section each spine item belongs to.
        """
        spine_to_nav = {}

        # Get navigation structure
        try:
            if hasattr(book, "toc") and book.toc:
                nav_items = self._process_toc_items(book.toc, book)
            else:
                # Fallback: each spine item is its own section
                nav_items = []
                for idx, (item_id, _) in enumerate(book.spine):
                    item = book.get_item_with_id(item_id)
                    if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                        nav_items.append(
                            {
                                "id": item.get_id(),
                                "title": item.get_name()
                                .replace(".xhtml", "")
                                .replace(".html", "")
                                .replace("_", " ")
                                .title(),
                                "href": item.get_name(),
                                "level": 1,
                                "children": [],
                            }
                        )
        except Exception:
            nav_items = []

        # Map each navigation item to spine positions
        for nav_item in nav_items:
            spine_positions = self._find_spine_positions_for_nav_item(book, nav_item)

            for spine_pos in spine_positions:
                spine_to_nav[spine_pos] = nav_item

            # Also handle child navigation items
            self._map_child_nav_items(book, nav_item.get("children", []), spine_to_nav)

        return spine_to_nav

    def _map_child_nav_items(
        self, book, child_nav_items: List[Dict], spine_to_nav: Dict
    ):
        """Recursively map child navigation items to spine positions."""
        for child_item in child_nav_items:
            spine_positions = self._find_spine_positions_for_nav_item(book, child_item)

            for spine_pos in spine_positions:
                spine_to_nav[spine_pos] = child_item

            # Recursively handle nested children
            if child_item.get("children"):
                self._map_child_nav_items(book, child_item["children"], spine_to_nav)

    def _find_spine_positions_for_nav_item(
        self, book, nav_item: Dict[str, Any]
    ) -> List[int]:
        """
        Find which spine positions correspond to a navigation item.
        A nav item might span multiple spine items or be contained within one.
        """
        positions = []
        nav_href = nav_item.get("href", "")

        if not nav_href:
            return positions

        # Split href into base file and fragment
        if "#" in nav_href:
            base_href, fragment = nav_href.split("#", 1)
        else:
            base_href = nav_href

        # Find all spine positions that match this href
        for idx, (item_id, _) in enumerate(book.spine):
            item = book.get_item_with_id(item_id)
            if item and item.get_type() == ebooklib.ITEM_DOCUMENT:
                item_name = item.get_name()

                # Check if this spine item matches the navigation href
                if (
                    item_name == base_href
                    or item_name.endswith(base_href)
                    or base_href.endswith(item_name)
                ):
                    positions.append(idx)

        return positions

    def _get_chapter_spine_items(
        self,
        spine_to_nav_mapping: Dict,
        current_nav_entry: Dict,
        start_position: int,
        book,
    ) -> List[int]:
        """
        Get all spine items that belong to the same logical chapter as the current position.
        Uses navigation hierarchy to determine chapter boundaries.
        """
        current_level = current_nav_entry.get("level", 1)
        current_title = current_nav_entry.get("title", "")

        # Collect all spine positions for this logical chapter
        chapter_positions = []

        # Start from the current position and look forward
        for spine_pos in range(start_position, len(book.spine)):
            nav_entry = spine_to_nav_mapping.get(spine_pos)

            if not nav_entry:
                # No navigation info - include this spine item if we're still in the same chapter
                if chapter_positions:  # Only if we've already started collecting
                    chapter_positions.append(spine_pos)
                continue

            nav_level = nav_entry.get("level", 1)
            nav_title = nav_entry.get("title", "")

            # If we hit a navigation item at the same or higher level with a different title,
            # we've reached a new chapter
            if (
                nav_level <= current_level
                and nav_title != current_title
                and chapter_positions
            ):  # Only stop if we've collected something
                break

            chapter_positions.append(spine_pos)

        # Ensure we always include at least the starting position
        if not chapter_positions:
            chapter_positions = [start_position]

        return sorted(set(chapter_positions))

    def _get_single_spine_content(
        self, book, spine_position: int, filename: str
    ) -> str:
        """Fallback method to get content from a single spine item."""
        if spine_position >= len(book.spine):
            return ""

        item_id, _ = book.spine[spine_position]
        item = book.get_item_with_id(item_id)

        if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
            return ""

        try:
            raw_content = item.get_content().decode("utf-8")
            sanitized_content = self._sanitize_html(raw_content)
            return self._rewrite_image_paths(sanitized_content, filename)
        except Exception:
            return ""

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
            new_src = f"{self.base_url}/epub/{filename}/image/{clean_path}"

            return f'<img{before_src}src="{new_src}"{after_src}>'

        return re.sub(img_pattern, replace_img_src, content, flags=re.IGNORECASE)
