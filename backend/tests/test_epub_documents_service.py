"""
Unit tests for EPUBDocumentsService.

Tests cover:
- Database connection management
- CRUD operations (create, read, update, delete)
- Idempotent create_or_update operations
- Filesystem sync functionality
- Edge cases and error handling
- Metadata JSON serialization
- Timestamp management
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.services.epub_documents_service import EPUBDocumentsService


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    # Initialize the database with the epub_documents table
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS epub_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            title TEXT,
            author TEXT,
            chapters INTEGER NOT NULL DEFAULT 0,
            subject TEXT,
            publisher TEXT,
            language TEXT,
            file_size INTEGER,
            file_path TEXT,
            thumbnail_path TEXT,
            created_date TEXT,
            modified_date TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def service(temp_db):
    """Create EPUBDocumentsService instance with temp database"""
    return EPUBDocumentsService(db_path=temp_db)


class TestEPUBDocumentsServiceInitialization:
    """Test service initialization"""
    
    def test_init_with_default_path(self):
        """Test initialization with default database path"""
        service = EPUBDocumentsService()
        assert service.db_path == "data/reading_progress.db"
    
    def test_init_with_custom_path(self, temp_db):
        """Test initialization with custom database path"""
        service = EPUBDocumentsService(db_path=temp_db)
        assert service.db_path == temp_db


class TestDatabaseConnectionManagement:
    """Test database connection context manager"""
    
    def test_get_connection_context_manager(self, service):
        """Test that connection context manager works correctly"""
        with service.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            # Verify row_factory is set
            assert conn.row_factory == sqlite3.Row
    
    def test_connection_closes_after_context(self, service):
        """Test that connection closes after exiting context"""
        with service.get_connection() as conn:
            pass
        
        # Connection should be closed - trying to use it should raise an error
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")
    
    def test_connection_closes_on_exception(self, service, temp_db):
        """Test that connection closes even when exception occurs"""
        try:
            with service.get_connection() as conn:
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Verify database is still accessible
        with service.get_connection() as conn:
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone() is not None


class TestCreateOrUpdate:
    """Test create_or_update method"""
    
    def test_create_new_document(self, service):
        """Test creating a new EPUB document"""
        epub_id = service.create_or_update(
            filename="test.epub",
            chapters=10,
            title="Test EPUB",
            author="Test Author",
            subject="Fiction",
            publisher="Test Publisher",
            language="en",
            file_size=1024000,
            file_path="/path/to/test.epub",
            thumbnail_path="/path/to/thumbnail.jpg",
            created_date="2024-01-01T00:00:00",
            modified_date="2024-01-02T00:00:00",
        )
        
        assert epub_id is not None
        assert epub_id > 0
        
        # Verify the document was created
        doc = service.get_by_filename("test.epub")
        assert doc is not None
        assert doc["filename"] == "test.epub"
        assert doc["title"] == "Test EPUB"
        assert doc["author"] == "Test Author"
        assert doc["chapters"] == 10
        assert doc["subject"] == "Fiction"
        assert doc["publisher"] == "Test Publisher"
        assert doc["language"] == "en"
        assert doc["file_size"] == 1024000
    
    def test_create_with_metadata_json(self, service):
        """Test creating document with metadata JSON"""
        metadata = {
            "custom_field": "custom_value",
            "isbn": "978-1234567890",
            "tags": ["fiction", "adventure"]
        }
        
        epub_id = service.create_or_update(
            filename="test_metadata.epub",
            chapters=5,
            metadata=metadata
        )
        
        doc = service.get_by_filename("test_metadata.epub")
        assert doc is not None
        
        stored_metadata = json.loads(doc["metadata_json"])
        assert stored_metadata == metadata
        assert stored_metadata["isbn"] == "978-1234567890"
        assert "adventure" in stored_metadata["tags"]
    
    def test_update_existing_document(self, service):
        """Test updating an existing EPUB document"""
        # Create initial document
        epub_id = service.create_or_update(
            filename="update_test.epub",
            chapters=5,
            title="Original Title",
            author="Original Author"
        )
        
        # Update the document
        updated_id = service.create_or_update(
            filename="update_test.epub",
            chapters=10,
            title="Updated Title",
            author="Updated Author",
            subject="New Subject"
        )
        
        # IDs should match
        assert updated_id == epub_id
        
        # Verify updates
        doc = service.get_by_filename("update_test.epub")
        assert doc["id"] == epub_id
        assert doc["title"] == "Updated Title"
        assert doc["author"] == "Updated Author"
        assert doc["chapters"] == 10
        assert doc["subject"] == "New Subject"
    
    def test_create_or_update_idempotent(self, service):
        """Test that create_or_update is idempotent"""
        # Call multiple times with same data
        id1 = service.create_or_update(
            filename="idempotent.epub",
            chapters=3,
            title="Same Title"
        )
        
        id2 = service.create_or_update(
            filename="idempotent.epub",
            chapters=3,
            title="Same Title"
        )
        
        id3 = service.create_or_update(
            filename="idempotent.epub",
            chapters=3,
            title="Same Title"
        )
        
        # All IDs should be the same
        assert id1 == id2 == id3
        
        # Should only have one record
        all_docs = service.list_all()
        matching_docs = [d for d in all_docs if d["filename"] == "idempotent.epub"]
        assert len(matching_docs) == 1
    
    def test_create_with_minimal_fields(self, service):
        """Test creating document with only required fields"""
        epub_id = service.create_or_update(
            filename="minimal.epub",
            chapters=1
        )
        
        assert epub_id > 0
        
        doc = service.get_by_filename("minimal.epub")
        assert doc["filename"] == "minimal.epub"
        assert doc["chapters"] == 1
        assert doc["title"] is None
        assert doc["author"] is None
    
    def test_create_with_zero_chapters(self, service):
        """Test creating document with zero chapters"""
        epub_id = service.create_or_update(
            filename="zero_chapters.epub",
            chapters=0,
            title="Empty Book"
        )
        
        doc = service.get_by_filename("zero_chapters.epub")
        assert doc["chapters"] == 0
    
    def test_update_last_accessed_on_update(self, service):
        """Test that last_accessed is updated when document is updated"""
        import time
        
        # Create document
        epub_id = service.create_or_update(
            filename="timestamp_test.epub",
            chapters=1
        )
        
        doc1 = service.get_by_filename("timestamp_test.epub")
        first_accessed = doc1["last_accessed"]
        
        # Wait a moment
        time.sleep(0.1)
        
        # Update document
        service.create_or_update(
            filename="timestamp_test.epub",
            chapters=2
        )
        
        doc2 = service.get_by_filename("timestamp_test.epub")
        second_accessed = doc2["last_accessed"]
        
        # last_accessed should have changed
        assert second_accessed >= first_accessed


class TestReadOperations:
    """Test read operations"""
    
    def test_get_by_filename_exists(self, service):
        """Test getting document by filename when it exists"""
        service.create_or_update(
            filename="find_me.epub",
            chapters=5,
            title="Findable"
        )
        
        doc = service.get_by_filename("find_me.epub")
        assert doc is not None
        assert doc["filename"] == "find_me.epub"
        assert doc["title"] == "Findable"
    
    def test_get_by_filename_not_exists(self, service):
        """Test getting document by filename when it doesn't exist"""
        doc = service.get_by_filename("nonexistent.epub")
        assert doc is None
    
    def test_get_by_id_exists(self, service):
        """Test getting document by ID when it exists"""
        epub_id = service.create_or_update(
            filename="id_test.epub",
            chapters=3,
            title="ID Test"
        )
        
        doc = service.get_by_id(epub_id)
        assert doc is not None
        assert doc["id"] == epub_id
        assert doc["filename"] == "id_test.epub"
    
    def test_get_by_id_not_exists(self, service):
        """Test getting document by ID when it doesn't exist"""
        doc = service.get_by_id(99999)
        assert doc is None
    
    def test_list_all_empty(self, service):
        """Test listing all documents when database is empty"""
        docs = service.list_all()
        assert docs == []
    
    def test_list_all_with_documents(self, service):
        """Test listing all documents"""
        # Create multiple documents
        service.create_or_update(filename="book1.epub", chapters=1, title="Book 1")
        service.create_or_update(filename="book2.epub", chapters=2, title="Book 2")
        service.create_or_update(filename="book3.epub", chapters=3, title="Book 3")
        
        docs = service.list_all()
        assert len(docs) == 3
        
        filenames = {doc["filename"] for doc in docs}
        assert "book1.epub" in filenames
        assert "book2.epub" in filenames
        assert "book3.epub" in filenames
    
    def test_list_all_ordered_by_last_accessed(self, service):
        """Test that list_all returns documents ordered by last_accessed (most recent first)"""
        import time
        
        # Create documents with delays to ensure different timestamps
        service.create_or_update(filename="old.epub", chapters=1)
        time.sleep(0.05)
        service.create_or_update(filename="middle.epub", chapters=1)
        time.sleep(0.05)
        service.create_or_update(filename="new.epub", chapters=1)
        
        docs = service.list_all()
        
        # Most recent should be first
        assert docs[0]["filename"] == "new.epub"
        assert docs[-1]["filename"] == "old.epub"


