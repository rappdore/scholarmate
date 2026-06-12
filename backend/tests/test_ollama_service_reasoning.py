"""
Tests for OllamaService reasoning-session handling (bug B-9).

Covers:
- End-aligned pairing of stored reasoning traces with assistant messages,
  including when chat history is truncated to the last 10 messages.
- Reasoning session reset on new chat.
- Per-file cap on stored reasoning traces.
"""

from app.services.ollama_service import (
    CHAT_HISTORY_LIMIT,
    MAX_REASONING_PER_FILE,
    OllamaService,
)


def make_service() -> OllamaService:
    """Create an OllamaService without running __init__ (avoids DB access)."""
    service = OllamaService.__new__(OllamaService)
    service._reasoning_sessions = {}
    return service


def build_history(pair_count: int) -> list[dict]:
    """Build alternating user/assistant history: q1, a1, q2, a2, ..."""
    history: list[dict] = []
    for i in range(1, pair_count + 1):
        history.append({"role": "user", "content": f"q{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})
    return history


class TestReconstructHistoryWithReasoning:
    def test_pairing_when_history_truncated_to_last_ten(self):
        # 7 exchanges = 14 messages; only the last 10 are sent to the LLM.
        chat_history = build_history(7)
        stored_reasoning = [f"r{i}" for i in range(1, 8)]

        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, stored_reasoning
        )

        # Truncated to the last CHAT_HISTORY_LIMIT messages: q3..a7
        assert len(messages) == CHAT_HISTORY_LIMIT
        assert messages[0] == {"role": "user", "content": "q3"}

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert [m["content"] for m in assistant_msgs] == ["a3", "a4", "a5", "a6", "a7"]
        # Reasoning must align from the END: a3->r3 ... a7->r7 (not r1..r5).
        assert [m["reasoning_details"] for m in assistant_msgs] == [
            "r3",
            "r4",
            "r5",
            "r6",
            "r7",
        ]

    def test_pairing_without_truncation(self):
        chat_history = build_history(3)
        stored_reasoning = ["r1", "r2", "r3"]

        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, stored_reasoning
        )

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert [m["reasoning_details"] for m in assistant_msgs] == ["r1", "r2", "r3"]
        assert [m["content"] for m in assistant_msgs] == ["a1", "a2", "a3"]

    def test_fewer_reasonings_than_assistant_messages(self):
        # Only the most recent assistant message has a stored trace.
        chat_history = build_history(2)
        stored_reasoning = ["r-latest"]

        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, stored_reasoning
        )

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert "reasoning_details" not in assistant_msgs[0]
        assert assistant_msgs[1]["reasoning_details"] == "r-latest"

    def test_more_reasonings_than_assistant_messages(self):
        # Older traces beyond the visible history are ignored.
        chat_history = build_history(2)
        stored_reasoning = ["r1", "r2", "r3", "r4"]

        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, stored_reasoning
        )

        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert [m["reasoning_details"] for m in assistant_msgs] == ["r3", "r4"]

    def test_none_reasoning_leaves_message_untouched(self):
        chat_history = build_history(1)
        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, [None]
        )

        assert messages[1] == {"role": "assistant", "content": "a1"}
        assert "reasoning_details" not in messages[1]

    def test_empty_inputs(self):
        assert OllamaService._reconstruct_history_with_reasoning([], []) == []

        chat_history = build_history(1)
        messages = OllamaService._reconstruct_history_with_reasoning(chat_history, [])
        assert messages == chat_history

    def test_non_assistant_messages_passed_through(self):
        chat_history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        messages = OllamaService._reconstruct_history_with_reasoning(
            chat_history, ["r1"]
        )
        assert messages[0] == {"role": "user", "content": "q1"}
        assert messages[2] == {"role": "user", "content": "q2"}
        assert messages[1]["reasoning_details"] == "r1"


class TestReasoningSessionLifecycle:
    def test_clear_on_new_chat(self):
        service = make_service()
        service._store_reasoning("book.pdf", "r1")
        assert "book.pdf" in service._reasoning_sessions

        service._clear_reasoning_session("book.pdf")
        assert "book.pdf" not in service._reasoning_sessions

    def test_clear_when_no_session_exists_is_noop(self):
        service = make_service()
        service._clear_reasoning_session("missing.pdf")
        assert service._reasoning_sessions == {}

    def test_store_keeps_none_placeholders(self):
        service = make_service()
        service._store_reasoning("book.pdf", "r1")
        service._store_reasoning("book.pdf", None)
        assert service._reasoning_sessions["book.pdf"] == ["r1", None]

    def test_cap_respected(self):
        service = make_service()
        total = MAX_REASONING_PER_FILE + 10
        for i in range(total):
            service._store_reasoning("book.pdf", f"r{i}")

        session = service._reasoning_sessions["book.pdf"]
        assert len(session) == MAX_REASONING_PER_FILE
        # Only the most recent traces are kept.
        assert session[0] == "r10"
        assert session[-1] == f"r{total - 1}"

    def test_cap_is_per_file(self):
        service = make_service()
        for i in range(MAX_REASONING_PER_FILE + 5):
            service._store_reasoning("a.pdf", f"a{i}")
        service._store_reasoning("b.epub", "b0")

        assert len(service._reasoning_sessions["a.pdf"]) == MAX_REASONING_PER_FILE
        assert service._reasoning_sessions["b.epub"] == ["b0"]
