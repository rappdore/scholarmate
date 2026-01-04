"""
Unit tests for EPUBChatContextService.

Tests cover:
- Context extraction at different scroll positions
- Text extraction around reading position
- Surrounding context for new chats
- Edge cases (first/last section, short sections)
- LLM formatting
"""

from unittest.mock import Mock

import pytest

from app.services.epub.epub_chat_context_service import (
    EPUBChatContext,
    EPUBChatContextService,
)


class TestEPUBChatContext:
    """Tests for EPUBChatContext dataclass and format_for_llm method."""

    def test_format_for_llm_current_only(self):
        """Test formatting with only current section (ongoing chat)."""
        context = EPUBChatContext(
            current_section_text="This is the current section content.",
            current_section_title="Chapter 1",
            current_nav_id="chapter-1",
            scroll_position_used=0.0,
        )

        formatted = context.format_for_llm()

        assert "[Current section: Chapter 1]" in formatted
        assert "This is the current section content." in formatted
        assert "[Previous section:" not in formatted
        assert "[Next section:" not in formatted

    def test_format_for_llm_with_scroll_position(self):
        """Test formatting includes scroll position indicator."""
        context = EPUBChatContext(
            current_section_text="Content here.",
            current_section_title="Chapter 2",
            current_nav_id="chapter-2",
            scroll_position_used=0.75,
        )

        formatted = context.format_for_llm()

        assert "(reading position: ~75%)" in formatted

    def test_format_for_llm_no_position_at_zero(self):
        """Test no position indicator when at the start."""
        context = EPUBChatContext(
            current_section_text="Content here.",
            current_section_title="Chapter 1",
            current_nav_id="chapter-1",
            scroll_position_used=0.0,
        )

        formatted = context.format_for_llm()

        assert "(reading position:" not in formatted

    def test_format_for_llm_with_surrounding_context(self):
        """Test formatting with previous and next sections (new chat)."""
        context = EPUBChatContext(
            current_section_text="Current content.",
            current_section_title="Chapter 2",
            current_nav_id="chapter-2",
            previous_section_text="End of previous chapter.",
            previous_section_title="Chapter 1",
            next_section_text="Beginning of next chapter.",
            next_section_title="Chapter 3",
            scroll_position_used=0.5,
        )

        formatted = context.format_for_llm()

        assert "[Previous section: Chapter 1]" in formatted
        assert "...End of previous chapter." in formatted
        assert "[Current section: Chapter 2" in formatted
        assert "Current content." in formatted
        assert "[Next section: Chapter 3]" in formatted
        assert "Beginning of next chapter...." in formatted

    def test_format_for_llm_missing_titles(self):
        """Test formatting uses fallback titles when not provided."""
        context = EPUBChatContext(
            current_section_text="Content.",
            current_section_title="",  # Empty title
            current_nav_id="nav-1",
            previous_section_text="Previous.",
            previous_section_title=None,
            next_section_text="Next.",
            next_section_title=None,
        )

        formatted = context.format_for_llm()

        assert "[Current section: Current section]" in formatted
        assert "[Previous section: Previous section]" in formatted
        assert "[Next section: Next section]" in formatted


