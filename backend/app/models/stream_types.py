"""
Type definitions for structured LLM streaming.

Provides strong typing for thinking/response separation during streaming.
"""

from typing import Literal, Optional, TypedDict


class StreamMetadata(TypedDict, total=False):
    """Metadata about the stream state"""

    thinking_started: bool
    thinking_complete: bool


class StreamChunk(TypedDict):
    """
    A single chunk of structured stream data.

    Fields:
        type: The type of content in this chunk
        content: The actual text content (optional for metadata-only chunks)
        metadata: State information about thinking stream
    """

    type: Literal["thinking", "response", "metadata"]
    content: Optional[str]
    metadata: StreamMetadata


# Type alias for the stream generator
StreamGenerator = "AsyncGenerator[StreamChunk, None]"
