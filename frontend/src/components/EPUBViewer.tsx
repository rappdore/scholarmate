import React, { useState, useEffect } from 'react';
import { epubService } from '../services/epubService';

interface EPUBViewerProps {
  filename?: string;
}

interface NavigationItem {
  id: string;
  title: string;
  href?: string;
  level: number;
  children: NavigationItem[];
}

interface NavigationData {
  navigation: NavigationItem[];
  spine_length: number;
  has_toc: boolean;
}

interface ContentData {
  nav_id: string;
  title: string;
  content: string;
  spine_position: number;
  total_sections: number;
  progress_percentage: number;
  previous_nav_id: string | null;
  next_nav_id: string | null;
}

export default function EPUBViewer({ filename }: EPUBViewerProps) {
  const [navigation, setNavigation] = useState<NavigationData | null>(null);
  const [currentContent, setCurrentContent] = useState<ContentData | null>(
    null
  );
  const [currentNavId, setCurrentNavId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chapterOptions, setChapterOptions] = useState<
    { id: string; title: string }[]
  >([]);

  useEffect(() => {
    if (!filename) return;
    loadNavigation();
  }, [filename]);

  const loadNavigation = async () => {
    if (!filename) return;

    try {
      setLoading(true);
      setError(null);

      const navData = await epubService.getNavigation(filename);
      setNavigation(navData);

      // Create flat list of chapter-level options for dropdown
      // Display only top-level items (chapters) but store finest navigation ID
      const chapterOpts = extractChapterOptions(navData.navigation);
      setChapterOptions(chapterOpts);

      // Load first chapter by default
      if (chapterOpts.length > 0) {
        await loadContent(chapterOpts[0].id);
      }
    } catch (err) {
      console.error('Error loading navigation:', err);
      setError('Failed to load EPUB navigation');
    } finally {
      setLoading(false);
    }
  };

  const extractChapterOptions = (
    navItems: NavigationItem[]
  ): { id: string; title: string }[] => {
    const options: { id: string; title: string }[] = [];

    const processItems = (items: NavigationItem[], level: number = 1) => {
      for (const item of items) {
        // For display, we show chapter-level (level 1) items
        // But we store the finest navigation level available
        if (level === 1) {
          // If this chapter has subsections, use the first subsection ID for navigation
          const navId =
            item.children.length > 0 ? getFinestNavId(item) : item.id;
          options.push({
            id: navId,
            title: item.title,
          });
        }

        // Process children for nested navigation
        if (item.children.length > 0) {
          processItems(item.children, level + 1);
        }
      }
    };

    processItems(navItems);
    return options;
  };

  const getFinestNavId = (item: NavigationItem): string => {
    // Recursively find the finest (deepest) navigation ID
    if (item.children.length === 0) {
      return item.id;
    }
    return getFinestNavId(item.children[0]);
  };

  const loadContent = async (navId: string) => {
    if (!filename) return;

    try {
      setCurrentNavId(navId);
      const contentData = await epubService.getContent(filename, navId);
      setCurrentContent(contentData);
    } catch (err) {
      console.error('Error loading content:', err);
      setError('Failed to load chapter content');
    }
  };

  const handleChapterChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedNavId = event.target.value;
    loadContent(selectedNavId);
  };

  const handlePreviousChapter = () => {
    if (currentContent?.previous_nav_id) {
      loadContent(currentContent.previous_nav_id);
    }
  };

  const handleNextChapter = () => {
    if (currentContent?.next_nav_id) {
      loadContent(currentContent.next_nav_id);
    }
  };

  const getCurrentChapterTitle = (): string => {
    if (!currentNavId) return '';

    // Find the chapter title that corresponds to current nav ID
    for (const option of chapterOptions) {
      if (option.id === currentNavId) {
        return option.title;
      }
    }

    // Fallback: search through all navigation items
    const findTitleInNav = (items: NavigationItem[]): string => {
      for (const item of items) {
        if (item.id === currentNavId) {
          return item.title;
        }
        if (item.children.length > 0) {
          const childTitle = findTitleInNav(item.children);
          if (childTitle) return childTitle;
        }
      }
      return '';
    };

    return navigation ? findTitleInNav(navigation.navigation) : '';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-gray-300">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-t-4 border-purple-400 mx-auto mb-4"></div>
          <h2 className="text-xl font-bold mb-2">Loading EPUB...</h2>
          <p className="text-gray-400">Extracting chapters and content</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-gray-300">
        <div className="text-center">
          <div className="text-red-400 text-4xl mb-4">❌</div>
          <h2 className="text-xl font-bold mb-2">Error Loading EPUB</h2>
          <p className="text-gray-400 mb-4">{error}</p>
          <button
            onClick={loadNavigation}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!navigation || !currentContent) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-900 text-gray-300">
        <div className="text-center">
          <div className="text-6xl mb-6">📚</div>
          <h2 className="text-2xl font-bold mb-4">No Content Available</h2>
          <p className="text-gray-400">
            This EPUB appears to be empty or corrupted.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-900 text-gray-300 flex flex-col">
      {/* Header with Navigation Controls */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-bold text-purple-400">
            {filename && decodeURIComponent(filename)}
          </h2>
          <div className="text-sm text-gray-400">
            Section {currentContent.spine_position + 1} of{' '}
            {currentContent.total_sections}
            {' • '}
            {currentContent.progress_percentage}% complete
          </div>
        </div>

        {/* Chapter Selection and Navigation */}
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <select
              value={currentNavId || ''}
              onChange={handleChapterChange}
              className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              {chapterOptions.map(option => (
                <option key={option.id} value={option.id}>
                  {option.title}
                </option>
              ))}
            </select>
          </div>

          {/* Previous/Next Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handlePreviousChapter}
              disabled={!currentContent.previous_nav_id}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              Previous
            </button>
            <button
              onClick={handleNextChapter}
              disabled={!currentContent.next_nav_id}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-lg transition-colors flex items-center gap-2"
            >
              Next
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6">
          {/* Chapter Title */}
          <h1 className="text-2xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
            {getCurrentChapterTitle()}
          </h1>

          {/* Chapter Content */}
          <div
            className="prose prose-invert prose-lg max-w-none"
            style={{
              lineHeight: '1.6',
              fontSize: '16px',
              color: '#e0e0e0',
            }}
            dangerouslySetInnerHTML={{ __html: currentContent.content }}
          />
        </div>
      </div>

      {/* Footer with Progress */}
      <div className="bg-gray-800 border-t border-gray-700 p-4">
        <div className="flex items-center justify-between text-sm text-gray-400">
          <div>{currentContent.progress_percentage}% of book completed</div>
          <div className="flex gap-4">
            <span>
              Section {currentContent.spine_position + 1} of{' '}
              {currentContent.total_sections}
            </span>
            {navigation.has_toc && (
              <span className="text-purple-400">
                📖 Table of Contents Available
              </span>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
          <div
            className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${currentContent.progress_percentage}%` }}
          />
        </div>
      </div>
    </div>
  );
}
