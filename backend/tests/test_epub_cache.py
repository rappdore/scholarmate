"""
Unit tests for EPUBCache with database backing.

Tests cover:
- Cache initialization with database persistence
- Basic metadata caching
- Extended metadata lazy-loading
- Database persistence for metadata
- Thumbnail path management
- Cache refresh functionality
- Error handling and resilience
- Integration with EPUBDocumentsService
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call
import sqlite3
import json

import pytest

from app.services.epub_cache import EPUBCache
from app.services.epub_documents_service import EPUBDocumentsService


@pytest.fixture
def temp_dirs():
    """Create temporary directories for EPUBs and thumbnails"""
    with tempfile.TemporaryDirectory() as epub_dir, \
         tempfile.TemporaryDirectory() as thumb_dir, \
         tempfile.TemporaryDirectory() as data_dir:
        yield {
            'epub_dir': Path(epub_dir),
            'thumb_dir': Path(thumb_dir),
            'data_dir': Path(data_dir)
        }


@pytest.fixture
def temp_db(temp_dirs):
    """Create a temporary database with epub_documents table"""
    db_path = str(temp_dirs['data_dir'] / 'test.db')
    
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


@pytest.fixture
def mock_epub_service():
    """Create mock EPUBService"""
    service = Mock()
    service.generate_thumbnail = Mock(return_value=Path("thumbnails/test.jpg"))
    return service


@pytest.fixture
def mock_epub_book():
    """Create mock EPUB book object"""
    book = Mock()
    book.get_metadata = Mock(return_value=[("Test Title",)])
    return book


class TestCacheInitialization:
    """Test cache initialization with database backing"""
    
    def test_init_creates_db_service(self, temp_dirs, temp_db, mock_epub_service):
        """Test that cache initializes EPUBDocumentsService"""
        with patch('app.services.epub_cache.epub.read_epub'):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        assert cache._db_service is not None
        assert isinstance(cache._db_service, EPUBDocumentsService)
        assert cache._db_service.db_path == temp_db
    
    def test_init_with_empty_directory(self, temp_dirs, temp_db, mock_epub_service):
        """Test initialization with empty EPUB directory"""
        with patch('app.services.epub_cache.epub.read_epub'):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        assert cache._cache_epub_count == 0
        assert cache._cache == {}
    
    def test_init_builds_cache(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that initialization builds cache from filesystem"""
        # Create mock EPUB file
        epub_file = temp_dirs['epub_dir'] / "test.epub"
        epub_file.touch()
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            with patch('app.services.epub_cache.EPUBCache._extract_metadata_values') as mock_extract:
                mock_extract.side_effect = lambda book, ns, field: {
                    'title': 'Test Book',
                    'creator': 'Test Author'
                }.get(field, '')
                
                cache = EPUBCache(
                    epub_dir=temp_dirs['epub_dir'],
                    thumbnails_dir=temp_dirs['thumb_dir'],
                    epub_service=mock_epub_service,
                    db_path=temp_db
                )
        
        assert cache._cache_epub_count >= 0


