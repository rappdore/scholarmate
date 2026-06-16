from app.models.documents import EpubDocumentUpsert
from app.routers.epub import (
    EPUBProgressRequest,
    get_all_epub_progress,
    get_epub_progress_by_id,
    save_epub_progress_by_id,
)
from app.services.documents_repository import DocumentsRepository
from app.services.progress_service import ProgressService


class FakeEPUBService:
    def needs_word_count(self, nav_metadata):
        return False


def _make_services(tmp_path):
    db_path = str(tmp_path / "test.db")
    repo = DocumentsRepository(db_path)
    progress = ProgressService(db_path)
    return repo, progress


def test_epub_progress_routes_return_epub_cfi(tmp_path):
    repo, progress = _make_services(tmp_path)
    epub_id = repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=2))
    cfi = "epubcfi(/4/2[preface]!/4/2/8:42)"

    response = save_epub_progress_by_id(
        epub_id,
        EPUBProgressRequest(current_nav_id="section_1", epub_cfi=cfi),
        progress_service=progress,
        documents_repository=repo,
    )
    assert response["success"] is True

    saved = get_epub_progress_by_id(
        epub_id,
        progress_service=progress,
        epub_service=FakeEPUBService(),
        documents_repository=repo,
    )
    assert saved["epub_cfi"] == cfi

    all_progress = get_all_epub_progress(progress_service=progress)
    assert all_progress["epub_progress"]["book.epub"]["epub_cfi"] == cfi


def test_epub_progress_routes_preserve_omitted_cfi_and_clear_explicit_null(tmp_path):
    repo, progress = _make_services(tmp_path)
    epub_id = repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=2))
    cfi = "epubcfi(/4/2[preface]!/4/2/8:42)"

    save_epub_progress_by_id(
        epub_id,
        EPUBProgressRequest(current_nav_id="section_1", epub_cfi=cfi),
        progress_service=progress,
        documents_repository=repo,
    )
    save_epub_progress_by_id(
        epub_id,
        EPUBProgressRequest(current_nav_id="section_2", scroll_position=200),
        progress_service=progress,
        documents_repository=repo,
    )
    saved = get_epub_progress_by_id(
        epub_id,
        progress_service=progress,
        epub_service=FakeEPUBService(),
        documents_repository=repo,
    )
    assert saved["current_nav_id"] == "section_2"
    assert saved["scroll_position"] == 200
    assert saved["epub_cfi"] == cfi

    save_epub_progress_by_id(
        epub_id,
        EPUBProgressRequest(current_nav_id="section_2", epub_cfi=None),
        progress_service=progress,
        documents_repository=repo,
    )
    saved = get_epub_progress_by_id(
        epub_id,
        progress_service=progress,
        epub_service=FakeEPUBService(),
        documents_repository=repo,
    )
    assert saved["epub_cfi"] is None


def test_epub_progress_default_response_includes_epub_cfi(tmp_path):
    repo, progress = _make_services(tmp_path)
    epub_id = repo.upsert(EpubDocumentUpsert(filename="book.epub", chapters=2))

    response = get_epub_progress_by_id(
        epub_id,
        progress_service=progress,
        epub_service=FakeEPUBService(),
        documents_repository=repo,
    )

    assert response["epub_cfi"] is None
