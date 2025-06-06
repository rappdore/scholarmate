import io
import zipfile
from pathlib import Path
from typing import Dict, List

import ebooklib
from ebooklib import epub
from PIL import Image

from .epub_url_helper import EPUBURLHelper


class EPUBImageService:
    def __init__(self, thumbnails_dir: str = "thumbnails"):
        self.thumbnails_dir = Path(thumbnails_dir)
        if not self.thumbnails_dir.exists():
            self.thumbnails_dir.mkdir(exist_ok=True)

    def generate_thumbnail(
        self,
        file_path: Path,
        width: int = 200,
        height: int = 280,
        background_color: str = "white",
        strategy: str = "center",
    ) -> Path:
        """
        Generate a thumbnail image of the EPUB cover
        Returns the path to the generated thumbnail

        Args:
            file_path: Path to EPUB file
            width: Target thumbnail width
            height: Target thumbnail height
            background_color: Background color for padding (white, #f0f0f0, etc.)
            strategy: Sizing strategy - "center" (default) or "fill"
        """
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

    def get_thumbnail_path(
        self, file_path: Path, width: int = 200, height: int = 280
    ) -> Path:
        """
        Get the path to the thumbnail for an EPUB file
        """
        thumbnail_filename = f"{file_path.stem}_thumb_{width}x{height}.png"
        return self.thumbnails_dir / thumbnail_filename

    def get_epub_image(self, book, image_path: str) -> bytes:
        """
        Extract and return a specific image from an EPUB file
        Uses robust URL helper for path normalization and security
        """
        # Validate the image path for security
        if not EPUBURLHelper.is_valid_image_path(image_path):
            raise FileNotFoundError(f"Invalid image path: {image_path}")

        # Normalize the path using URL helper
        normalized_path = EPUBURLHelper.normalize_image_path(image_path)

        if not normalized_path:
            raise FileNotFoundError(
                f"Empty image path after normalization: {image_path}"
            )

        # Try to find the image by exact match first
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_name = EPUBURLHelper.extract_image_path_from_epub_item(item.get_name())

            # Try multiple matching strategies
            if (
                item_name == image_path
                or item_name == normalized_path
                or item.get_name() == image_path
                or item.get_name() == normalized_path
                or item.get_name().endswith(image_path)
                or item.get_name().endswith(normalized_path)
            ):
                return item.get_content()

        # If not found, try fallback matching by filename only
        target_filename = (
            normalized_path.split("/")[-1]
            if "/" in normalized_path
            else normalized_path
        )

        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            item_filename = (
                item.get_name().split("/")[-1]
                if "/" in item.get_name()
                else item.get_name()
            )

            if item_filename == target_filename:
                return item.get_content()

        raise FileNotFoundError(f"Image {image_path} not found in EPUB")

    def get_epub_images_list(self, book) -> List[Dict[str, str]]:
        """
        Get a list of all images in an EPUB file
        """
        images = []
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            images.append(
                {"id": item.get_id(), "name": item.get_name(), "path": item.get_name()}
            )

        return images

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
