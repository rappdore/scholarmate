import React, { useState, useEffect } from 'react';
import { epubService } from '../services/epubService';
import '../styles/epub.css';

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

interface EPUBStyles {
  styles: Array<{
    id: string;
    name: string;
    content: string;
  }>;
  count: number;
}

type Theme = 'dark' | 'light' | 'sepia';
type FontSize = 'small' | 'medium' | 'large' | 'xl';
type LineHeight = 'tight' | 'normal' | 'loose';

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
  const [epubStyles, setEpubStyles] = useState<EPUBStyles | null>(null);
  const [theme, setTheme] = useState<Theme>('dark');
  const [fontSize, setFontSize] = useState<FontSize>('medium');
  const [lineHeight, setLineHeight] = useState<LineHeight>('normal');
  const [showSettings, setShowSettings] = useState(false);

  useEffect(() => {
    if (!filename) return;
    loadNavigation();
    loadStyles();
  }, [filename]);

  // Inject EPUB styles into the document
  useEffect(() => {
    if (!epubStyles || !epubStyles.styles.length) return;

    const styleElement = document.createElement('style');
    styleElement.id = 'epub-custom-styles';

    // Combine all EPUB CSS and scope it to the container
    const combinedCSS = epubStyles.styles
      .map(style => {
        // Scope all CSS rules to the epub-content-container
        return style.content.replace(
          /([^{}]+)\s*{([^}]*)}/g,
          (match, selector, rules) => {
            // Don't scope @-rules or already scoped selectors
            if (
              selector.trim().startsWith('@') ||
              selector.includes('.epub-content-container')
            ) {
              return match;
            }
            // Scope the selector to the container
            const scopedSelector = selector
              .split(',')
              .map((s: string) => `.epub-content-container ${s.trim()}`)
              .join(', ');
            return `${scopedSelector} { ${rules} }`;
          }
        );
      })
      .join('\n');

    styleElement.textContent = combinedCSS;
    document.head.appendChild(styleElement);

    return () => {
      const existingStyle = document.getElementById('epub-custom-styles');
      if (existingStyle) {
        existingStyle.remove();
      }
    };
  }, [epubStyles]);

  const loadStyles = async () => {
    if (!filename) return;

    try {
      const stylesData = await epubService.getStyles(filename);
      setEpubStyles(stylesData);
    } catch (err) {
      console.error('Error loading EPUB styles:', err);
      // Non-critical error, continue without styles
    }
  };

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

  const getTruncatedTitle = (): string => {
    if (!filename) return '';
    const decodedTitle = decodeURIComponent(filename);
    const maxLength = 30; // Adjust this value as needed

    if (decodedTitle.length <= maxLength) {
      return decodedTitle;
    }

    return decodedTitle.substring(0, maxLength) + '...';
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
          <h2
            className="text-lg font-bold text-purple-400"
            title={filename && decodeURIComponent(filename)}
          >
            {getTruncatedTitle()}
          </h2>
          <div className="flex items-center gap-4">
            <div className="text-sm text-gray-400">
              Section {currentContent.spine_position + 1} of{' '}
              {currentContent.total_sections}
              {' • '}
              {currentContent.progress_percentage}% complete
            </div>
            {/* Settings Button */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
              title="Reading Settings"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="mb-4 p-4 bg-gray-700 rounded-lg border border-gray-600">
            <h3 className="text-sm font-bold text-white mb-3">
              Reading Settings
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Theme */}
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Theme
                </label>
                <select
                  value={theme}
                  onChange={e => setTheme(e.target.value as Theme)}
                  className="w-full bg-gray-600 border border-gray-500 rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="sepia">Sepia</option>
                </select>
              </div>

              {/* Font Size */}
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Font Size
                </label>
                <select
                  value={fontSize}
                  onChange={e => setFontSize(e.target.value as FontSize)}
                  className="w-full bg-gray-600 border border-gray-500 rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="small">Small</option>
                  <option value="medium">Medium</option>
                  <option value="large">Large</option>
                  <option value="xl">Extra Large</option>
                </select>
              </div>

              {/* Line Height */}
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Line Spacing
                </label>
                <select
                  value={lineHeight}
                  onChange={e => setLineHeight(e.target.value as LineHeight)}
                  className="w-full bg-gray-600 border border-gray-500 rounded px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="tight">Tight</option>
                  <option value="normal">Normal</option>
                  <option value="loose">Loose</option>
                </select>
              </div>
            </div>
          </div>
        )}

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
        {/* Chapter Title */}
        <div className="max-w-4xl mx-auto p-6 pb-2">
          <h1 className="text-2xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
            {getCurrentChapterTitle()}
          </h1>
        </div>

        {/* Chapter Content with EPUB Styling */}
        <div
          className="epub-content-container"
          data-theme={theme}
          data-font-size={fontSize}
          data-line-height={lineHeight}
          dangerouslySetInnerHTML={{ __html: currentContent.content }}
        />
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
            {epubStyles && epubStyles.count > 0 && (
              <span className="text-green-400">
                🎨 {epubStyles.count} styles loaded
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
