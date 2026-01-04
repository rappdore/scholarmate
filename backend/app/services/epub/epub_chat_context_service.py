"""
EPUB Chat Context Service

Extracts appropriate text context for EPUB chat based on:
- Current nav_id (which section the user is reading)
- Scroll position within section (0.0-1.0 ratio)
- Whether it's a new chat or ongoing conversation

This mirrors the PDF context extraction in dual_chat_service._get_document_context()
but is completely separate to keep EPUB-specific logic clean.
"""

import logging
from dataclasses import dataclass

from ebooklib import epub

from .epub_content_processor import EPUBContentProcessor

logger = logging.getLogger(__name__)


@dataclass
class EPUBChatContext:
    """Context extracted for EPUB chat."""

    # Current section info
    current_section_text: str
    current_section_title: str
    current_nav_id: str

    # Surrounding context (for new chats)
    previous_section_text: str | None = None
    previous_section_title: str | None = None
    next_section_text: str | None = None
    next_section_title: str | None = None

    # Metadata about extraction
    scroll_position_used: float = 0.0  # 0.0-1.0
    estimated_reading_position: int = 0  # character position in section

    def format_for_llm(self) -> str:
        """
        Format context for LLM system prompt.

        Returns a structured text representation that helps the LLM understand
        what the user is currently reading and the surrounding context.
        """
        parts = []

        # Previous section (if available)
        if self.previous_section_text:
            title = self.previous_section_title or "Previous section"
            parts.append(f"[Previous section: {title}]")
            parts.append(f"...{self.previous_section_text}")
            parts.append("")

        # Current section with reading position indicator
        position_pct = int(self.scroll_position_used * 100)
        position_indicator = (
            f" (reading position: ~{position_pct}%)" if position_pct > 0 else ""
        )
        title = self.current_section_title or "Current section"
        parts.append(f"[Current section: {title}{position_indicator}]")
        parts.append(self.current_section_text)

        # Next section (if available)
        if self.next_section_text:
            parts.append("")
            title = self.next_section_title or "Next section"
            parts.append(f"[Next section: {title}]")
            parts.append(f"{self.next_section_text}...")

        return "\n".join(parts)


class EPUBChatContextService:
    """
    Service for extracting chat context from EPUB documents.

    Provides context-aware text extraction that considers:
    - Where the user is reading (scroll position)
    - Surrounding sections (for new conversations)
    """

    def __init__(self, content_processor: EPUBContentProcessor):
        """
        Initialize the chat context service.

        Args:
            content_processor: The EPUB content processor for text extraction
        """
        self.content_processor = content_processor

    def get_chat_context(
        self,
        book: epub.EpubBook,
        filename: str,
        nav_id: str,
        scroll_position: float = 0.0,
        is_new_chat: bool = False,
        context_chars: int = 2000,
        surrounding_chars: int = 500,
    ) -> EPUBChatContext:
        """
        Extract context for EPUB chat.

        For new chats:
        - Previous section (last `surrounding_chars` chars)
        - Current section (around scroll position, `context_chars` chars)
        - Next section (first `surrounding_chars` chars)

        For ongoing chats:
        - Current section only (around scroll position)

        Args:
            book: The loaded EPUB book object
            filename: EPUB filename (needed for content processor)
            nav_id: Current navigation section ID
            scroll_position: Reading position within section (0.0-1.0)
            is_new_chat: Whether this is the first message in a conversation
            context_chars: Characters to extract around reading position
            surrounding_chars: Characters to include from adjacent sections

        Returns:
            EPUBChatContext with extracted text and metadata
        """
        # Clamp scroll position to valid range
        scroll_position = max(0.0, min(1.0, scroll_position))

        # Get current section data (includes prev/next nav_ids and title)
        try:
            section_data = self.content_processor.get_content_by_nav_id(
                book, nav_id, filename
            )
        except ValueError as e:
            logger.warning(f"Could not find nav_id '{nav_id}': {e}")
            return EPUBChatContext(
                current_section_text="[Section not found]",
                current_section_title="Unknown",
                current_nav_id=nav_id,
                scroll_position_used=scroll_position,
            )

        # Extract plain text from current section HTML
        current_full_text = self._extract_text_from_html(
            section_data.get("content", "")
        )
        current_title = section_data.get("title", "")

        # Extract text around the reading position
        current_text, reading_position = self._extract_text_around_position(
            current_full_text,
            scroll_position,
            context_chars,
        )

        # Build the context object
        context = EPUBChatContext(
            current_section_text=current_text,
            current_section_title=current_title,
            current_nav_id=nav_id,
            scroll_position_used=scroll_position,
            estimated_reading_position=reading_position,
        )

        # For new chats, include surrounding context
        if is_new_chat:
            self._add_surrounding_context(
                context=context,
                book=book,
                filename=filename,
                section_data=section_data,
                surrounding_chars=surrounding_chars,
            )

        return context

    def _extract_text_around_position(
        self,
        full_text: str,
        scroll_position: float,
        char_limit: int,
    ) -> tuple[str, int]:
        """
        Extract text centered around the estimated reading position.

        If scroll_position is 0.7 in a 10000-char section, the user is
        approximately at character 7000. We extract chars centered there.

        Args:
            full_text: Complete section text
            scroll_position: Position within section (0.0-1.0)
            char_limit: Maximum characters to extract

        Returns:
            Tuple of (extracted_text, estimated_position)
        """
        if not full_text:
            return "", 0

        text_length = len(full_text)

        # If text is shorter than limit, return it all
        if text_length <= char_limit:
            return full_text, int(text_length * scroll_position)

        # Calculate the center position based on scroll
        center_position = int(text_length * scroll_position)

        # Calculate window around center
        half_limit = char_limit // 2
        start = max(0, center_position - half_limit)
        end = min(text_length, start + char_limit)

        # Adjust start if we hit the end of text
        if end == text_length:
            start = max(0, text_length - char_limit)

        extracted = full_text[start:end]

        # Add ellipsis indicators if we're not at the boundaries
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < text_length else ""

        return f"{prefix}{extracted}{suffix}", center_position

    def _add_surrounding_context(
        self,
        context: EPUBChatContext,
        book: epub.EpubBook,
        filename: str,
        section_data: dict,
        surrounding_chars: int,
    ) -> None:
        """
        Add previous and next section context for new chats.

        Modifies the context object in place.
        """
        # Previous section
        previous_nav_id = section_data.get("previous_nav_id")
        if previous_nav_id:
            try:
                prev_data = self.content_processor.get_content_by_nav_id(
                    book, previous_nav_id, filename
                )
                prev_text = self._extract_text_from_html(prev_data.get("content", ""))

                # Take the last N characters (end of previous section)
                if prev_text:
                    context.previous_section_text = prev_text[-surrounding_chars:]
                    context.previous_section_title = prev_data.get("title", "")
            except Exception as e:
                logger.debug(f"Could not get previous section: {e}")

        # Next section
        next_nav_id = section_data.get("next_nav_id")
        if next_nav_id:
            try:
                next_data = self.content_processor.get_content_by_nav_id(
                    book, next_nav_id, filename
                )
                next_text = self._extract_text_from_html(next_data.get("content", ""))

                # Take the first N characters (beginning of next section)
                if next_text:
                    context.next_section_text = next_text[:surrounding_chars]
                    context.next_section_title = next_data.get("title", "")
            except Exception as e:
                logger.debug(f"Could not get next section: {e}")

    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract plain text from HTML content.

        This is a simple extraction - the content processor already handles
        sanitization, so we just need to strip tags.
        """
        if not html_content:
            return ""

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text