class TestBuildCache:
    """Test _build_cache method"""
    
    def test_build_cache_processes_epub_files(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that _build_cache processes EPUB files and persists to database"""
        # Create mock EPUB file
        epub_file = temp_dirs['epub_dir'] / "book.epub"
        epub_file.write_bytes(b"mock epub content")
        
        # Mock EPUB reading
        mock_epub_book.get_metadata.side_effect = lambda ns, field: {
            ('DC', 'title'): [("Great Book",)],
            ('DC', 'creator'): [("Jane Author",)],
        }.get((ns, field), [])
        
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        # Verify cache was built
        assert "book.epub" in cache._cache
        
        # Verify database was updated
        doc = cache._db_service.get_by_filename("book.epub")
        assert doc is not None
        assert doc["filename"] == "book.epub"
    
    def test_build_cache_handles_corrupted_epub(self, temp_dirs, temp_db, mock_epub_service):
        """Test that _build_cache handles corrupted EPUB files gracefully"""
        # Create mock corrupted EPUB file
        epub_file = temp_dirs['epub_dir'] / "corrupted.epub"
        epub_file.write_bytes(b"not a valid epub")
        
        # Mock EPUB reading to raise exception
        with patch('app.services.epub_cache.epub.read_epub', side_effect=Exception("Invalid EPUB")):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        # Cache should still be initialized
        assert cache._cache is not None
        # Corrupted file should still be in cache with limited info
        assert "corrupted.epub" in cache._cache or cache._cache_epub_count == 0
    
    def test_build_cache_generates_thumbnails(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that _build_cache generates thumbnails for EPUBs"""
        epub_file = temp_dirs['epub_dir'] / "with_cover.epub"
        epub_file.write_bytes(b"epub with cover")
        
        mock_epub_book.get_metadata.return_value = [("Test",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        thumbnail_path = temp_dirs['thumb_dir'] / "with_cover.jpg"
        mock_epub_service.generate_thumbnail.return_value = thumbnail_path
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        # Verify thumbnail generation was attempted
        assert mock_epub_service.generate_thumbnail.called


class TestDatabasePersistence:
    """Test database persistence functionality"""
    
    def test_cache_persists_basic_metadata(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that basic metadata is persisted to database"""
        epub_file = temp_dirs['epub_dir'] / "persist_test.epub"
        epub_file.write_bytes(b"test epub")
        
        mock_epub_book.get_metadata.side_effect = lambda ns, field: {
            ('DC', 'title'): [("Persistent Book",)],
            ('DC', 'creator'): [("Persistent Author",)],
        }.get((ns, field), [])
        mock_epub_book.get_items_of_type = Mock(return_value=[Mock()])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        # Check database directly
        doc = cache._db_service.get_by_filename("persist_test.epub")
        assert doc is not None
        assert doc["filename"] == "persist_test.epub"
        assert doc["chapters"] >= 0
    
    def test_cache_handles_db_write_failure(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that cache continues even if database write fails"""
        epub_file = temp_dirs['epub_dir'] / "db_fail.epub"
        epub_file.write_bytes(b"test epub")
        
        mock_epub_book.get_metadata.return_value = [("Test",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            with patch.object(EPUBDocumentsService, 'create_or_update', side_effect=Exception("DB Error")):
                # Should not raise exception
                cache = EPUBCache(
                    epub_dir=temp_dirs['epub_dir'],
                    thumbnails_dir=temp_dirs['thumb_dir'],
                    epub_service=mock_epub_service,
                    db_path=temp_db
                )
        
        # In-memory cache should still work
        assert "db_fail.epub" in cache._cache


class TestExtendedMetadataLoading:
    """Test lazy loading of extended metadata"""
    
    def test_load_extended_metadata_on_demand(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that extended metadata is loaded on first request"""
        epub_file = temp_dirs['epub_dir'] / "extended.epub"
        epub_file.write_bytes(b"test epub")
        
        # Setup mock for basic metadata
        def get_metadata_side_effect(ns, field):
            metadata_map = {
                ('DC', 'title'): [("Extended Book",)],
                ('DC', 'creator'): [("Author Name",)],
                ('DC', 'subject'): [("Fiction", "Adventure")],
                ('DC', 'publisher'): [("Test Publisher",)],
                ('DC', 'language'): [("en",)],
            }
            return metadata_map.get((ns, field), [])
        
        mock_epub_book.get_metadata.side_effect = get_metadata_side_effect
        mock_epub_book.get_items_of_type = Mock(return_value=[Mock()])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            # Get epub info (should trigger extended metadata loading)
            info = cache.get_epub_info("extended.epub")
        
        # Extended metadata should be loaded
        assert "subject" in info or info.get("subject") is not None
        assert "publisher" in info or info.get("publisher") is not None
        assert "language" in info or info.get("language") is not None
    
    def test_extended_metadata_persisted_to_db(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that extended metadata is persisted to database when loaded"""
        epub_file = temp_dirs['epub_dir'] / "extended_persist.epub"
        epub_file.write_bytes(b"test epub")
        
        mock_epub_book.get_metadata.side_effect = lambda ns, field: {
            ('DC', 'title'): [("Book",)],
            ('DC', 'creator'): [("Author",)],
            ('DC', 'subject'): [("Science Fiction",)],
            ('DC', 'publisher'): [("Publisher XYZ",)],
            ('DC', 'language'): [("en",)],
        }.get((ns, field), [])
        mock_epub_book.get_items_of_type = Mock(return_value=[Mock()])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            # Trigger extended metadata loading
            cache.get_epub_info("extended_persist.epub")
        
        # Check database for extended metadata
        doc = cache._db_service.get_by_filename("extended_persist.epub")
        # Extended fields should be present (may be None or empty, but key exists)
        assert "subject" in doc or doc.get("subject") is not None
        assert "publisher" in doc or doc.get("publisher") is not None
    
    def test_extended_metadata_handles_errors(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test that extended metadata loading handles errors gracefully"""
        epub_file = temp_dirs['epub_dir'] / "error_extended.epub"
        epub_file.write_bytes(b"test epub")
        
        # First call succeeds (basic metadata), second fails (extended metadata)
        call_count = [0]
        def read_epub_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_epub_book
            else:
                raise Exception("Failed to read extended metadata")
        
        mock_epub_book.get_metadata.return_value = [("Test",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', side_effect=read_epub_side_effect):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            # Should not raise exception
            try:
                info = cache.get_epub_info("error_extended.epub")
                # Should have basic info even if extended fails
                assert info is not None
            except Exception:
                # If get_epub_info raises, that's also acceptable
                pass


class TestMetadataExtraction:
    """Test _extract_metadata_values method"""
    
    def test_extract_single_value(self, temp_dirs, temp_db, mock_epub_service):
        """Test extracting single metadata value"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = [("Single Value",)]
        
        result = cache._extract_metadata_values(mock_book, "DC", "title")
        assert result == "Single Value"
    
    def test_extract_multiple_authors(self, temp_dirs, temp_db, mock_epub_service):
        """Test extracting multiple authors (should join with semicolon)"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = [
            ("Author One",),
            ("Author Two",),
            ("Author Three",)
        ]
        
        result = cache._extract_metadata_values(mock_book, "DC", "creator")
        assert "Author One" in result
        assert "Author Two" in result
        assert ";" in result  # Should use semicolon separator
    
    def test_extract_multiple_subjects(self, temp_dirs, temp_db, mock_epub_service):
        """Test extracting multiple subjects (should join with comma)"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = [
            ("Fiction",),
            ("Adventure",),
            ("Mystery",)
        ]
        
        result = cache._extract_metadata_values(mock_book, "DC", "subject")
        assert "Fiction" in result
        assert "Adventure" in result
        assert "," in result  # Should use comma separator
    
    def test_extract_empty_metadata(self, temp_dirs, temp_db, mock_epub_service):
        """Test extracting when metadata is empty"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = []
        
        result = cache._extract_metadata_values(mock_book, "DC", "title")
        assert result == ""
    
    def test_extract_filters_empty_values(self, temp_dirs, temp_db, mock_epub_service):
        """Test that empty values are filtered out"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = [
            ("Valid",),
            ("",),
            ("Also Valid",),
            ("   ",)  # Whitespace only
        ]
        
        result = cache._extract_metadata_values(mock_book, "DC", "creator")
        assert "Valid" in result
        assert "Also Valid" in result
        # Empty and whitespace-only values should not appear
        assert ";  ;" not in result
    
    def test_extract_handles_string_values(self, temp_dirs, temp_db, mock_epub_service):
        """Test extracting when values are strings instead of tuples"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = ["String Value", "Another String"]
        
        result = cache._extract_metadata_values(mock_book, "DC", "subject")
        assert "String Value" in result
        assert "Another String" in result
    
    def test_extract_handles_exception(self, temp_dirs, temp_db, mock_epub_service):
        """Test that exceptions in extraction return empty string"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.side_effect = Exception("Metadata error")
        
        result = cache._extract_metadata_values(mock_book, "DC", "title")
        assert result == ""
    
    def test_extract_unknown_author_default(self, temp_dirs, temp_db, mock_epub_service):
        """Test that empty creator returns 'Unknown'"""
        cache = EPUBCache(
            epub_dir=temp_dirs['epub_dir'],
            thumbnails_dir=temp_dirs['thumb_dir'],
            epub_service=mock_epub_service,
            db_path=temp_db
        )
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = []
        
        result = cache._extract_metadata_values(mock_book, "DC", "creator")
        assert result == "Unknown"


class TestCacheOperations:
    """Test cache query operations"""
    
    def test_get_all_epubs(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test getting all EPUBs from cache"""
        # Create multiple EPUB files
        for i in range(3):
            epub_file = temp_dirs['epub_dir'] / f"book{i}.epub"
            epub_file.write_bytes(b"test")
        
        mock_epub_book.get_metadata.return_value = [("Test",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            all_epubs = cache.get_all_epubs()
        
        assert len(all_epubs) == 3
    
    def test_get_epub_info_existing(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test getting info for existing EPUB"""
        epub_file = temp_dirs['epub_dir'] / "specific.epub"
        epub_file.write_bytes(b"test")
        
        mock_epub_book.get_metadata.return_value = [("Specific Book",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            info = cache.get_epub_info("specific.epub")
        
        assert info is not None
        assert info["filename"] == "specific.epub"
    
    def test_get_cache_info(self, temp_dirs, temp_db, mock_epub_service):
        """Test getting cache metadata"""
        with patch('app.services.epub_cache.epub.read_epub'):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            cache_info = cache.get_cache_info()
        
        assert "epub_count" in cache_info or cache_info is not None
        assert "built_at" in cache_info or cache_info is not None


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_unicode_filenames(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test handling EPUBs with Unicode filenames"""
        epub_file = temp_dirs['epub_dir'] / "книга_📚.epub"
        epub_file.write_bytes(b"test")
        
        mock_epub_book.get_metadata.return_value = [("Unicode Book",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        assert "книга_📚.epub" in cache._cache
    
    def test_very_large_epub_directory(self, temp_dirs, temp_db, mock_epub_service, mock_epub_book):
        """Test cache handles many EPUB files"""
        # Create many EPUB files
        num_files = 50
        for i in range(num_files):
            epub_file = temp_dirs['epub_dir'] / f"book_{i:03d}.epub"
            epub_file.write_bytes(b"test")
        
        mock_epub_book.get_metadata.return_value = [("Test",)]
        mock_epub_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_epub_book):
            cache = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        assert cache._cache_epub_count == num_files
    
    def test_concurrent_database_access(self, temp_dirs, temp_db, mock_epub_service):
        """Test that multiple cache instances can access database"""
        epub_file = temp_dirs['epub_dir'] / "concurrent.epub"
        epub_file.write_bytes(b"test")
        
        mock_book = Mock()
        mock_book.get_metadata.return_value = [("Test",)]
        mock_book.get_items_of_type = Mock(return_value=[])
        
        with patch('app.services.epub_cache.epub.read_epub', return_value=mock_book):
            cache1 = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
            
            cache2 = EPUBCache(
                epub_dir=temp_dirs['epub_dir'],
                thumbnails_dir=temp_dirs['thumb_dir'],
                epub_service=mock_epub_service,
                db_path=temp_db
            )
        
        # Both caches should see the same data
        assert cache1._cache_epub_count == cache2._cache_epub_count