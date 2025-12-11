"""
Unit tests for ThinkingStreamParser.

Tests cover:
- Complete tags in single chunk
- Tags split across chunks
- Empty thinking blocks
- No thinking blocks
- Content before/after thinking
- Case-insensitive tags
- Edge cases with buffer management
"""

import pytest

from app.services.stream_parser import StreamState, ThinkingStreamParser


@pytest.mark.asyncio
async def test_complete_thinking_block_single_chunk():
    """Test complete <think> block in one chunk"""
    parser = ThinkingStreamParser()
    input_text = "<think>reasoning here</think>final answer"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # Should have: metadata(started) -> thinking content -> metadata(complete) -> response
    assert len(results) >= 3

    # Find metadata chunks
    metadata_chunks = [r for r in results if r["type"] == "metadata"]
    assert len(metadata_chunks) == 2
    assert metadata_chunks[0]["metadata"]["thinking_started"] is True
    assert metadata_chunks[1]["metadata"]["thinking_complete"] is True

    # Find thinking content
    thinking_chunks = [r for r in results if r["type"] == "thinking"]
    assert len(thinking_chunks) >= 1
    thinking_text = "".join([c["content"] for c in thinking_chunks])
    assert "reasoning here" in thinking_text

    # Find response content
    response_chunks = [r for r in results if r["type"] == "response"]
    response_text = "".join([c["content"] for c in response_chunks if c["content"]])
    assert "final answer" in response_text


@pytest.mark.asyncio
async def test_thinking_tag_split_across_chunks():
    """Test <think> tag split: '<thi' + 'nk>content</think>'"""
    parser = ThinkingStreamParser()

    results = []
    async for chunk in parser.process_chunk("<thi"):
        results.append(chunk)
    async for chunk in parser.process_chunk("nk>inside</think>"):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # Should detect thinking and content
    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    assert len(thinking_chunks) > 0
    thinking_text = "".join([c["content"] for c in thinking_chunks if c["content"]])
    assert "inside" in thinking_text


@pytest.mark.asyncio
async def test_closing_tag_split_across_chunks():
    """Test </think> tag split: '<think>content</thi' + 'nk>response'"""
    parser = ThinkingStreamParser()

    results = []
    async for chunk in parser.process_chunk("<think>content</thi"):
        results.append(chunk)
    async for chunk in parser.process_chunk("nk>response"):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    thinking_text = "".join([c["content"] for c in thinking_chunks if c["content"]])
    assert "content" in thinking_text

    response_chunks = [r for r in results if r.get("type") == "response"]
    response_text = "".join([c["content"] for c in response_chunks if c["content"]])
    assert "response" in response_text


@pytest.mark.asyncio
async def test_no_thinking_blocks():
    """Test stream without any <think> tags"""
    parser = ThinkingStreamParser()
    input_text = "This is just a regular response without thinking"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # All content should be type "response"
    response_chunks = [r for r in results if r.get("type") == "response"]
    assert len(response_chunks) >= 1

    # No thinking should have started
    assert parser.thinking_started is False
    assert parser.state == StreamState.BEFORE_THINK


@pytest.mark.asyncio
async def test_content_before_thinking():
    """Test content before <think> tag"""
    parser = ThinkingStreamParser()
    input_text = "Some preamble <think>thoughts</think>answer"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    response_chunks = [r for r in results if r.get("type") == "response"]
    assert len(response_chunks) >= 1

    # First response chunk should contain preamble
    first_response = response_chunks[0]["content"]
    assert "preamble" in first_response


@pytest.mark.asyncio
async def test_empty_thinking_block():
    """Test empty <think></think>"""
    parser = ThinkingStreamParser()
    input_text = "<think></think>response"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # Should handle gracefully
    assert parser.thinking_complete is True
    response_chunks = [r for r in results if r.get("type") == "response"]
    assert len(response_chunks) > 0


@pytest.mark.asyncio
async def test_case_insensitive_tags():
    """Test <THINK>, <Think>, etc."""
    parser = ThinkingStreamParser()
    input_text = "<THINK>thoughts</THINK>answer"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    assert len(thinking_chunks) > 0


@pytest.mark.asyncio
async def test_incomplete_thinking_at_stream_end():
    """Test stream ending before </think>"""
    parser = ThinkingStreamParser()

    results = []
    async for chunk in parser.process_chunk("<think>incomplete thinking"):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # Should still output the thinking content
    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    assert len(thinking_chunks) > 0
    assert parser.thinking_complete is False


@pytest.mark.asyncio
async def test_multiple_chunks_gradual_streaming():
    """Test realistic streaming: one word at a time"""
    parser = ThinkingStreamParser()
    chunks = ["<think>", "I ", "need ", "to ", "think", "</think>", "answer"]

    results = []
    for chunk in chunks:
        async for data in parser.process_chunk(chunk):
            results.append(data)
    async for data in parser.finalize():
        results.append(data)

    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    thinking_text = "".join([c["content"] for c in thinking_chunks if c["content"]])
    assert "need" in thinking_text
    assert "answer" not in thinking_text

    response_chunks = [r for r in results if r.get("type") == "response"]
    response_text = "".join([c["content"] for c in response_chunks if c["content"]])
    assert "answer" in response_text


@pytest.mark.asyncio
async def test_unicode_and_emoji_in_thinking():
    """Test Unicode characters and emoji in thinking content"""
    parser = ThinkingStreamParser()
    input_text = "<think>🤔 Let me think about λ-calculus</think>The answer is 42"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    thinking_text = "".join([c["content"] for c in thinking_chunks if c["content"]])
    assert "🤔" in thinking_text
    assert "λ-calculus" in thinking_text


@pytest.mark.asyncio
async def test_buffer_management_with_similar_text():
    """Test buffer doesn't get confused by text similar to tags"""
    parser = ThinkingStreamParser()
    input_text = "Let me <think about this <think>real thinking</think>answer"

    results = []
    async for chunk in parser.process_chunk(input_text):
        results.append(chunk)
    async for chunk in parser.finalize():
        results.append(chunk)

    # "Let me <think about this " should be in response (before real <think>)
    response_chunks = [r for r in results if r.get("type") == "response"]
    first_response = response_chunks[0]["content"] if response_chunks else ""
    assert "<think about this" in first_response or "about this" in first_response

    # "real thinking" should be in thinking
    thinking_chunks = [r for r in results if r.get("type") == "thinking"]
    thinking_text = "".join([c["content"] for c in thinking_chunks if c["content"]])
    assert "real thinking" in thinking_text
