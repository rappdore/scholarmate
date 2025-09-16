import re
from typing import Any, Dict, List, Optional, Tuple

import ebooklib
from bs4 import BeautifulSoup

from .epub_navigation_service import EPUBNavigationService
from .epub_url_helper import EPUBURLHelper


class EPUBContentProcessor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.navigation_service = EPUBNavigationService()

    def get_content_by_nav_id(self, book, nav_id: str, filename: str) -> Dict[str, Any]:
        """
        Get HTML content for a specific navigation section.
        Uses the navigation index so previous/next navigation follows the book's
        logical table of contents rather than the raw spine order.
        """
        navigation_index = self.navigation_service.build_navigation_index(book)
        flat_nav = navigation_index["flat"]

        nav_entry = self._resolve_navigation_entry(nav_id, navigation_index, book)
        if not nav_entry:
            raise ValueError(f"Navigation section '{nav_id}' not found")

        resolved_nav_id = nav_entry.get("id", nav_id)

        content, used_positions = self._collect_entry_content(
            book, nav_entry, filename, resolved_nav_id
        )

        if not content:
            # As a last resort, attempt to load the requested nav_id directly.
            fallback_content, fallback_positions = self._legacy_nav_fallback(
                book, nav_id, filename
            )
            content = fallback_content
            used_positions = fallback_positions

        if not content:
            # Gracefully handle navigation nodes that don't have standalone content
            fallback_positions = nav_entry.get(
                "spine_positions", []
            ) or self._positions_from_item_ids(
                book, nav_entry.get("spine_item_ids", [])
            )
            used_positions = fallback_positions
            content = ""

        used_positions = sorted(set(used_positions))
        spine_start = used_positions[0] if used_positions else 0
        spine_end = used_positions[-1] if used_positions else spine_start

        progress_percentage = round(
            (spine_end / max(navigation_index["spine_length"] - 1, 1)) * 100,
            1,
        )

        previous_entry = self._adjacent_entry(flat_nav, nav_entry, -1)
        next_entry = self._adjacent_entry(flat_nav, nav_entry, 1)

        title = self._resolve_entry_title(nav_entry, book)

        return {
            "nav_id": resolved_nav_id,
            "title": title,
            "content": content,
            "spine_position": spine_start,
            "total_sections": self._count_readable_sections(flat_nav)
            or navigation_index["spine_length"],
            "progress_percentage": progress_percentage,
            "previous_nav_id": previous_entry.get("id") if previous_entry else None,
            "next_nav_id": next_entry.get("id") if next_entry else None,
            "spine_items_used": len(used_positions),
        }

    def _get_single_spine_content(
        self, book, spine_position: int, filename: str
    ) -> str:
        """Fallback method to get content from a single spine item."""
        if spine_position >= len(book.spine):
            return ""

        item_id, _ = book.spine[spine_position]
        item = book.get_item_with_id(item_id)

        if not self._is_document_item(item):
            return ""

        return self._get_processed_item_content(item, filename)

    def _collect_entry_content(
        self,
        book,
        nav_entry: Dict[str, Any],
        filename: str,
        requested_nav_id: str,
    ) -> Tuple[str, List[int]]:
        combined_content = ""
        used_positions: List[int] = []

        # Primary: use explicit spine positions recorded for the nav entry.
        for pos in nav_entry.get("spine_positions", []) or []:
            html = self._get_single_spine_content(book, pos, filename)
            if html:
                combined_content += html
                used_positions.append(pos)

        if combined_content:
            return combined_content, used_positions

        # Secondary: try using spine item ids to resolve positions.
        item_positions = self._positions_from_item_ids(
            book, nav_entry.get("spine_item_ids", [])
        )
        for pos in item_positions:
            html = self._get_single_spine_content(book, pos, filename)
            if html:
                combined_content += html
                used_positions.append(pos)

        if combined_content:
            return combined_content, used_positions

        # Final attempt: resolve a specific item by href/nav id.
        candidate_item = self._find_candidate_item(book, nav_entry, requested_nav_id)
        if self._is_document_item(candidate_item):
            html = self._get_processed_item_content(candidate_item, filename)
            if html:
                combined_content = html
                used_positions = self._positions_from_item_ids(
                    book, [candidate_item.get_id()]
                )
                return combined_content, used_positions

        return "", []

    def _legacy_nav_fallback(
        self, book, nav_id: str, filename: str
    ) -> Tuple[str, List[int]]:
        """Fallback that mimics the legacy behaviour for unexpected nav ids."""
        if not nav_id:
            return "", []

        base_nav_id = nav_id.split("#", 1)[0]

        # Try to find an item by exact id first.
        item = book.get_item_with_id(base_nav_id)
        if not self._is_document_item(item):
            search_key = base_nav_id.replace(".", "_").replace("/", "_")
            for doc_item in book.get_items():
                if not self._is_document_item(doc_item):
                    continue
                if (
                    base_nav_id in doc_item.get_name()
                    or search_key
                    == doc_item.get_name().replace(".", "_").replace("/", "_")
                ):
                    item = doc_item
                    break

        if self._is_document_item(item):
            content = self._get_processed_item_content(item, filename)
            positions = self._positions_from_item_ids(book, [item.get_id()])
            return content, positions

        return "", []

    def _resolve_navigation_entry(
        self, nav_id: str, navigation_index: Dict[str, Any], book
    ) -> Optional[Dict[str, Any]]:
        nav_lookup = navigation_index.get("by_id", {})
        flat_nav = navigation_index.get("flat", [])

        if nav_id in nav_lookup:
            return nav_lookup[nav_id]

        base_nav_id = nav_id.split("#", 1)[0]
        if base_nav_id in nav_lookup:
            return nav_lookup[base_nav_id]

        sanitized_candidate = base_nav_id.replace("/", "_").replace(".", "_")
        if sanitized_candidate in nav_lookup:
            return nav_lookup[sanitized_candidate]

        # Old progress entries stored spine item ids; map those back to nav entries.
        for entry in flat_nav:
            if nav_id in entry.get("spine_item_ids", []):
                return entry

        if nav_id == "start" and flat_nav:
            return flat_nav[0]

        return None

    def _adjacent_entry(
        self, flat_nav: List[Dict[str, Any]], current_entry: Dict[str, Any], offset: int
    ) -> Optional[Dict[str, Any]]:
        if not flat_nav or offset == 0:
            return None

        current_id = current_entry.get("id")
        current_index = None
        for idx, entry in enumerate(flat_nav):
            if entry.get("id") == current_id:
                current_index = idx
                break

        if current_index is None:
            return None

        next_index = current_index + offset
        while 0 <= next_index < len(flat_nav):
            candidate = flat_nav[next_index]
            if self._entry_has_content(candidate):
                return candidate
            next_index += offset

        return None

    def _entry_has_content(self, entry: Dict[str, Any]) -> bool:
        return bool(entry.get("spine_positions")) or entry.get("child_count", 0) == 0

    def _count_readable_sections(self, flat_nav: List[Dict[str, Any]]) -> int:
        return sum(1 for entry in flat_nav if self._entry_has_content(entry))

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
        Uses robust URL helper for proper encoding and security
        """
        # Pattern to match img src attributes
        img_pattern = r'<img([^>]*?)src\s*=\s*["\']([^"\']*?)["\']([^>]*?)>'

        def replace_img_src(match):
            before_src = match.group(1)
            src_path = match.group(2)
            after_src = match.group(3)

            # Skip if already an absolute URL
            if src_path.startswith(("http://", "https://", "data:", "blob:")):
                return match.group(0)

            # Use robust URL helper to build the image URL
            new_src = EPUBURLHelper.build_image_url(self.base_url, filename, src_path)

            # If URL building failed, keep original
            if not new_src:
                return match.group(0)

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

    def _get_processed_item_content(self, item, filename: str) -> str:
        if not self._is_document_item(item):
            return ""

        try:
            raw_content = item.get_content().decode("utf-8")
        except Exception:
            return ""

        sanitized_content = self._sanitize_html(raw_content)
        return self._rewrite_image_paths(sanitized_content, filename)

    def _positions_from_item_ids(self, book, item_ids: List[str]) -> List[int]:
        if not item_ids:
            return []

        id_set = {item_id for item_id in item_ids if item_id}
        positions: List[int] = []
        for idx, (spine_item_id, _) in enumerate(book.spine):
            if spine_item_id in id_set:
                positions.append(idx)
        return sorted(set(positions))

    def _find_candidate_item(
        self, book, nav_entry: Dict[str, Any], requested_nav_id: str
    ):
        candidates: List[str] = []
        candidates.extend(nav_entry.get("spine_item_ids", []) or [])

        href = nav_entry.get("href") or ""
        if href:
            candidates.append(href.split("#", 1)[0])

        base_nav_id = requested_nav_id.split("#", 1)[0]
        candidates.append(base_nav_id)
        candidates.append(base_nav_id.replace("/", "_").replace(".", "_"))

        for candidate in candidates:
            if not candidate:
                continue
            item = book.get_item_with_id(candidate)
            if self._is_document_item(item):
                return item

        # Fallback: try matching by file name
        name_candidates = [href.split("#", 1)[0], base_nav_id]
        for item in book.get_items():
            if not self._is_document_item(item):
                continue
            item_name = item.get_name()
            for candidate in name_candidates:
                if candidate and (
                    item_name == candidate or item_name.endswith(candidate)
                ):
                    return item

        return None

    def _resolve_entry_title(self, nav_entry: Dict[str, Any], book) -> str:
        title = nav_entry.get("title")
        if title:
            return str(title)

        for item_id in nav_entry.get("spine_item_ids", []) or []:
            item = book.get_item_with_id(item_id)
            if self._is_document_item(item):
                return (
                    item.get_name()
                    .replace(".xhtml", "")
                    .replace(".html", "")
                    .replace("_", " ")
                    .title()
                )

        return nav_entry.get("id", "")

    def _is_document_item(self, item) -> bool:
        if not item:
            return False

        try:
            item_type = item.get_type()
        except Exception:
            return False

        doc_type = getattr(ebooklib, "ITEM_DOCUMENT", None)
        return item_type in {doc_type, 0}