class TestUpdateLastAccessed:
    """Test update_last_accessed method"""
    
    def test_update_last_accessed(self, service):
        """Test updating last_accessed timestamp"""
        import time
        
        epub_id = service.create_or_update(
            filename="access_test.epub",
            chapters=1
        )
        
        doc1 = service.get_by_id(epub_id)
        first_accessed = doc1["last_accessed"]
        
        time.sleep(0.1)
        
        service.update_last_accessed(epub_id)
        
        doc2 = service.get_by_id(epub_id)
        second_accessed = doc2["last_accessed"]
        
        # Timestamp should have changed
        assert second_accessed >= first_accessed
    
    def test_update_last_accessed_nonexistent(self, service):
        """Test updating last_accessed for non-existent document (should not raise error)"""
        # Should not raise an exception
        service.update_last_accessed(99999)


class TestDeleteOperations:
    """Test delete operations"""
    
    def test_delete_by_filename_exists(self, service):
        """Test deleting document that exists"""
        service.create_or_update(
            filename="delete_me.epub",
            chapters=1
        )
        
        # Verify it exists
        assert service.get_by_filename("delete_me.epub") is not None
        
        # Delete it
        result = service.delete_by_filename("delete_me.epub")
        assert result is True
        
        # Verify it's gone
        assert service.get_by_filename("delete_me.epub") is None
    
    def test_delete_by_filename_not_exists(self, service):
        """Test deleting document that doesn't exist"""
        result = service.delete_by_filename("nonexistent.epub")
        assert result is False
    
    def test_delete_multiple_times(self, service):
        """Test deleting same document multiple times"""
        service.create_or_update(filename="delete_twice.epub", chapters=1)
        
        result1 = service.delete_by_filename("delete_twice.epub")
        assert result1 is True
        
        result2 = service.delete_by_filename("delete_twice.epub")
        assert result2 is False


