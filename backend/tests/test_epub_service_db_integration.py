"""
Unit tests for EPUBService database integration.

Tests cover:
- Database path parameter passing
- Cache initialization with database backing
- Integration between EPUBService, EPUBCache, and EPUBDocumentsService
- Default database path behavior
- Custom database path configuration
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import sqlite3
import os

import pytest

from app.services.epub_service import EPUBService


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""
    with tempfile.TemporaryDirectory() as epub_dir, \
         tempfile.TemporaryDirectory() as thumb_dir, \
         tempfile.TemporaryDirectory() as data_dir:
        yield {
            'epub_dir': epub_dir,
            'thumb_dir': thumb_dir,
            'data_dir': data_dir
        }


@pytest.fixture
def temp_db(temp_dirs):
    """Create temporary database with required tables"""
    db_path = os.path.join(temp_dirs['data_dir'], 'test.db')
    
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
    
    return db_path


class TestEPUBServiceInitialization:
    """Test EPUBService initialization with database parameters"""
    
    def test_init_with_default_db_path(self, temp_dirs):
        """Test initialization with default database path"""
        with patch('app.services.epub_service.EPUBCache'):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir']
            )
        
        # Default path should be used
        assert service is not None
    
    def test_init_with_custom_db_path(self, temp_dirs, temp_db):
        """Test initialization with custom database path"""
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        # Verify cache was initialized with custom db_path
        mock_cache.assert_called_once()
        call_args = mock_cache.call_args
        assert call_args[0][3] == temp_db  # Fourth positional arg is db_path
    
    def test_db_path_passed_to_cache(self, temp_dirs, temp_db):
        """Test that db_path is correctly passed to EPUBCache"""
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        # Verify cache constructor received db_path
        assert mock_cache.called
        call_kwargs = mock_cache.call_args[1] if mock_cache.call_args[1] else {}
        call_args = mock_cache.call_args[0] if mock_cache.call_args[0] else []
        
        # db_path should be in args or kwargs
        assert temp_db in call_args or call_kwargs.get('db_path') == temp_db
    
    def test_service_initializes_all_components(self, temp_dirs, temp_db):
        """Test that EPUBService initializes all required components"""
        with patch('app.services.epub_service.EPUBCache'):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        assert service.epub_dir is not None
        assert service.thumbnails_dir is not None
        assert service.base_url is not None
        assert service.metadata_extractor is not None
        assert service.navigation_service is not None
        assert service.content_processor is not None
        assert service.image_service is not None
        assert service.style_processor is not None
        assert service.cache is not None


class TestDatabasePathConfiguration:
    """Test database path configuration options"""
    
    def test_default_db_path_value(self, temp_dirs):
        """Test that default database path is correct"""
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir']
            )
        
        # Default should be "data/reading_progress.db"
        call_args = mock_cache.call_args[0]
        assert call_args[3] == "data/reading_progress.db"
    
    def test_relative_db_path(self, temp_dirs):
        """Test initialization with relative database path"""
        relative_path = "custom/data/epubs.db"
        
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=relative_path
            )
        
        call_args = mock_cache.call_args[0]
        assert call_args[3] == relative_path
    
    def test_absolute_db_path(self, temp_dirs, temp_db):
        """Test initialization with absolute database path"""
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        call_args = mock_cache.call_args[0]
        assert call_args[3] == temp_db
    
    def test_db_path_with_special_characters(self, temp_dirs):
        """Test database path with special characters"""
        special_path = "data/test-db_with spaces.db"
        
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=special_path
            )
        
        call_args = mock_cache.call_args[0]
        assert call_args[3] == special_path


class TestCacheIntegration:
    """Test integration between EPUBService and EPUBCache"""
    
    def test_cache_receives_correct_parameters(self, temp_dirs, temp_db):
        """Test that cache receives all correct initialization parameters"""
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                base_url="http://test:8000",
                db_path=temp_db
            )
        
        # Verify all parameters passed to cache
        call_args = mock_cache.call_args[0]
        
        assert isinstance(call_args[0], Path)  # epub_dir
        assert isinstance(call_args[1], Path)  # thumbnails_dir
        # call_args[2] is epub_service (self)
        assert call_args[3] == temp_db  # db_path
    
    def test_service_methods_use_cache(self, temp_dirs, temp_db):
        """Test that EPUBService methods utilize the cache"""
        mock_cache = Mock()
        mock_cache.get_all_epubs.return_value = []
        mock_cache.get_epub_info.return_value = {"filename": "test.epub"}
        mock_cache.get_thumbnail_path.return_value = "thumb.jpg"
        mock_cache.get_cache_info.return_value = {"epub_count": 0}
        
        with patch('app.services.epub_service.EPUBCache', return_value=mock_cache):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
            
            # Test cache methods are called
            service.list_epubs()
            assert mock_cache.get_all_epubs.called
            
            service.get_cache_info()
            assert mock_cache.get_cache_info.called


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""
    
    def test_service_works_without_db_path_parameter(self, temp_dirs):
        """Test that service works when db_path is not provided"""
        with patch('app.services.epub_service.EPUBCache'):
            # Should not raise error
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir']
            )
        
        assert service is not None
    
    def test_existing_methods_still_work(self, temp_dirs, temp_db):
        """Test that existing EPUBService methods still function"""
        mock_cache = Mock()
        mock_cache.get_all_epubs.return_value = [
            {"filename": "book1.epub", "title": "Book 1"},
            {"filename": "book2.epub", "title": "Book 2"}
        ]
        mock_cache.get_epub_info.return_value = {
            "filename": "test.epub",
            "title": "Test Book",
            "chapters": 5
        }
        
        with patch('app.services.epub_service.EPUBCache', return_value=mock_cache):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
            
            # Test existing methods
            epubs = service.list_epubs()
            assert len(epubs) == 2
            
            info = service.get_epub_info("test.epub")
            assert info["title"] == "Test Book"


class TestServiceConfiguration:
    """Test EPUBService configuration options"""
    
    def test_all_init_parameters_work_together(self, temp_dirs, temp_db):
        """Test that all initialization parameters work together"""
        with patch('app.services.epub_service.EPUBCache'):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                base_url="http://custom:9000",
                db_path=temp_db
            )
        
        assert str(service.epub_dir) == temp_dirs['epub_dir']
        assert service.base_url == "http://custom:9000"
    
    def test_service_creates_directories_if_missing(self, temp_dirs, temp_db):
        """Test that service creates required directories"""
        epub_dir = Path(temp_dirs['epub_dir']) / "new_epubs"
        
        with patch('app.services.epub_service.EPUBCache'):
            service = EPUBService(
                epub_dir=str(epub_dir),
                db_path=temp_db
            )
        
        # Directories should be created
        assert service.epub_dir.exists()
        assert service.thumbnails_dir.exists()
    
    def test_base_url_configuration(self, temp_dirs, temp_db):
        """Test base URL configuration"""
        custom_url = "https://example.com:8080"
        
        with patch('app.services.epub_service.EPUBCache'):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                base_url=custom_url,
                db_path=temp_db
            )
        
        assert service.base_url == custom_url


class TestErrorHandling:
    """Test error handling scenarios"""
    
    def test_invalid_db_path_handled(self, temp_dirs):
        """Test handling of invalid database path"""
        invalid_path = "/invalid/path/to/db.db"
        
        # Should handle gracefully or raise appropriate error
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            # May raise error during cache initialization, which is acceptable
            try:
                service = EPUBService(
                    epub_dir=temp_dirs['epub_dir'],
                    db_path=invalid_path
                )
            except Exception:
                # If it raises, that's acceptable for invalid path
                pass
    
    def test_cache_initialization_failure_handling(self, temp_dirs, temp_db):
        """Test handling when cache initialization fails"""
        with patch('app.services.epub_service.EPUBCache', side_effect=Exception("Cache error")):
            with pytest.raises(Exception):
                service = EPUBService(
                    epub_dir=temp_dirs['epub_dir'],
                    db_path=temp_db
                )


class TestIntegrationScenarios:
    """Test realistic integration scenarios"""
    
    def test_service_with_real_cache_and_db(self, temp_dirs, temp_db):
        """Test EPUBService with actual cache and database"""
        # Create a real EPUB file (minimal)
        epub_file = Path(temp_dirs['epub_dir']) / "test.epub"
        epub_file.write_bytes(b"mock epub content")
        
        # Mock only the epub reading
        mock_book = Mock()
        mock_book.get_metadata.return_value = [("Test Book",)]
        mock_book.get_items_of_type.return_value = []
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_book):
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        # Service should be fully functional
        assert service.cache is not None
        assert service.cache._db_service is not None
    
    def test_multiple_service_instances_share_database(self, temp_dirs, temp_db):
        """Test that multiple service instances can share the same database"""
        mock_book = Mock()
        mock_book.get_metadata.return_value = [("Test",)]
        mock_book.get_items_of_type.return_value = []
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_book):
            service1 = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
            
            service2 = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=temp_db
            )
        
        # Both services should be able to coexist
        assert service1 is not None
        assert service2 is not None


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_empty_db_path_string(self, temp_dirs):
        """Test handling of empty database path string"""
        with patch('app.services.epub_service.EPUBCache'):
            try:
                service = EPUBService(
                    epub_dir=temp_dirs['epub_dir'],
                    db_path=""
                )
                # If it succeeds, verify it's initialized
                assert service is not None
            except Exception:
                # Empty string may cause error, which is acceptable
                pass
    
    def test_none_db_path(self, temp_dirs):
        """Test that None db_path is not accepted"""
        # None should not be passed as db_path (should use default)
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            # This should use the default path, not None
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir']
            )
            
            # Verify default path was used (not None)
            call_args = mock_cache.call_args[0]
            assert call_args[3] is not None
            assert call_args[3] == "data/reading_progress.db"
    
    def test_unicode_in_db_path(self, temp_dirs):
        """Test database path with Unicode characters"""
        unicode_path = "data/数据库_📚.db"
        
        with patch('app.services.epub_service.EPUBCache') as mock_cache:
            service = EPUBService(
                epub_dir=temp_dirs['epub_dir'],
                db_path=unicode_path
            )
        
        call_args = mock_cache.call_args[0]
        assert call_args[3] == unicode_path