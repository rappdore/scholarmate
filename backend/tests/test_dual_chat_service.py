"""
Unit tests for DualChatService client management (audit B-11).

Previously a new AsyncOpenAI client was constructed for every streamed
request and never closed, leaking connections. Clients are now cached per
(base_url, api_key) on the service instance.
"""

from types import SimpleNamespace
from unittest.mock import Mock

from app.services.dual_chat_service import DualChatService
from app.services.registry import get_dual_chat_service, get_pdf_service


def _config(base_url: str, api_key: str) -> SimpleNamespace:
    return SimpleNamespace(base_url=base_url, api_key=api_key)


def _service(tmp_path) -> DualChatService:
    return DualChatService(db_path=str(tmp_path / "test.db"), pdf_service=Mock())


class TestClientCaching:
    def test_same_config_reuses_client(self, tmp_path):
        service = _service(tmp_path)
        config = _config("http://localhost:11434/v1", "key-1")

        client_a = service._get_client(config)
        client_b = service._get_client(config)

        assert client_a is client_b
        assert len(service._llm_clients) == 1

    def test_different_configs_get_distinct_clients(self, tmp_path):
        service = _service(tmp_path)

        client_a = service._get_client(_config("http://localhost:11434/v1", "key-1"))
        client_b = service._get_client(_config("http://other:8080/v1", "key-1"))
        client_c = service._get_client(_config("http://localhost:11434/v1", "key-2"))

        assert client_a is not client_b
        assert client_a is not client_c
        assert len(service._llm_clients) == 3

    def test_registry_wires_shared_pdf_service(self):
        # B-3: the registry must hand dual chat THE shared PDFService.
        assert get_dual_chat_service().pdf_service is get_pdf_service()