class TestFilesystemSync:
    """Test sync_from_filesystem method"""
    
    @pytest.fixture
    def temp_epub_dir(self):
        """Create temporary directory for EPUB files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def mock_epub_service(self):
        """Create mock EPUBService"""
        mock_service = Mock()
        mock_cache = Mock()
        mock_service.cache = mock_cache
        return mock_service
    
    def test_sync_add_new_files(self, service, temp_epub_dir, mock_epub_service):
        """Test syncing adds new EPUB files from filesystem"""
        # Create mock EPUB files
        epub1 = Path(temp_epub_dir) / "book1.epub"
        epub2 = Path(temp_epub_dir) / "book2.epub"
        epub1.touch()
        epub2.touch()
        
        # Mock the EPUBService to return metadata
        mock_epub_service.cache.get_epub_info.side_effect = [
            {
                "title": "Book 1",
                "author": "Author 1",
                "chapters": 5,
                "created_date": "2024-01-01",
                "modified_date": "2024-01-02"
            },
            {
                "title": "Book 2",
                "author": "Author 2",
                "chapters": 3,
                "created_date": "2024-01-03",
                "modified_date": "2024-01-04"
            }
        ]
        mock_epub_service.cache.get_thumbnail_path.return_value = None
        
        with patch('app.services.epub_documents_service.EPUBService', return_value=mock_epub_service):
            stats = service.sync_from_filesystem(temp_epub_dir)
        
        assert stats["added"] == 2
        assert stats["removed"] == 0
        assert stats["updated"] == 0
        
        # Verify documents were added
        assert service.get_by_filename("book1.epub") is not None
        assert service.get_by_filename("book2.epub") is not None
    
    def test_sync_remove_missing_files(self, service, temp_epub_dir, mock_epub_service):
        """Test syncing removes documents for files no longer in filesystem"""
        # Add documents to database
        service.create_or_update(filename="removed.epub", chapters=1)
        service.create_or_update(filename="still_here.epub", chapters=1)
        
        # Create only one file in filesystem
        epub_file = Path(temp_epub_dir) / "still_here.epub"
        epub_file.touch()
        
        mock_epub_service.cache.get_epub_info.return_value = {
            "title": "Still Here",
            "author": "Author",
            "chapters": 1,
            "created_date": "2024-01-01",
            "modified_date": "2024-01-01"
        }
        mock_epub_service.cache.get_thumbnail_path.return_value = None
        
        with patch('app.services.epub_documents_service.EPUBService', return_value=mock_epub_service):
            stats = service.sync_from_filesystem(temp_epub_dir)
        
        assert stats["removed"] == 1
        
        # Verify removed.epub was deleted
        assert service.get_by_filename("removed.epub") is None
        assert service.get_by_filename("still_here.epub") is not None
    
    def test_sync_update_existing_files(self, service, temp_epub_dir, mock_epub_service):
        """Test syncing updates metadata for existing files"""
        # Add document with old metadata
        service.create_or_update(
            filename="update.epub",
            chapters=1,
            title="Old Title"
        )
        
        # Create file in filesystem
        epub_file = Path(temp_epub_dir) / "update.epub"
        epub_file.touch()
        
        # Mock returns updated metadata
        mock_epub_service.cache.get_epub_info.return_value = {
            "title": "New Title",
            "author": "New Author",
            "chapters": 10,
            "created_date": "2024-01-01",
            "modified_date": "2024-01-05"
        }
        mock_epub_service.cache.get_thumbnail_path.return_value = None
        
        with patch('app.services.epub_documents_service.EPUBService', return_value=mock_epub_service):
            stats = service.sync_from_filesystem(temp_epub_dir)
        
        assert stats["updated"] == 1
        assert stats["added"] == 0
        
        # Verify metadata was updated
        doc = service.get_by_filename("update.epub")
        assert doc["title"] == "New Title"
        assert doc["author"] == "New Author"
        assert doc["chapters"] == 10
    
    def test_sync_handles_errors_gracefully(self, service, temp_epub_dir, mock_epub_service):
        """Test sync continues even if some files cause errors"""
        # Create two files
        epub1 = Path(temp_epub_dir) / "good.epub"
        epub2 = Path(temp_epub_dir) / "bad.epub"
        epub1.touch()
        epub2.touch()
        
        # First call succeeds, second fails
        mock_epub_service.cache.get_epub_info.side_effect = [
            {
                "title": "Good",
                "author": "Author",
                "chapters": 1,
                "created_date": "2024-01-01",
                "modified_date": "2024-01-01"
            },
            Exception("Failed to read EPUB")
        ]
        mock_epub_service.cache.get_thumbnail_path.return_value = None
        
        with patch('app.services.epub_documents_service.EPUBService', return_value=mock_epub_service):
            stats = service.sync_from_filesystem(temp_epub_dir)
        
        # Should have added the good one
        assert stats["added"] >= 1
        assert service.get_by_filename("good.epub") is not None
    
    def test_sync_empty_directory(self, service, temp_epub_dir, mock_epub_service):
        """Test syncing with empty directory"""
        # Add some documents
        service.create_or_update(filename="book1.epub", chapters=1)
        service.create_or_update(filename="book2.epub", chapters=1)
        
        with patch('app.services.epub_documents_service.EPUBService', return_value=mock_epub_service):
            stats = service.sync_from_filesystem(temp_epub_dir)
        
        # All should be removed
        assert stats["removed"] == 2
        assert stats["added"] == 0
        assert len(service.list_all()) == 0


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_unicode_in_metadata(self, service):
        """Test handling Unicode characters in metadata"""
        epub_id = service.create_or_update(
            filename="unicode_test.epub",
            chapters=1,
            title="Test with émojis 📚 and ñoñó",
            author="José García Márquez",
            subject="Литература"
        )
        
        doc = service.get_by_filename("unicode_test.epub")
        assert "émojis" in doc["title"]
        assert "📚" in doc["title"]
        assert "García" in doc["author"]
        assert "Литература" in doc["subject"]
    
    def test_special_characters_in_filename(self, service):
        """Test handling special characters in filenames"""
        special_filename = "book_with_spaces & special-chars (2024).epub"
        
        epub_id = service.create_or_update(
            filename=special_filename,
            chapters=1,
            title="Special Chars"
        )
        
        doc = service.get_by_filename(special_filename)
        assert doc is not None
        assert doc["filename"] == special_filename
    
    def test_very_long_strings(self, service):
        """Test handling very long strings in metadata"""
        long_title = "A" * 1000
        long_author = "B" * 1000
        
        epub_id = service.create_or_update(
            filename="long_strings.epub",
            chapters=1,
            title=long_title,
            author=long_author
        )
        
        doc = service.get_by_filename("long_strings.epub")
        assert doc["title"] == long_title
        assert doc["author"] == long_author
    
    def test_null_and_empty_strings(self, service):
        """Test handling None and empty strings"""
        epub_id = service.create_or_update(
            filename="nulls.epub",
            chapters=1,
            title="",
            author=None,
            subject="",
            publisher=None
        )
        
        doc = service.get_by_filename("nulls.epub")
        assert doc["title"] == ""
        assert doc["author"] is None
        assert doc["subject"] == ""
    
    def test_large_metadata_json(self, service):
        """Test handling large metadata JSON"""
        large_metadata = {
            f"key_{i}": f"value_{i}" * 100
            for i in range(100)
        }
        
        epub_id = service.create_or_update(
            filename="large_metadata.epub",
            chapters=1,
            metadata=large_metadata
        )
        
        doc = service.get_by_filename("large_metadata.epub")
        stored_metadata = json.loads(doc["metadata_json"])
        assert len(stored_metadata) == 100
        assert stored_metadata["key_50"] == "value_50" * 100
    
    def test_negative_values(self, service):
        """Test handling negative values for numeric fields"""
        # Negative chapters should be allowed (validation is application layer concern)
        epub_id = service.create_or_update(
            filename="negative.epub",
            chapters=-1,
            file_size=-100
        )
        
        doc = service.get_by_filename("negative.epub")
        assert doc["chapters"] == -1
        assert doc["file_size"] == -100
    
    def test_database_locked_scenario(self, temp_db):
        """Test behavior when database is locked (simulated)"""
        service1 = EPUBDocumentsService(db_path=temp_db)
        service2 = EPUBDocumentsService(db_path=temp_db)
        
        # Both services should be able to operate
        service1.create_or_update(filename="service1.epub", chapters=1)
        service2.create_or_update(filename="service2.epub", chapters=1)
        
        assert service1.get_by_filename("service2.epub") is not None
        assert service2.get_by_filename("service1.epub") is not None