class TestEPUBChatContextService:
    """Tests for EPUBChatContextService."""

    @pytest.fixture
    def mock_content_processor(self):
        """Create a mock content processor."""
        processor = Mock()
        return processor

    @pytest.fixture
    def service(self, mock_content_processor):
        """Create service with mock processor."""
        return EPUBChatContextService(mock_content_processor)

    def test_extract_text_around_position_short_text(self, service):
        """Test extraction when text is shorter than limit."""
        text = "Short text."
        result, position = service._extract_text_around_position(text, 0.5, 2000)

        assert result == text
        assert position == 5  # 50% of 11 chars

    def test_extract_text_around_position_at_start(self, service):
        """Test extraction at start of text."""
        text = "A" * 5000
        result, position = service._extract_text_around_position(text, 0.0, 1000)

        assert len(result) == 1003  # 1000 + "..."
        assert result.startswith("A")
        assert result.endswith("...")
        assert position == 0

    def test_extract_text_around_position_at_middle(self, service):
        """Test extraction at middle of text."""
        text = "A" * 5000
        result, position = service._extract_text_around_position(text, 0.5, 1000)

        # Should have ellipsis on both ends
        assert result.startswith("...")
        assert result.endswith("...")
        assert position == 2500

    def test_extract_text_around_position_at_end(self, service):
        """Test extraction at end of text."""
        text = "A" * 5000
        result, position = service._extract_text_around_position(text, 1.0, 1000)

        assert result.startswith("...")
        assert not result.endswith("...")  # No ellipsis at actual end
        assert position == 5000

    def test_extract_text_around_position_empty_text(self, service):
        """Test extraction with empty text."""
        result, position = service._extract_text_around_position("", 0.5, 1000)

        assert result == ""
        assert position == 0

    def test_get_chat_context_ongoing_chat(self, service, mock_content_processor):
        """Test context extraction for ongoing chat (no surrounding context)."""
        mock_content_processor.get_content_by_nav_id.return_value = {
            "content": "<p>This is the section content.</p>",
            "title": "Test Section",
            "previous_nav_id": "prev-1",
            "next_nav_id": "next-1",
        }

        mock_book = Mock()
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="current-1",
            scroll_position=0.0,
            is_new_chat=False,
        )

        assert context.current_section_title == "Test Section"
        assert "section content" in context.current_section_text
        assert context.previous_section_text is None
        assert context.next_section_text is None

    def test_get_chat_context_new_chat(self, service, mock_content_processor):
        """Test context extraction for new chat (includes surrounding context)."""

        def mock_get_content(book, nav_id, filename):
            if nav_id == "current-1":
                return {
                    "content": "<p>Current section content.</p>",
                    "title": "Current Section",
                    "previous_nav_id": "prev-1",
                    "next_nav_id": "next-1",
                }
            elif nav_id == "prev-1":
                return {
                    "content": "<p>Previous section content.</p>",
                    "title": "Previous Section",
                    "previous_nav_id": None,
                    "next_nav_id": "current-1",
                }
            elif nav_id == "next-1":
                return {
                    "content": "<p>Next section content.</p>",
                    "title": "Next Section",
                    "previous_nav_id": "current-1",
                    "next_nav_id": None,
                }

        mock_content_processor.get_content_by_nav_id.side_effect = mock_get_content

        mock_book = Mock()
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="current-1",
            scroll_position=0.5,
            is_new_chat=True,
        )

        assert context.current_section_title == "Current Section"
        assert context.previous_section_title == "Previous Section"
        assert context.next_section_title == "Next Section"
        assert "Previous section content" in context.previous_section_text
        assert "Next section content" in context.next_section_text

    def test_get_chat_context_first_section(self, service, mock_content_processor):
        """Test context extraction for first section (no previous)."""
        mock_content_processor.get_content_by_nav_id.return_value = {
            "content": "<p>First section.</p>",
            "title": "First Section",
            "previous_nav_id": None,  # No previous
            "next_nav_id": "next-1",
        }

        mock_book = Mock()
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="first-1",
            scroll_position=0.0,
            is_new_chat=True,
        )

        assert context.previous_section_text is None
        # Note: next section would require additional mock setup

    def test_get_chat_context_invalid_nav_id(self, service, mock_content_processor):
        """Test handling of invalid nav_id."""
        mock_content_processor.get_content_by_nav_id.side_effect = ValueError(
            "Section not found"
        )

        mock_book = Mock()
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="invalid-id",
            scroll_position=0.0,
            is_new_chat=False,
        )

        assert context.current_section_text == "[Section not found]"
        assert context.current_section_title == "Unknown"

    def test_get_chat_context_clamps_scroll_position(
        self, service, mock_content_processor
    ):
        """Test that scroll position is clamped to valid range."""
        mock_content_processor.get_content_by_nav_id.return_value = {
            "content": "<p>Content.</p>",
            "title": "Section",
            "previous_nav_id": None,
            "next_nav_id": None,
        }

        mock_book = Mock()

        # Test value > 1.0
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="section-1",
            scroll_position=1.5,
            is_new_chat=False,
        )
        assert context.scroll_position_used == 1.0

        # Test value < 0.0
        context = service.get_chat_context(
            book=mock_book,
            filename="test.epub",
            nav_id="section-1",
            scroll_position=-0.5,
            is_new_chat=False,
        )
        assert context.scroll_position_used == 0.0

    def test_extract_text_from_html(self, service):
        """Test HTML to plain text extraction."""
        html = "<p>Hello <strong>world</strong>!</p><p>Second paragraph.</p>"
        result = service._extract_text_from_html(html)

        assert "Hello" in result
        assert "world" in result
        assert "Second paragraph." in result
        assert "<p>" not in result
        assert "<strong>" not in result

    def test_extract_text_from_html_empty(self, service):
        """Test HTML extraction with empty input."""
        assert service._extract_text_from_html("") == ""
        assert service._extract_text_from_html(None) == ""


