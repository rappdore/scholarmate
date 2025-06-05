import re
from typing import Any, Dict, Tuple

import ebooklib
from bs4 import BeautifulSoup

from .epub_navigation_service import EPUBNavigationService


class EPUBContentProcessor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.navigation_service = EPUBNavigationService()

    def get_content_by_nav_id(self, book, nav_id: str, filename: str) -> Dict[str, Any]:
        """
        Get HTML content for a specific navigation section
        Enhanced to handle chapters that span multiple spine items
        """
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
    ) -> Tuple[str, int]:
        """
        Get complete chapter content that may span multiple spine items.
        Uses EPUB's native navigation structure to determine logical boundaries.
        Returns (combined_content, number_of_spine_items_used)
        """
        # Get the navigation structure to understand logical boundaries
        spine_to_nav_mapping = self.navigation_service.build_spine_to_nav_mapping(book)

        # Find the logical chapter/section that contains this spine position
        current_nav_entry = spine_to_nav_mapping.get(start_spine_position)

        if not current_nav_entry:
            # Fallback: just return single spine item if no TOC mapping
            return self._get_single_spine_content(
                book, start_spine_position, filename
            ), 1

        # Find all spine items that belong to the same logical chapter
        chapter_spine_items = self.navigation_service.get_chapter_spine_items(
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

    def _rewrite_image_paths(self, content: str, filename: str) -> str:
        """
        Rewrite image paths in HTML content to point to our image serving endpoint
        """
        # Pattern to match img src attributes
        img_pattern = r'<img([^>]*?)src\s*=\s*["\']([^"\']*?)["\']([^>]*?)>'

        def replace_img_src(match):
            before_src = match.group(1)
            src_path = match.group(2)
            after_src = match.group(3)

            # Skip if already an absolute URL
            if src_path.startswith(("http://", "https://", "data:")):
                return match.group(0)

            # Construct the new path
            # The replace('.', '_') is to handle potential file extension issues in paths
            safe_filename = filename.replace(".", "_")
            new_src = f"{self.base_url}/epub/{safe_filename}/image/{src_path}"
            return f'<img{before_src}src="{new_src}"{after_src}>'

        return re.sub(img_pattern, replace_img_src, content, flags=re.IGNORECASE)

    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract plain text from HTML content using BeautifulSoup.
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        return text

    def extract_section_text(self, book, nav_id: str, filename: str) -> str:
        """
        Extracts plain text content for a specific navigation section.
        """
        # We pass filename here because get_content_by_nav_id needs it to rewrite image paths,
        # even though we are stripping them out, it's part of the process.
        section_data = self.get_content_by_nav_id(book, nav_id, filename)
        html_content = section_data.get("content", "")
        return self._extract_text_from_html(html_content)
