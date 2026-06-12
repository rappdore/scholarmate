"""
Tests for TTSService async streaming (bug B-15a).

generate_audio_async must stream chunks as the synthesis pipeline produces
them (not collect everything first), propagate pipeline exceptions, and stop
the producer when the consumer cancels.
"""

import asyncio
import threading

import pytest

from app.services.tts_service import TTSService


@pytest.fixture
def service():
    return TTSService()


@pytest.mark.asyncio
async def test_chunks_arrive_incrementally(service, monkeypatch):
    """First chunk must be yielded before the sync generator finishes."""
    release = threading.Event()

    def fake_chunks(self, text, voice, speed):
        yield b"chunk-1"
        # Block the rest of synthesis until the test releases it. If the
        # implementation collected all chunks before yielding, the first
        # chunk could never arrive while this is blocked.
        release.wait(timeout=10)
        yield b"chunk-2"

    monkeypatch.setattr(TTSService, "_generate_audio_chunks", fake_chunks)

    gen = service.generate_audio_async("hello")
    try:
        first = await asyncio.wait_for(gen.__anext__(), timeout=5)
        assert first == b"chunk-1"
        assert not release.is_set()  # generator is still mid-synthesis

        release.set()
        second = await asyncio.wait_for(gen.__anext__(), timeout=5)
        assert second == b"chunk-2"

        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(gen.__anext__(), timeout=5)
    finally:
        release.set()
        await gen.aclose()


@pytest.mark.asyncio
async def test_all_chunks_delivered_in_order(service, monkeypatch):
    expected = [b"a", b"b", b"c"]

    def fake_chunks(self, text, voice, speed):
        yield from expected

    monkeypatch.setattr(TTSService, "_generate_audio_chunks", fake_chunks)

    received = [chunk async for chunk in service.generate_audio_async("hello")]
    assert received == expected


@pytest.mark.asyncio
async def test_pipeline_exception_propagates(service, monkeypatch):
    def fake_chunks(self, text, voice, speed):
        yield b"chunk-1"
        raise RuntimeError("synthesis exploded")

    monkeypatch.setattr(TTSService, "_generate_audio_chunks", fake_chunks)

    gen = service.generate_audio_async("hello")
    first = await asyncio.wait_for(gen.__anext__(), timeout=5)
    assert first == b"chunk-1"

    with pytest.raises(RuntimeError, match="Audio generation failed"):
        await asyncio.wait_for(gen.__anext__(), timeout=5)


@pytest.mark.asyncio
async def test_consumer_cancellation_stops_producer(service, monkeypatch):
    produced: list[int] = []
    release = threading.Event()

    def fake_chunks(self, text, voice, speed):
        produced.append(1)
        yield b"chunk-1"
        release.wait(timeout=10)
        produced.append(2)
        yield b"chunk-2"
        produced.append(3)
        yield b"chunk-3"

    monkeypatch.setattr(TTSService, "_generate_audio_chunks", fake_chunks)

    gen = service.generate_audio_async("hello")
    first = await asyncio.wait_for(gen.__anext__(), timeout=5)
    assert first == b"chunk-1"

    # Consumer goes away mid-stream.
    await gen.aclose()
    release.set()

    # Give the worker thread a moment to observe the stop signal.
    await asyncio.sleep(0.3)

    # The producer may have been mid-chunk (2), but must not keep pulling
    # further chunks (3) after the consumer cancelled.
    assert 3 not in produced


@pytest.mark.asyncio
async def test_invalid_voice_rejected(service):
    gen = service.generate_audio_async("hello", voice="not_a_voice")
    with pytest.raises(ValueError, match="Unsupported voice"):
        await gen.__anext__()


@pytest.mark.asyncio
async def test_invalid_speed_rejected(service):
    gen = service.generate_audio_async("hello", speed=99.0)
    with pytest.raises(ValueError, match="Speed too high"):
        await gen.__anext__()