class TestIntegration:
    """Integration tests with realistic scenarios."""

    @pytest.fixture
    def mock_content_processor(self):
        """Create a mock with realistic content."""
        processor = Mock()

        # Simulate a book with 3 chapters
        def mock_get_content(book, nav_id, filename):
            chapters = {
                "intro": {
                    "content": "<h1>Introduction</h1><p>"
                    + "This is the introduction. " * 100
                    + "</p>",
                    "title": "Introduction",
                    "previous_nav_id": None,
                    "next_nav_id": "chapter-1",
                },
                "chapter-1": {
                    "content": "<h1>Chapter 1</h1><p>"
                    + "This is chapter one content. " * 200
                    + "</p>",
                    "title": "Chapter 1: The Beginning",
                    "previous_nav_id": "intro",
                    "next_nav_id": "chapter-2",
                },
                "chapter-2": {
                    "content": "<h1>Chapter 2</h1><p>"
                    + "This is chapter two content. " * 150
                    + "</p>",
                    "title": "Chapter 2: The Middle",
                    "previous_nav_id": "chapter-1",
                    "next_nav_id": None,
                },
            }
            if nav_id not in chapters:
                raise ValueError(f"Section {nav_id} not found")
            return chapters[nav_id]

        processor.get_content_by_nav_id.side_effect = mock_get_content
        return processor

    def test_realistic_new_chat_scenario(self, mock_content_processor):
        """Test a realistic new chat in the middle of a book."""
        service = EPUBChatContextService(mock_content_processor)
        mock_book = Mock()

        # User is 60% through Chapter 1
        context = service.get_chat_context(
            book=mock_book,
            filename="mybook.epub",
            nav_id="chapter-1",
            scroll_position=0.6,
            is_new_chat=True,
        )

        # Verify current section
        assert context.current_section_title == "Chapter 1: The Beginning"
        assert context.scroll_position_used == 0.6
        assert "chapter one content" in context.current_section_text

        # Verify surrounding context is included
        assert context.previous_section_title == "Introduction"
        assert context.next_section_title == "Chapter 2: The Middle"

        # Verify LLM formatting
        formatted = context.format_for_llm()
        assert "[Previous section: Introduction]" in formatted
        assert "(reading position: ~60%)" in formatted
        assert "[Next section: Chapter 2: The Middle]" in formatted

    def test_realistic_ongoing_chat_scenario(self, mock_content_processor):
        """Test a realistic ongoing chat (no surrounding context needed)."""
        service = EPUBChatContextService(mock_content_processor)
        mock_book = Mock()

        # User continues chatting at 80% through Chapter 1
        context = service.get_chat_context(
            book=mock_book,
            filename="mybook.epub",
            nav_id="chapter-1",
            scroll_position=0.8,
            is_new_chat=False,
        )

        # Verify only current section
        assert context.current_section_title == "Chapter 1: The Beginning"
        assert context.previous_section_text is None
        assert context.next_section_text is None

        # Verify LLM formatting is simpler
        formatted = context.format_for_llm()
        assert "[Previous section:" not in formatted
        assert "[Next section:" not in formatted
        assert "(reading position: ~80%)" in formatted
