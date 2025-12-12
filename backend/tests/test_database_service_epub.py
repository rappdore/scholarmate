"""
Unit tests for DatabaseService EPUB documents table functionality.

Tests cover:
- EPUB documents table creation
- Index creation for epub_documents
- Table schema validation
- Integration with EPUBDocumentsService
- Migration compatibility
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.services.database_service import DatabaseService


@pytest.fixture
def temp_db_path():
    """Create temporary database path"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def db_service(temp_db_path):
    """Create DatabaseService instance with temp database"""
    return DatabaseService(db_path=temp_db_path)


class TestEPUBDocumentsTableCreation:
    """Test epub_documents table creation"""
    
    def test_table_created_on_init(self, db_service):
        """Test that epub_documents table is created during initialization"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='epub_documents'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[0] == 'epub_documents'
    
    def test_table_schema_has_required_columns(self, db_service):
        """Test that epub_documents table has all required columns"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("PRAGMA table_info(epub_documents)")
        columns = cursor.fetchall()
        
        conn.close()
        
        column_names = [col[1] for col in columns]
        
        # Verify all required columns exist
        assert 'id' in column_names
        assert 'filename' in column_names
        assert 'title' in column_names
        assert 'author' in column_names
        assert 'chapters' in column_names
        assert 'subject' in column_names
        assert 'publisher' in column_names
        assert 'language' in column_names
        assert 'file_size' in column_names
        assert 'file_path' in column_names
        assert 'thumbnail_path' in column_names
        assert 'created_date' in column_names
        assert 'modified_date' in column_names
        assert 'added_at' in column_names
        assert 'last_accessed' in column_names
        assert 'metadata_json' in column_names
    
    def test_id_column_is_primary_key(self, db_service):
        """Test that id column is the primary key"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(epub_documents)")
        columns = cursor.fetchall()
        
        conn.close()
        
        # Find id column
        id_column = next((col for col in columns if col[1] == 'id'), None)
        assert id_column is not None
        
        # Check if it's a primary key (pk field is 5th element, 1-indexed)
        assert id_column[5] == 1  # pk flag
    
    def test_filename_column_is_unique(self, db_service):
        """Test that filename column has unique constraint"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Try to insert duplicate filenames
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('test.epub', 1)
        """)
        
        # Second insert with same filename should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO epub_documents (filename, chapters)
                VALUES ('test.epub', 2)
            """)
        
        conn.close()
    
    def test_chapters_default_value(self, db_service):
        """Test that chapters column has default value of 0"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Insert without specifying chapters
        cursor.execute("""
            INSERT INTO epub_documents (filename)
            VALUES ('default_test.epub')
        """)
        conn.commit()
        
        # Retrieve the record
        cursor.execute("""
            SELECT chapters FROM epub_documents 
            WHERE filename = 'default_test.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[0] == 0
    
    def test_timestamps_have_defaults(self, db_service):
        """Test that timestamp columns have default values"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Insert minimal record
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('timestamp_test.epub', 1)
        """)
        conn.commit()
        
        # Retrieve timestamps
        cursor.execute("""
            SELECT added_at, last_accessed FROM epub_documents
            WHERE filename = 'timestamp_test.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[0] is not None  # added_at
        assert result[1] is not None  # last_accessed


class TestEPUBDocumentsIndexes:
    """Test indexes for epub_documents table"""
    
    def test_filename_index_exists(self, db_service):
        """Test that index on filename exists"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Get list of indexes
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='epub_documents'
        """)
        indexes = cursor.fetchall()
        
        conn.close()
        
        index_names = [idx[0] for idx in indexes]
        
        # Check for filename index
        assert any('filename' in name.lower() for name in index_names)
    
    def test_last_accessed_index_exists(self, db_service):
        """Test that index on last_accessed exists"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND tbl_name='epub_documents'
        """)
        indexes = cursor.fetchall()
        
        conn.close()
        
        index_names = [idx[0] for idx in indexes]
        
        # Check for last_accessed index
        assert any('accessed' in name.lower() for name in index_names)
    
    def test_indexes_improve_query_performance(self, db_service):
        """Test that indexes are used for common queries"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Insert test data
        for i in range(10):
            cursor.execute("""
                INSERT INTO epub_documents (filename, chapters)
                VALUES (?, 1)
            """, (f"book_{i}.epub",))
        conn.commit()
        
        # Check query plan for filename lookup
        cursor.execute("""
            EXPLAIN QUERY PLAN
            SELECT * FROM epub_documents WHERE filename = 'book_5.epub'
        """)
        plan = cursor.fetchall()
        
        conn.close()
        
        # Query plan should mention index usage
        plan_str = str(plan).lower()
        assert 'index' in plan_str or 'search' in plan_str


class TestEPUBDocumentsDataOperations:
    """Test basic data operations on epub_documents table"""
    
    def test_insert_complete_record(self, db_service):
        """Test inserting a complete EPUB document record"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (
                filename, title, author, chapters, subject, publisher, language,
                file_size, file_path, thumbnail_path, created_date, modified_date,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'complete.epub',
            'Complete Book',
            'Complete Author',
            15,
            'Fiction',
            'Complete Publisher',
            'en',
            1024000,
            '/path/to/complete.epub',
            '/path/to/thumbnail.jpg',
            '2024-01-01T00:00:00',
            '2024-01-02T00:00:00',
            '{"extra": "data"}'
        ))
        conn.commit()
        
        # Verify insertion
        cursor.execute("""
            SELECT * FROM epub_documents WHERE filename = 'complete.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[1] == 'complete.epub'  # filename
        assert result[2] == 'Complete Book'  # title
    
    def test_insert_minimal_record(self, db_service):
        """Test inserting with only required fields"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('minimal.epub', 3)
        """)
        conn.commit()
        
        cursor.execute("""
            SELECT * FROM epub_documents WHERE filename = 'minimal.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        assert result[1] == 'minimal.epub'
        assert result[3] == 3  # chapters
    
    def test_update_record(self, db_service):
        """Test updating an existing record"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Insert initial record
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters, title)
            VALUES ('update.epub', 5, 'Original Title')
        """)
        conn.commit()
        
        # Update the record
        cursor.execute("""
            UPDATE epub_documents
            SET title = 'Updated Title', chapters = 10
            WHERE filename = 'update.epub'
        """)
        conn.commit()
        
        # Verify update
        cursor.execute("""
            SELECT title, chapters FROM epub_documents
            WHERE filename = 'update.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result[0] == 'Updated Title'
        assert result[1] == 10
    
    def test_delete_record(self, db_service):
        """Test deleting a record"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('delete.epub', 1)
        """)
        conn.commit()
        
        # Delete the record
        cursor.execute("""
            DELETE FROM epub_documents WHERE filename = 'delete.epub'
        """)
        conn.commit()
        
        # Verify deletion
        cursor.execute("""
            SELECT * FROM epub_documents WHERE filename = 'delete.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is None
    
    def test_query_by_last_accessed(self, db_service):
        """Test querying records ordered by last_accessed"""
        import time
        
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Insert multiple records with delays
        for i in range(3):
            cursor.execute("""
                INSERT INTO epub_documents (filename, chapters)
                VALUES (?, 1)
            """, (f"book_{i}.epub",))
            conn.commit()
            time.sleep(0.05)
        
        # Query ordered by last_accessed
        cursor.execute("""
            SELECT filename FROM epub_documents
            ORDER BY last_accessed DESC
        """)
        results = cursor.fetchall()
        
        conn.close()
        
        # Most recent should be first
        assert results[0][0] == 'book_2.epub'
        assert results[-1][0] == 'book_0.epub'


class TestTableCompatibility:
    """Test compatibility with other tables and services"""
    
    def test_coexists_with_pdf_documents_table(self, db_service):
        """Test that epub_documents table coexists with pdf_documents table"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Check both tables exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('epub_documents', 'pdf_documents')
        """)
        tables = cursor.fetchall()
        
        conn.close()
        
        table_names = [t[0] for t in tables]
        assert 'epub_documents' in table_names
        assert 'pdf_documents' in table_names
    
    def test_similar_schema_to_pdf_documents(self, db_service):
        """Test that epub_documents has similar structure to pdf_documents"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # Get columns for both tables
        cursor.execute("PRAGMA table_info(epub_documents)")
        epub_columns = {col[1] for col in cursor.fetchall()}
        
        cursor.execute("PRAGMA table_info(pdf_documents)")
        pdf_columns = {col[1] for col in cursor.fetchall()}
        
        conn.close()
        
        # Common columns should exist in both
        common_expected = {
            'id', 'filename', 'title', 'author', 'file_size', 'file_path',
            'thumbnail_path', 'created_date', 'modified_date', 'added_at',
            'last_accessed', 'metadata_json'
        }
        
        assert common_expected.issubset(epub_columns)
        assert common_expected.issubset(pdf_columns)
    
    def test_epub_specific_columns(self, db_service):
        """Test that epub_documents has EPUB-specific columns"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(epub_documents)")
        columns = cursor.fetchall()
        
        conn.close()
        
        column_names = [col[1] for col in columns]
        
        # EPUB-specific columns
        assert 'chapters' in column_names
        assert 'publisher' in column_names
        assert 'language' in column_names


class TestDatabaseIntegration:
    """Test integration with DatabaseService"""
    
    def test_database_service_initializes_epub_table(self, temp_db_path):
        """Test that creating DatabaseService initializes epub_documents table"""
        service = DatabaseService(db_path=temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='epub_documents'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
    
    def test_table_survives_service_restart(self, temp_db_path):
        """Test that epub_documents table persists across service restarts"""
        # Create first service instance
        service1 = DatabaseService(db_path=temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('persistent.epub', 1)
        """)
        conn.commit()
        conn.close()
        
        del service1
        
        # Create second service instance
        service2 = DatabaseService(db_path=temp_db_path)
        
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM epub_documents WHERE filename = 'persistent.epub'
        """)
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[1] == 'persistent.epub'


class TestEdgeCasesAndConstraints:
    """Test edge cases and constraint validation"""
    
    def test_null_values_allowed_for_optional_fields(self, db_service):
        """Test that NULL is allowed for optional fields"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters, title, author)
            VALUES ('nulls.epub', 1, NULL, NULL)
        """)
        conn.commit()
        
        cursor.execute("""
            SELECT title, author FROM epub_documents
            WHERE filename = 'nulls.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result[0] is None
        assert result[1] is None
    
    def test_large_metadata_json(self, db_service):
        """Test storing large JSON in metadata_json field"""
        import json
        
        large_metadata = {
            f"key_{i}": f"value_{i}" * 50
            for i in range(100)
        }
        metadata_str = json.dumps(large_metadata)
        
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters, metadata_json)
            VALUES ('large_json.epub', 1, ?)
        """, (metadata_str,))
        conn.commit()
        
        cursor.execute("""
            SELECT metadata_json FROM epub_documents
            WHERE filename = 'large_json.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result is not None
        retrieved_metadata = json.loads(result[0])
        assert len(retrieved_metadata) == 100
    
    def test_unicode_in_text_fields(self, db_service):
        """Test Unicode characters in text fields"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters, title, author)
            VALUES (?, 1, ?, ?)
        """, (
            'unicode_книга_📚.epub',
            'Title with émojis 📖 and 漢字',
            'Author Иванов García'
        ))
        conn.commit()
        
        cursor.execute("""
            SELECT filename, title, author FROM epub_documents
            WHERE filename LIKE '%unicode%'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert '📚' in result[0]
        assert '📖' in result[1]
        assert 'García' in result[2]
    
    def test_negative_file_size(self, db_service):
        """Test that negative file size can be stored (validation is app layer)"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        # SQLite allows negative numbers
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters, file_size)
            VALUES ('negative.epub', 1, -100)
        """)
        conn.commit()
        
        cursor.execute("""
            SELECT file_size FROM epub_documents WHERE filename = 'negative.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result[0] == -100
    
    def test_zero_chapters(self, db_service):
        """Test that zero chapters is valid"""
        conn = sqlite3.connect(db_service.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO epub_documents (filename, chapters)
            VALUES ('empty_book.epub', 0)
        """)
        conn.commit()
        
        cursor.execute("""
            SELECT chapters FROM epub_documents WHERE filename = 'empty_book.epub'
        """)
        result = cursor.fetchone()
        
        conn.close()
        
        assert result[0] == 0