"""
Stream parser for handling LLM thinking blocks.

This service processes LLM output streams to detect and separate
<think> blocks from regular response content. Handles tags that
may be split across multiple chunks.

Model Assumptions:
- At most ONE thinking block per response
- If present, thinking block appears FIRST: <think>...</think>response
- No nested or self-closing tags
"""

import logging
import re
from enum import Enum
from typing import AsyncGenerator, Literal

from app.models.stream_types import StreamChunk, StreamMetadata

logger = logging.getLogger(__name__)


class StreamState(Enum):
    """Parser state machine states"""

    BEFORE_THINK = "before_think"
    INSIDE_THINK = "inside_think"
    AFTER_THINK = "after_think"


class ThinkingStreamParser:
    """
    Parse LLM stream to detect <think> tags and structure output.

    Handles:
    - Tags split across chunks
    - Case-insensitive tag matching
    - Content before, inside, and after thinking blocks
    - Single thinking block (as per model assumptions)

    Usage:
        parser = ThinkingStreamParser()
        async for chunk in llm_stream:
            async for structured_data in parser.process_chunk(chunk):
                yield structured_data
        async for final_data in parser.finalize():
            yield final_data
    """

    # Pre-compiled regex patterns for performance
    _THINK_OPEN_PATTERN = re.compile(r"<think>", re.IGNORECASE)
    _THINK_CLOSE_PATTERN = re.compile(r"</think>", re.IGNORECASE)

    def __init__(self):
        """Initialize parser with clean state"""
        self.state = StreamState.BEFORE_THINK
        self.buffer = ""
        self.thinking_started = False
        self.thinking_complete = False

    def reset(self):
        """Reset parser state for new stream"""
        self.__init__()

    async def process_chunk(self, chunk: str) -> AsyncGenerator[StreamChunk, None]:
        """
        Process a chunk from LLM stream.

        Args:
            chunk: Raw text chunk from LLM

        Yields:
            Structured data dictionaries with type and content

        Example output:
            {"type": "thinking", "content": "reasoning...", "metadata": {...}}
            {"type": "response", "content": "answer text", "metadata": {...}}
            {"type": "metadata", "content": None, "metadata": {"thinking_complete": True}}
        """
        self.buffer += chunk

        while True:
            buffer_len_before = len(self.buffer)

            if self.state == StreamState.BEFORE_THINK:
                async for chunk_data in self._process_before_think():
                    yield chunk_data

            elif self.state == StreamState.INSIDE_THINK:
                async for chunk_data in self._process_inside_think():
                    yield chunk_data

            elif self.state == StreamState.AFTER_THINK:
                async for chunk_data in self._process_after_think():
                    yield chunk_data
                break

            # Check if we made progress; if not, wait for more data
            if len(self.buffer) == buffer_len_before:
                break

    async def _process_before_think(self) -> AsyncGenerator[StreamChunk, None]:
        """Process content before <think> tag appears"""

        # Look for <think> opening tag (case-insensitive)
        open_match = self._THINK_OPEN_PATTERN.search(self.buffer)

        # TODO: TEMPORARY FIX - Replace with config-based solution later
        # Check for orphaned </think> tag (closing tag without opening tag)
        # This happens with some models that don't emit <think> opening tags
        # IMPORTANT: Only treat as orphaned if we found </think> BEFORE any <think>
        close_match = self._THINK_CLOSE_PATTERN.search(self.buffer)

        if close_match and (not open_match or close_match.start() < open_match.start()):
            # Found </think> before any <think> (orphaned closing tag)
            # Send everything before it as response, then insert <hr/> divider
            before_close = self.buffer[: close_match.start()]
            if before_close.strip():
                yield StreamChunk(
                    type="response",
                    content=before_close,
                    metadata=StreamMetadata(
                        thinking_started=False, thinking_complete=False
                    ),
                )
                logger.warning(
                    f"[ThinkingParser] Orphaned </think> detected! "
                    f"Sent {len(before_close)} chars before tag. "
                    f"Consider using 'always_starts_with_thinking' config flag."
                )

            # Insert horizontal rule as visual separator with extra spacing
            yield StreamChunk(
                type="response",
                content="\n\n---\n\n&nbsp;\n\n",
                metadata=StreamMetadata(
                    thinking_started=False, thinking_complete=False
                ),
            )
            logger.info(
                "[ThinkingParser] Inserted <hr/> divider for orphaned </think> tag"
            )

            # Move past the </think> tag and continue as response
            self.buffer = self.buffer[close_match.end() :]
            # Stay in BEFORE_THINK state (treat rest as normal response)
            return

        if open_match:
            # Send any content before <think> as response
            before = self.buffer[: open_match.start()]
            if before.strip():
                yield StreamChunk(
                    type="response",
                    content=before,
                    metadata=StreamMetadata(
                        thinking_started=False, thinking_complete=False
                    ),
                )
                logger.debug(
                    f"[ThinkingParser] Sent {len(before)} chars before <think>"
                )

            # Move past the <think> tag
            self.buffer = self.buffer[open_match.end() :]
            self.state = StreamState.INSIDE_THINK
            self.thinking_started = True

            # Signal thinking started
            yield StreamChunk(
                type="metadata",
                content=None,
                metadata=StreamMetadata(thinking_started=True, thinking_complete=False),
            )
            logger.info("[ThinkingParser] Detected <think> tag, entering thinking mode")
        else:
            # No tags yet, but might be split across chunks
            # Keep last 8 chars in buffer (max length of "</think>")
            # This handles both <think> (7 chars) and </think> (8 chars) being split
            if len(self.buffer) > 8:
                to_send = self.buffer[:-8]
                self.buffer = self.buffer[-8:]
                if to_send.strip():
                    yield StreamChunk(
                        type="response",
                        content=to_send,
                        metadata=StreamMetadata(
                            thinking_started=False, thinking_complete=False
                        ),
                    )
                    logger.debug(
                        f"[ThinkingParser] Sent {len(to_send)} chars (no <think> yet)"
                    )

    async def _process_inside_think(self) -> AsyncGenerator[StreamChunk, None]:
        """Process content inside <think>...</think> block"""
        # Look for </think> closing tag (case-insensitive)
        match = self._THINK_CLOSE_PATTERN.search(self.buffer)

        if match:
            # Send thinking content
            thinking_content = self.buffer[: match.start()]
            if thinking_content:  # Allow empty thinking blocks
                yield StreamChunk(
                    type="thinking",
                    content=thinking_content,
                    metadata=StreamMetadata(
                        thinking_started=True, thinking_complete=False
                    ),
                )
                logger.debug(
                    f"[ThinkingParser] Sent {len(thinking_content)} chars of thinking"
                )

            # Move past the </think> tag
            self.buffer = self.buffer[match.end() :]
            self.state = StreamState.AFTER_THINK
            self.thinking_complete = True

            # Signal thinking complete
            yield StreamChunk(
                type="metadata",
                content=None,
                metadata=StreamMetadata(thinking_started=True, thinking_complete=True),
            )
            logger.info("[ThinkingParser] Detected </think> tag, thinking complete")
        else:
            # No closing tag yet, might be split across chunks
            # Keep last 8 chars in buffer (length of "</think>")
            if len(self.buffer) > 8:
                to_send = self.buffer[:-8]
                self.buffer = self.buffer[-8:]
                if to_send:
                    yield StreamChunk(
                        type="thinking",
                        content=to_send,
                        metadata=StreamMetadata(
                            thinking_started=True, thinking_complete=False
                        ),
                    )
                    logger.debug(
                        f"[ThinkingParser] Sent {len(to_send)} chars of thinking (streaming)"
                    )

    async def _process_after_think(self) -> AsyncGenerator[StreamChunk, None]:
        """Process content after </think> tag"""
        # Everything after </think> is response content
        # Based on model assumptions, there will be no more <think> tags
        if self.buffer:
            yield StreamChunk(
                type="response",
                content=self.buffer,
                metadata=StreamMetadata(thinking_started=True, thinking_complete=True),
            )
            logger.debug(
                f"[ThinkingParser] Sent {len(self.buffer)} chars of response after thinking"
            )
            self.buffer = ""

    async def finalize(self) -> AsyncGenerator[StreamChunk, None]:
        """
        Call when stream ends to flush remaining buffer.

        Yields:
            Any remaining buffered content with appropriate type
        """
        if self.buffer:
            chunk_type: Literal["thinking", "response"] = (
                "thinking" if self.state == StreamState.INSIDE_THINK else "response"
            )
            yield StreamChunk(
                type=chunk_type,
                content=self.buffer,
                metadata=StreamMetadata(
                    thinking_started=self.thinking_started,
                    thinking_complete=self.thinking_complete,
                ),
            )
            logger.info(
                f"[ThinkingParser] Finalized with state={self.state.value}, "
                f"flushed {len(self.buffer)} chars as {chunk_type}"
            )
            self.buffer = ""
