-- Migration: Create epub_highlights table for storing DOM-based highlights in EPUBs
-- Date: 2025-06-10
-- Description: Adds a dedicated table for EPUB text highlights with XPath positioning

-- Create table if it doesn't already exist
CREATE TABLE IF NOT EXISTS epub_highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epub_filename TEXT NOT NULL,
    nav_id TEXT NOT NULL,                -- Section identifier (finest granularity)
    chapter_id TEXT,                     -- Chapter identifier for grouping/display
    xpath TEXT NOT NULL,                 -- DOM XPath to the selected element (relative to section)
    start_offset INTEGER NOT NULL,       -- Character offset where highlight starts
    end_offset INTEGER NOT NULL,         -- Character offset where highlight ends
    highlight_text TEXT NOT NULL,        -- Exact highlighted text content
    color TEXT DEFAULT '#ffff00',        -- Highlight color (CSS hex or named)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Composite index for fast lookup by EPUB and nav_id (section-level retrieval)
CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_nav
ON epub_highlights(epub_filename, nav_id);

-- Composite index for fast lookup by EPUB and chapter_id (chapter aggregation)
CREATE INDEX IF NOT EXISTS idx_epub_highlights_epub_chapter
ON epub_highlights(epub_filename, chapter_id);
