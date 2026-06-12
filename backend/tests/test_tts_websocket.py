"""
Regression tests for the /ws/tts websocket loop.

After a TTS generation task finished normally, the handler cleared
`current_task` without breaking out of its inner wait loop, so the loop
condition re-evaluated `None.done()`, raised AttributeError, and the outer
handler sent a spurious error frame and closed the websocket — after every
completed playback. The connection must instead survive completion (and
task-level failure) and accept further requests.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.tts import router as tts_router
from app.services.registry import get_tts_service
from app.services.tts_service import SentenceSegment


class FakeTTSService:
    """One sentence per request, one audio chunk per sentence."""

    def segment_text_with_offsets(self, text: str) -> list[SentenceSegment]:
        return [SentenceSegment(text=text, start_offset=0, end_offset=len(text))]

    async def generate_audio_async(
        self, text: str, voice: str = "af_heart", speed: float = 1.5
    ) -> AsyncIterator[bytes]:
        yield b"fake-audio"


class FailingThenWorkingTTSService(FakeTTSService):
    """Raises at the task level on the first request, works afterwards."""

    def __init__(self) -> None:
        self.calls = 0

    def segment_text_with_offsets(self, text: str) -> list[SentenceSegment]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("synthesizer exploded")
        return super().segment_text_with_offsets(text)


def make_client(service: FakeTTSService) -> TestClient:
    app = FastAPI()
    app.include_router(tts_router)
    app.dependency_overrides[get_tts_service] = lambda: service
    return TestClient(app)


def drain_until(ws, frame_type: str, limit: int = 20) -> list[dict]:
    """Receive frames until one of `frame_type` arrives; return all frames."""
    frames = []
    for _ in range(limit):
        frame = ws.receive_json()
        frames.append(frame)
        if frame["type"] == frame_type:
            return frames
    raise AssertionError(f"no {frame_type!r} frame within {limit} frames")


# timeout: with the regression present, the client blocks forever on the dead
# socket instead of failing an assertion
@pytest.mark.timeout(30)
def test_websocket_survives_completed_playback():
    client = make_client(FakeTTSService())

    with client.websocket_connect("/ws/tts") as ws:
        ws.send_json({"type": "start", "text": "hello"})
        frames = drain_until(ws, "done")
        assert [f["type"] for f in frames] == [
            "sentence_start",
            "audio",
            "sentence_end",
            "done",
        ]

        # The connection must still be usable for a second playback. With the
        # bug, the frame after "done" was an AttributeError error frame and
        # the socket then closed.
        ws.send_json({"type": "start", "text": "world"})
        frames = drain_until(ws, "done")
        types = [f["type"] for f in frames]
        assert "error" not in types
        assert types[0] == "sentence_start"
        assert frames[0]["text"] == "world"


@pytest.mark.timeout(30)
def test_websocket_survives_task_level_failure():
    client = make_client(FailingThenWorkingTTSService())

    with client.websocket_connect("/ws/tts") as ws:
        ws.send_json({"type": "start", "text": "boom"})
        frame = ws.receive_json()
        assert frame["type"] == "error"
        assert "Audio generation failed" in frame["message"]

        # Same break applies on the failure path: the socket must stay alive
        ws.send_json({"type": "start", "text": "recovered"})
        frames = drain_until(ws, "done")
        assert frames[0] == {
            "type": "sentence_start",
            "index": 0,
            "text": "recovered",
            "startOffset": 0,
            "endOffset": len("recovered"),
        }
