"""
EPUB Word Count Service Module

This module provides word count extraction functionality for EPUB files.
It calculates word counts per navigation section and total word count
for the entire book, storing these in the nav_metadata structure.
"""

import logging
import re
from typing import Any

import ebooklib
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EPUBWordCountService:
    """
    Service for extracting word counts from EPUB content.

    Calculates word counts for each navigation section by parsing HTML content
    and counting words. Results are stored in nav_metadata for use in
    reading statistics tracking.
    """

    def extract_word_counts(
        self, book: ebooklib.epub.EpubBook, nav_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Extract word counts for all sections and update nav_metadata.

        Args:
            book: The ebooklib EpubBook object
            nav_metadata: The navigation metadata dict containing all_sections

        Returns:
            Updated nav_metadata with word_count fields added to each section
            and total_word_count at the top level
        """
        if not nav_metadata or "all_sections" not in nav_metadata:
            logger.warning("nav_metadata missing or has no all_sections")
            return nav_metadata

        # Build href -> content mapping for efficient lookups
        content_map = self._build_content_map(book)

        # Build id -> href mapping from the EPUB book's navigation
        id_to_href = self._build_id_to_href_mapping(book)

        total_words = 0
        sections_processed = 0

        for section in nav_metadata["all_sections"]:
            # Try to get href from section first, otherwise look it up by id
            href = section.get("href", "")

            if not href:
                # Try to find href by section id
                section_id = section.get("id", "")
                href = id_to_href.get(section_id, "")

            if not href:
                section["word_count"] = 0
                continue

            # Store the href in the section for future use
            section["href"] = href

            # Remove fragment identifier for content lookup
            base_href = href.split("#")[0] if "#" in href else href

            word_count = self._get_word_count_for_href(base_href, content_map)
            section["word_count"] = word_count
            total_words += word_count
            sections_processed += 1

        nav_metadata["total_word_count"] = total_words

        logger.info(
            f"Extracted word counts: {sections_processed} sections, "
            f"{total_words} total words"
        )

        return nav_metadata

    def needs_word_count(self, nav_metadata: dict[str, Any] | None) -> bool:
        """
        Check if word counts need to be extracted.

        Args:
            nav_metadata: The navigation metadata dict

        Returns:
            True if word counts have not been extracted yet
        """
        if not nav_metadata:
            return True
        return nav_metadata.get("total_word_count") is None

    def _build_id_to_href_mapping(self, book: ebooklib.epub.EpubBook) -> dict[str, str]:
        """
        Build a mapping from navigation id to href by parsing the EPUB's TOC.

        Args:
            book: The ebooklib EpubBook object

        Returns:
            Dict mapping navigation id to href
        """
        id_to_href: dict[str, str] = {}

        # Process TOC if available
        if hasattr(book, "toc") and book.toc:
            self._process_toc_for_href_mapping(book.toc, id_to_href, book)

        # Also map spine items by their id
        for item_id, _ in book.spine:
            item = book.get_item_with_id(item_id)
            if self._is_document_item(item):
                name = item.get_name()
                # Map by spine item id
                id_to_href[item_id] = name
                # Also map by id#fragment pattern
                if "#" not in item_id:
                    id_to_href[f"{item_id}#"] = name

        return id_to_href

    def _process_toc_for_href_mapping(
        self, toc_items, id_to_href: dict[str, str], book
    ) -> None:
        """
        Recursively process TOC items to build id -> href mapping.

        Args:
            toc_items: TOC items from the EPUB
            id_to_href: Dict to populate with id -> href mappings
            book: The ebooklib EpubBook object
        """
        for item in toc_items:
            if isinstance(item, tuple):
                # Nested section
                section, children = item
                if hasattr(section, "href"):
                    nav_id = self._get_nav_id_from_href(section.href, book)
                    id_to_href[nav_id] = section.href
                self._process_toc_for_href_mapping(children, id_to_href, book)
            elif hasattr(item, "href"):
                # Direct navigation item
                nav_id = self._get_nav_id_from_href(item.href, book)
                id_to_href[nav_id] = item.href

    def _get_nav_id_from_href(self, href: str, book) -> str:
        """
        Convert href to navigation ID (same logic as navigation service).

        Args:
            href: The href to convert
            book: The ebooklib EpubBook object

        Returns:
            Navigation ID string
        """
        # Split href into base and fragment
        if "#" in href:
            base_href, fragment = href.split("#", 1)
        else:
            base_href = href
            fragment = None

        # Find the item in the book
        spine_item_id = None
        for item in book.get_items():
            if not self._is_document_item(item):
                continue
            name = item.get_name()
            if name == base_href or name.endswith(base_href):
                spine_item_id = item.get_id()
                break

        # Create unique ID by combining spine item ID with fragment
        if spine_item_id:
            if fragment:
                return f"{spine_item_id}#{fragment}"
            else:
                return spine_item_id
        else:
            # Fallback: use href as ID (cleaned but preserving fragments)
            return href.replace("/", "_").replace(".", "_")

    def _build_content_map(self, book: ebooklib.epub.EpubBook) -> dict[str, bytes]:
        """
        Build a mapping from href to content for all document items.

        Args:
            book: The ebooklib EpubBook object

        Returns:
            Dict mapping href (file name) to raw content bytes
        """
        content_map: dict[str, bytes] = {}

        for item in book.get_items():
            if not self._is_document_item(item):
                continue

            try:
                name = item.get_name()
                content = item.get_content()
                content_map[name] = content
            except Exception as e:
                logger.warning(f"Failed to get content for item: {e}")

        return content_map

    def _get_word_count_for_href(self, href: str, content_map: dict[str, bytes]) -> int:
        """
        Get word count for a specific href.

        Args:
            href: The href to look up (without fragment)
            content_map: The content map from _build_content_map

        Returns:
            Word count for the href's content, or 0 if not found
        """
        content = content_map.get(href)

        if content is None:
            # Try partial matching, but require path boundary anchor
            # to avoid spurious matches like "chapter1.html" matching "ter1.html"
            for key in content_map:
                if self._is_path_suffix_match(key, href) or self._is_path_suffix_match(
                    href, key
                ):
                    content = content_map[key]
                    break

        if content is None:
            return 0

        return self._count_words(content)

    def _count_words(self, html_content: bytes) -> int:
        """
        Extract text from HTML and count words.

        Args:
            html_content: Raw HTML content as bytes

        Returns:
            Number of words in the content
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style"]):
                element.decompose()

            text = soup.get_text(separator=" ")

            # Count words using regex to handle various whitespace
            words = re.findall(r"\b\w+\b", text)
            return len(words)

        except Exception as e:
            logger.warning(f"Failed to count words: {e}")
            return 0

    def _is_path_suffix_match(self, full_path: str, suffix: str) -> bool:
        """
        Check if suffix is a valid path suffix of full_path.

        A valid suffix match requires the match to be anchored at a path boundary,
        meaning the character before the suffix must be '/' or the strings must
        be exactly equal. This prevents spurious matches like "chapter1.html"
        matching "ter1.html".

        Args:
            full_path: The full path to check against
            suffix: The suffix to look for

        Returns:
            True if suffix is a valid path suffix of full_path
        """
        if full_path == suffix:
            return True

        if not full_path.endswith(suffix):
            return False

        # Check that the character before the suffix is a path separator
        prefix_len = len(full_path) - len(suffix)
        return full_path[prefix_len - 1] == "/"

    def _is_document_item(self, item) -> bool:
        """Check if an item is a document item (HTML/XHTML content)."""
        if not item:
            return False

        try:
            item_type = item.get_type()
        except Exception:
            return False

        doc_type = getattr(ebooklib, "ITEM_DOCUMENT", None)
        return item_type in {doc_type, 0}
