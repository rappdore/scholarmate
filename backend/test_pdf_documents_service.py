"""
Quick test script for PDFDocumentsService

Run this to verify the service is working correctly:
    python test_pdf_documents_service.py
"""

import os
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3

from app.services.pdf_documents_service import PDFDocumentsService


def test_pdf_documents_service():
    """
    Execute a sequence of basic CRUD integration tests for PDFDocumentsService using a temporary SQLite test database.
    
    Performs create, read (by filename and id), update, list, delete, and last-accessed-update operations against PDFDocumentsService and asserts expected outcomes to verify service behavior. Initializes the pdf_documents schema in a test database before running tests and removes the test database afterward.
    
    Side effects:
    - Creates a test database at data/test_pdf_documents.db and the data/ directory if needed.
    - Deletes the test database file when finished.
    """
    print("Testing PDFDocumentsService...")

    # Use test database to avoid affecting real data
    db_path = "data/test_pdf_documents.db"

    # Clean up test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)

    # Create data directory if needed
    os.makedirs("data", exist_ok=True)

    # Create the pdf_documents table in test database
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pdf_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                title TEXT,
                author TEXT,
                num_pages INTEGER NOT NULL,
                subject TEXT,
                creator TEXT,
                producer TEXT,
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pdf_documents_filename
            ON pdf_documents(filename)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_pdf_documents_accessed
            ON pdf_documents(last_accessed)
        """)
        conn.commit()

    # Initialize service
    service = PDFDocumentsService(db_path)

    # Test 1: Create a PDF document
    print("\n1. Testing create_or_update (create)...")
    pdf_id = service.create_or_update(
        filename="test.pdf",
        num_pages=100,
        title="Test PDF",
        author="Test Author",
        file_size=1024000,
        created_date="2025-01-01T00:00:00",
        modified_date="2025-01-02T00:00:00",
    )
    print(f"   ✓ Created PDF with ID: {pdf_id}")
    assert pdf_id > 0, "PDF ID should be positive"

    # Test 2: Get by filename
    print("\n2. Testing get_by_filename...")
    doc = service.get_by_filename("test.pdf")
    print(f"   ✓ Retrieved: {doc['title']} by {doc['author']}")
    assert doc is not None, "Document should exist"
    assert doc["filename"] == "test.pdf"
    assert doc["num_pages"] == 100
    assert doc["title"] == "Test PDF"

    # Test 3: Get by ID
    print("\n3. Testing get_by_id...")
    doc_by_id = service.get_by_id(pdf_id)
    print(f"   ✓ Retrieved by ID: {doc_by_id['filename']}")
    assert doc_by_id is not None
    assert doc_by_id["id"] == pdf_id

    # Test 4: Update existing document
    print("\n4. Testing create_or_update (update)...")
    updated_id = service.create_or_update(
        filename="test.pdf",
        num_pages=100,
        title="Updated Test PDF",
        author="Updated Author",
        subject="Test Subject",
    )
    print(f"   ✓ Updated PDF, ID: {updated_id}")
    assert updated_id == pdf_id, "ID should remain the same"

    updated_doc = service.get_by_filename("test.pdf")
    assert updated_doc["title"] == "Updated Test PDF"
    assert updated_doc["subject"] == "Test Subject"

    # Test 5: List all
    print("\n5. Testing list_all...")
    all_docs = service.list_all()
    print(f"   ✓ Found {len(all_docs)} documents")
    assert len(all_docs) == 1

    # Test 6: Create another document
    print("\n6. Creating second document...")
    service.create_or_update(
        filename="test2.pdf",
        num_pages=50,
        title="Second PDF",
    )
    all_docs = service.list_all()
    print(f"   ✓ Now have {len(all_docs)} documents")
    assert len(all_docs) == 2

    # Test 7: Delete by filename
    print("\n7. Testing delete_by_filename...")
    deleted = service.delete_by_filename("test2.pdf")
    print(f"   ✓ Deleted: {deleted}")
    assert deleted is True

    all_docs = service.list_all()
    assert len(all_docs) == 1

    # Test 8: Update last accessed
    print("\n8. Testing update_last_accessed...")
    service.update_last_accessed(pdf_id)
    print("   ✓ Updated last_accessed timestamp")

    # Cleanup
    print("\n9. Cleanup...")
    os.remove(db_path)
    print("   ✓ Test database removed")

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_pdf_documents_service()