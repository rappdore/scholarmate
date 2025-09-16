from typing import Any, Dict, List, Optional

import ebooklib


class EPUBNavigationService:
    """Responsible for building navigation structures for EPUB files."""

    def get_navigation_tree(self, book) -> Dict[str, Any]:
        """
        Get the hierarchical navigation structure of an EPUB
        Returns full table of contents with nested structure
        """
        navigation_index = self.build_navigation_index(book)

        return {
            "navigation": navigation_index["tree"],
            "flat_navigation": navigation_index["flat"],
            "spine_length": navigation_index["spine_length"],
            "has_toc": navigation_index["has_toc"],
        }

    def _is_document_item(self, item) -> bool:
        """Some ebooklib builds report document items with type 0 instead of ITEM_DOCUMENT."""
        if not item:
            return False
        try:
            item_type = item.get_type()
        except Exception:
            return False
        return item_type in {getattr(ebooklib, "ITEM_DOCUMENT", None), 0}

    # NOTE: build_navigation_index currently unused externally but ensures Step2 can leverage.
    def build_navigation_index(self, book) -> Dict[str, Any]:
        """Build both hierarchical and flattened navigation structures."""
        nav_tree = self._build_navigation_tree(book)
        flat_items = self._flatten_navigation_tree(nav_tree, book)

        return {
            "tree": nav_tree,
            "flat": flat_items,
            "by_id": {item["id"]: item for item in flat_items},
            "spine_length": len(book.spine),
            "has_toc": bool(hasattr(book, "toc") and book.toc),
        }

    def _build_navigation_tree(self, book) -> List[Dict[str, Any]]:
        """Return the nested navigation tree, using TOC if available."""
        if hasattr(book, "toc") and book.toc:
            return self._process_toc_items(book.toc, book)

        # Fallback: create navigation from spine (reading order)
        spine_items: List[Dict[str, Any]] = []
        for index, (item_id, _) in enumerate(book.spine):
            item = book.get_item_with_id(item_id)
            if self._is_document_item(item):
                display_title = (
                    item.get_name()
                    .replace(".xhtml", "")
                    .replace(".html", "")
                    .replace("_", " ")
                    .title()
                )
                spine_items.append(
                    {
                        "id": item.get_id(),
                        "title": display_title,
                        "href": item.get_name(),
                        "level": 1,
                        "children": [],
                        "spine_positions": [index],
                    }
                )
        return spine_items

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
                        "spine_positions": self._find_spine_positions_for_nav_href(
                            section.href, book
                        ),
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
                    "spine_positions": self._find_spine_positions_for_nav_href(
                        item.href, book
                    ),
                }
                processed_items.append(processed_item)

        return processed_items

    def _flatten_navigation_tree(
        self, nav_items: List[Dict[str, Any]], book
    ) -> List[Dict[str, Any]]:
        """
        Produce a flattened, ordered list of navigation entries with metadata useful for
        precise chapter/section navigation.
        """

        flat_items: List[Dict[str, Any]] = []

        spine_length = len(book.spine)

        def walk(
            items: List[Dict[str, Any]], parent_id: Optional[str], order_start: int
        ) -> int:
            order = order_start
            for item in items:
                positions = item.get(
                    "spine_positions"
                ) or self._find_spine_positions_for_nav_item(book, item)
                positions = sorted(set(positions))
                spine_item_ids = [
                    book.spine[pos][0] for pos in positions if 0 <= pos < spine_length
                ]

                flat_items.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "href": item.get("href"),
                        "level": item.get("level", 1),
                        "parent_id": parent_id,
                        "order": order,
                        "spine_positions": positions,
                        "spine_item_ids": spine_item_ids,
                        "child_count": len(item.get("children", [])),
                    }
                )
                order += 1
                if item.get("children"):
                    order = walk(item["children"], item.get("id"), order)
            return order

        walk(nav_items, None, 0)
        return flat_items

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
                # Include fragment to ensure uniqueness
                return f"{spine_item_id}#{fragment}"
            else:
                return spine_item_id
        else:
            # Fallback: use href as ID (cleaned but preserving fragments for uniqueness)
            return href.replace("/", "_").replace(".", "_")

    def _find_spine_positions_for_nav_href(
        self, href: Optional[str], book
    ) -> List[int]:
        if not href:
            return []

        if "#" in href:
            base_href, _ = href.split("#", 1)
        else:
            base_href = href

        matches: List[int] = []
        for idx, (item_id, _) in enumerate(book.spine):
            item = book.get_item_with_id(item_id)
            if self._is_document_item(item):
                name = item.get_name()
                normalized_name = name.rsplit(".", 1)[0]
                normalized_base = base_href.rsplit(".", 1)[0]

                if (
                    name == base_href
                    or name.endswith(base_href)
                    or base_href.endswith(name)
                    or normalized_name == normalized_base
                    or normalized_name.endswith(normalized_base)
                    or normalized_base.endswith(normalized_name)
                ):
                    matches.append(idx)
        return matches

    def build_spine_to_nav_mapping(self, book) -> Dict[int, Dict[str, Any]]:
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
                    if self._is_document_item(item):
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
            if self._is_document_item(item):
                item_name = item.get_name()

                # Check if this spine item matches the navigation href
                if (
                    item_name == base_href
                    or item_name.endswith(base_href)
                    or base_href.endswith(item_name)
                ):
                    positions.append(idx)

        return positions

    def get_chapter_spine_items(
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
