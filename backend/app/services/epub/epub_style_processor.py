import re
from typing import Any, Dict

import ebooklib


class EPUBStyleProcessor:
    def get_epub_styles(self, book) -> Dict[str, Any]:
        """
        Extract and return CSS styles from an EPUB
        Returns sanitized CSS content for safe browser rendering
        """
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
