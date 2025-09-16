import React, { useState, useEffect, useRef } from 'react';
import {
  epubService,
  type EPUBProgress,
  type EPUBNavigationResponse,
  type EPUBFlatNavigationItem,
  type EPUBNavigationItem,
} from '../services/epubService';
import '../styles/epub.css';
import EPUBHighlightMenu from './EPUBHighlightMenu';
import {
  getEPUBSelection,
  applyHighlight,
  clearAllHighlights,
  extractChapterIdFromNavId,
  type EPUBHighlight,
  type HighlightColor,
} from '../utils/epubHighlights';

interface EPUBViewerProps {
  filename?: string;
  onNavIdChange?: (navId: string) => void;
  onChapterInfoChange?: (chapterId: string, chapterTitle: string) => void;
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

type ChapterOption = {
  id: string;
  title: string;
  label: string;
  level: number;
};

export default function EPUBViewer({
  filename,
  onNavIdChange,
  onChapterInfoChange,
}: EPUBViewerProps) {
  const [navigation, setNavigation] = useState<EPUBNavigationResponse | null>(
    null
  );
  const [currentContent, setCurrentContent] = useState<ContentData | null>(
    null
  );
  const [currentNavId, setCurrentNavId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chapterOptions, setChapterOptions] = useState<ChapterOption[]>([]);
  const [epubStyles, setEpubStyles] = useState<EPUBStyles | null>(null);
  const [theme, setTheme] = useState<Theme>('dark');
  const [fontSize, setFontSize] = useState<FontSize>('medium');
  const [lineHeight, setLineHeight] = useState<LineHeight>('normal');
  const [showSettings, setShowSettings] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  // Progress tracking state
  const [isProgressLoaded, setIsProgressLoaded] = useState(false);
  const [savedProgress, setSavedProgress] = useState<EPUBProgress | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  // Scroll tracking
  const contentContainerRef = useRef<HTMLDivElement>(null);
  const [scrollPosition, setScrollPosition] = useState(0);

  // Highlighting state
  const [highlights, setHighlights] = useState<EPUBHighlight[]>([]);
  const [showHighlightMenu, setShowHighlightMenu] = useState(false);
  const [highlightMenuPosition, setHighlightMenuPosition] = useState({
    x: 0,
    y: 0,
  });
  const [selectedText, setSelectedText] = useState('');
  const [pendingSelection, setPendingSelection] = useState<{
    xpath: string;
    startOffset: number;
    endOffset: number;
    selectedText: string;
    navId: string;
    chapterId: string;
  } | null>(null);

  // Ref for the HTML container that holds the injected EPUB content
  const htmlRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!filename) return;
    loadNavigation();
    loadStyles();
    loadProgress();
    setInitialLoadDone(false); // Reset initial load flag for new EPUB
  }, [filename]);

  // Load highlights when content changes
  useEffect(() => {
    if (!filename || !currentNavId) return;
    loadSectionHighlights();
  }, [filename, currentNavId]);

  // Inject chapter HTML into the DOM and then apply highlights
  useEffect(() => {
    if (!currentContent) return;

    // Inject HTML only when chapter content string changes
    if (htmlRef.current) {
      htmlRef.current.innerHTML = currentContent.content;
    }

    // Apply highlights after the DOM has updated
    setTimeout(() => {
      applyHighlightsToContent();
    }, 50);
  }, [currentContent]);

  // Re-apply highlights whenever the number of highlights changes (e.g. after creating a new one)
  useEffect(() => {
    if (!currentContent || highlights.length === 0) return;

    // Re-apply on next tick so the DOM has settled after state updates
    setTimeout(() => {
      applyHighlightsToContent();
    }, 20);
  }, [highlights.length]);

  // Load saved progress and restore position
  const loadProgress = async () => {
    if (!filename) return;

    try {
      const progress = await epubService.getEPUBProgress(filename);
      setSavedProgress(progress);

      // Set loaded flag for both new and existing progress
      setIsProgressLoaded(true);

      console.log('Loaded EPUB progress:', progress);
    } catch (error) {
      console.error('Error loading EPUB progress:', error);
      setIsProgressLoaded(true); // Set loaded even on error to allow new progress
    }
  };

  // Save progress when navigation changes or scroll position changes
  const saveProgress = async (
    navId: string,
    contentData?: ContentData,
    currentScrollPos?: number
  ) => {
    if (!filename || !isProgressLoaded) return;

    try {
      // Determine chapter info from current navigation or content data
      const chapterInfo = getCurrentChapterInfo(navId, contentData);

      // Calculate navigation metadata for progress calculation
      const navMetadata = buildNavMetadata(navigation);

      // Calculate more accurate progress if we have navigation metadata
      const progressPercentage =
        contentData?.progress_percentage ||
        calculateProgressFromNavMetadata(navId, navMetadata) ||
        0;

      const progressData = {
        current_nav_id: navId,
        chapter_id: chapterInfo.chapterId,
        chapter_title: chapterInfo.chapterTitle,
        scroll_position: currentScrollPos || scrollPosition,
        total_sections: contentData?.total_sections || navigation?.spine_length,
        progress_percentage: progressPercentage,
        nav_metadata: navMetadata,
      };

      await epubService.saveEPUBProgress(filename, progressData);
      // Also update the local state to ensure UI is consistent
      setSavedProgress(prev => ({
        ...(prev ?? ({} as EPUBProgress)),
        ...progressData,
        last_updated: new Date().toISOString(),
      }));
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000); // Effect for 2s
      console.log('Saved EPUB progress:', progressData);
    } catch (error) {
      console.error('Error saving EPUB progress:', error);
    }
  };

  // Debounced save effect for scroll position
  useEffect(() => {
    if (!filename || !currentNavId || !isProgressLoaded || !currentContent)
      return;

    const timeoutId = setTimeout(() => {
      saveProgress(currentNavId, currentContent, scrollPosition);
    }, 1000); // Debounce scroll saves

    return () => clearTimeout(timeoutId);
  }, [
    filename,
    currentNavId,
    scrollPosition,
    isProgressLoaded,
    currentContent,
  ]);

  // Handle scroll position tracking
  const handleScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const target = event.target as HTMLDivElement;
    setScrollPosition(target.scrollTop);
  };

  // Helper function to get current chapter info
  const getCurrentChapterInfo = (navId: string, contentData?: ContentData) => {
    // Try to find chapter info from current content
    if (contentData) {
      const chapterTitle = getCurrentChapterTitle();
      return {
        chapterId: extractChapterIdFromNavId(navId),
        chapterTitle: chapterTitle || contentData.title,
      };
    }

    // Fallback to extracting from navigation
    return {
      chapterId: extractChapterIdFromNavId(navId),
      chapterTitle: getCurrentChapterTitle(),
    };
  };

  // Helper to get all section IDs for progress calculation
  const getAllSectionIds = (
    flatNav?: EPUBFlatNavigationItem[],
    navItems?: EPUBNavigationItem[]
  ): Array<{ id: string; title: string }> => {
    if (flatNav && flatNav.length > 0) {
      return flatNav
        .filter(isReadableFlatItem)
        .map(item => ({ id: item.id, title: item.title }));
    }

    if (!navItems) return [];

    const sections: Array<{ id: string; title: string }> = [];

    const extractSections = (items: EPUBNavigationItem[]) => {
      for (const item of items) {
        sections.push({ id: item.id, title: item.title });
        if (item.children.length > 0) {
          extractSections(item.children);
        }
      }
    };

    extractSections(navItems);
    return sections;
  };

  // Helper to get chapter metadata for progress tracking
  const getChapterMetadata = (
    flatNav?: EPUBFlatNavigationItem[],
    navItems?: EPUBNavigationItem[]
  ) => {
    if (flatNav && flatNav.length > 0) {
      return buildChapterMetadataFromFlat(flatNav);
    }

    if (!navItems) return [];

    return navItems.map(chapter => ({
      id: chapter.id,
      title: chapter.title,
      sections: chapter.children.map(section => ({
        id: section.id,
        title: section.title,
      })),
    }));
  };

  const buildChapterMetadataFromFlat = (flatNav: EPUBFlatNavigationItem[]) => {
    if (!flatNav.length) return [];

    const byId = new Map(flatNav.map(item => [item.id, item]));
    const readableIds = new Set(
      flatNav.filter(isReadableFlatItem).map(item => item.id)
    );

    const chapterMap = new Map<
      string,
      {
        id: string;
        title: string;
        sections: Array<{ id: string; title: string }>;
      }
    >();

    const ensureChapter = (item: EPUBFlatNavigationItem) => {
      if (!chapterMap.has(item.id)) {
        chapterMap.set(item.id, {
          id: item.id,
          title: item.title,
          sections: [],
        });
      }
      return chapterMap.get(item.id)!;
    };

    for (const item of flatNav) {
      if (item.level === 1 && readableIds.has(item.id)) {
        ensureChapter(item);
      }
    }

    for (const item of flatNav) {
      if (item.level <= 1 || !readableIds.has(item.id)) {
        continue;
      }

      let parentId = item.parent_id ?? null;
      let assigned = false;

      while (parentId) {
        const parent = byId.get(parentId);
        if (!parent) {
          break;
        }

        if (parent.level <= 1) {
          if (isReadableFlatItem(parent)) {
            const chapter = ensureChapter(parent);
            chapter.sections.push({ id: item.id, title: item.title });
            assigned = true;
            break;
          }

          parentId = parent.parent_id ?? null;
          continue;
        }

        parentId = parent.parent_id ?? null;
      }

      if (!assigned) {
        ensureChapter(item);
      }
    }

    return Array.from(chapterMap.values());
  };

  const buildNavMetadata = (
    navData: EPUBNavigationResponse | null
  ):
    | {
        all_sections: Array<{ id: string; title: string }>;
        chapters: Array<{
          id: string;
          title: string;
          sections: Array<{ id: string; title: string }>;
        }>;
        spine_length: number;
      }
    | undefined => {
    if (!navData) return undefined;

    return {
      all_sections: getAllSectionIds(
        navData.flat_navigation,
        navData.navigation
      ),
      chapters: getChapterMetadata(navData.flat_navigation, navData.navigation),
      spine_length: navData.spine_length,
    };
  };

  // Helper to calculate progress from navigation metadata
  const calculateProgressFromNavMetadata = (
    navId: string,
    metadata?: { all_sections: Array<{ id: string; title: string }> }
  ): number => {
    if (!metadata?.all_sections) return 0;

    const currentIndex = metadata.all_sections.findIndex(
      section => section.id === navId
    );
    if (currentIndex === -1) return 0;

    return (
      Math.round(
        ((currentIndex + 1) / metadata.all_sections.length) * 100 * 10
      ) / 10
    );
  };

  // Inject EPUB styles into the document
  useEffect(() => {
    if (!epubStyles || !epubStyles.styles.length) return;

    const styleElement = document.createElement('style');
    styleElement.id = 'epub-custom-styles';

    // Combine all EPUB CSS and scope it to the inner container
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

            // For body/html selectors, replace with container
            if (selector.trim() === 'body' || selector.trim() === 'html') {
              return `.epub-content-container { ${rules} }`;
            }

            // Scope the selector to the container
            const scopedSelector = selector
              .split(',')
              .map((s: string) => {
                const trimmedSelector = s.trim();
                // Don't double-scope already specific selectors
                if (trimmedSelector.includes('.epub-content-container')) {
                  return trimmedSelector;
                }
                return `.epub-content-container ${trimmedSelector}`;
              })
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
      const chapterOpts = buildChapterOptions(navData);
      setChapterOptions(chapterOpts);

      // Set this as loaded only after we have navigation
      console.log('Navigation loaded, preparing to restore progress...');
    } catch (err) {
      console.error('Error loading navigation:', err);
      setError('Failed to load EPUB navigation');
      setIsProgressLoaded(true); // Set loaded even on error
    } finally {
      setLoading(false);
    }
  };

  // Load content and handle progress restoration
  useEffect(() => {
    if (!navigation || !isProgressLoaded || !filename || initialLoadDone)
      return;

    // Try to restore from saved progress, otherwise load first chapter
    const navIdToLoad =
      savedProgress?.current_nav_id && savedProgress.current_nav_id !== 'start'
        ? savedProgress.current_nav_id
        : chapterOptions.length > 0
          ? chapterOptions[0].id
          : null;

    if (navIdToLoad) {
      loadContent(navIdToLoad, true); // Pass true to indicate this is initial load
      setInitialLoadDone(true); // Mark initial load as complete
    }
  }, [
    navigation,
    isProgressLoaded,
    chapterOptions,
    savedProgress,
    initialLoadDone,
  ]); // Restored savedProgress

  // Restore scroll position after content loads
  useEffect(() => {
    if (currentContent && savedProgress && contentContainerRef.current) {
      // Small delay to ensure content is rendered
      setTimeout(() => {
        if (contentContainerRef.current && savedProgress.scroll_position > 0) {
          contentContainerRef.current.scrollTop = savedProgress.scroll_position;
          setScrollPosition(savedProgress.scroll_position);
          console.log(
            'Restored scroll position:',
            savedProgress.scroll_position
          );
        }
      }, 100);
    }
  }, [currentContent, savedProgress]);

  const isReadableFlatItem = (item: EPUBFlatNavigationItem): boolean => {
    return (
      (item.spine_positions && item.spine_positions.length > 0) ||
      item.child_count === 0
    );
  };

  const buildChapterOptions = (
    navData: EPUBNavigationResponse
  ): ChapterOption[] => {
    if (navData.flat_navigation && navData.flat_navigation.length > 0) {
      return navData.flat_navigation.filter(isReadableFlatItem).map(item => {
        const prefix =
          item.level > 1
            ? `${Array(item.level - 1)
                .fill('> ')
                .join('')}`
            : '';
        return {
          id: item.id,
          title: item.title,
          label: `${prefix}${item.title}`,
          level: item.level,
        };
      });
    }

    return extractChapterOptionsFromTree(navData.navigation);
  };

  const extractChapterOptionsFromTree = (
    navItems: EPUBNavigationItem[],
    level: number = 1
  ): ChapterOption[] => {
    const options: ChapterOption[] = [];

    for (const item of navItems) {
      if (level === 1) {
        const navId = item.children.length > 0 ? getFinestNavId(item) : item.id;
        options.push({
          id: navId,
          title: item.title,
          label: item.title,
          level,
        });
      }

      if (item.children.length > 0) {
        options.push(
          ...extractChapterOptionsFromTree(item.children, level + 1)
        );
      }
    }

    return options;
  };

  const getFinestNavId = (item: EPUBNavigationItem): string => {
    if (item.children.length === 0) {
      return item.id;
    }
    return getFinestNavId(item.children[0]);
  };

  const loadContent = async (navId: string, isInitialLoad: boolean = false) => {
    if (!filename) return;

    try {
      setCurrentNavId(navId);
      const contentData = await epubService.getContent(filename, navId);
      setCurrentContent(contentData);

      // Save progress immediately when navigating (but not on initial restore)
      if (!isInitialLoad && isProgressLoaded) {
        await saveProgress(navId, contentData, 0); // Reset scroll on navigation
        setScrollPosition(0); // Reset scroll position
      }

      // Restore scroll position if it's an initial load with saved progress
      if (isInitialLoad && savedProgress?.scroll_position) {
        // Use a timeout to allow the content to render before scrolling
        setTimeout(() => {
          if (contentContainerRef.current) {
            contentContainerRef.current.scrollTop =
              savedProgress.scroll_position;
          }
        }, 100);
      } else if (contentContainerRef.current) {
        // Otherwise, scroll to top for new sections
        contentContainerRef.current.scrollTop = 0;
      }
    } catch (err: unknown) {
      console.error('Error loading content:', err);
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(`Error loading content: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentNavId && onNavIdChange) {
      onNavIdChange(currentNavId);
    }

    // Also notify chapter info changes
    if (currentNavId && onChapterInfoChange) {
      const chapterId = extractChapterIdFromNavId(currentNavId);
      const chapterTitle = getCurrentChapterTitle();
      onChapterInfoChange(chapterId, chapterTitle);
    }
  }, [currentNavId, onNavIdChange, onChapterInfoChange]);

  const handleChapterChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const newNavId = event.target.value;
    if (newNavId) {
      loadContent(newNavId);
    }
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

    if (navigation?.flat_navigation) {
      const match = navigation.flat_navigation.find(
        item => item.id === currentNavId
      );
      if (match) {
        return match.title;
      }
    }

    // Fallback: search through all navigation items
    const findTitleInNav = (items: EPUBNavigationItem[]): string => {
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

  // ========================================
  // HIGHLIGHT FUNCTIONALITY
  // ========================================

  const loadSectionHighlights = async () => {
    if (!filename || !currentNavId) return;

    try {
      const sectionHighlights = await epubService.getSectionHighlights(
        filename,
        currentNavId
      );
      setHighlights(sectionHighlights);
    } catch (error) {
      console.error('Error loading section highlights:', error);
      setHighlights([]);
    }
  };

  const applyHighlightsToContent = () => {
    console.log('🎨 Applying highlights to content, count:', highlights.length);

    // Clear existing highlights first
    clearAllHighlights();

    // Apply each highlight
    highlights.forEach((highlight, index) => {
      console.log(
        `🖍️ Applying highlight ${index + 1}:`,
        highlight.highlight_text
      );
      const success = applyHighlight(highlight);
      if (!success) {
        console.warn('❌ Failed to apply highlight:', highlight);
      }
    });
  };

  const handleTextSelection = (event: MouseEvent) => {
    console.log('🖱️ Mouse up event detected', event.target);

    // Don't process selection if clicking on the highlight menu
    const target = event.target as Element;
    if (target.closest('.epub-highlight-menu')) {
      console.log('🚫 Clicked on highlight menu, ignoring');
      return;
    }

    // Close existing menu first
    setShowHighlightMenu(false);

    // Small delay to allow selection to complete
    setTimeout(() => {
      if (!currentNavId) {
        console.log('❌ No currentNavId');
        return;
      }

      console.log('🔍 Checking for text selection...');
      const chapterId = extractChapterIdFromNavId(currentNavId);
      const selection = getEPUBSelection(currentNavId, chapterId);

      console.log('📝 Selection result:', selection);

      if (selection) {
        console.log('✅ Valid selection found, showing menu');
        // Show highlight menu
        setSelectedText(selection.selectedText);
        setPendingSelection(selection);
        setHighlightMenuPosition({ x: event.clientX, y: event.clientY });
        setShowHighlightMenu(true);
      } else {
        console.log('❌ No valid selection found');
      }
    }, 10);
  };

  const handleCreateHighlight = async (color: HighlightColor) => {
    console.log('🎨 Creating highlight with color:', color);
    console.log('📋 Pending selection:', pendingSelection);

    if (!filename || !pendingSelection) {
      console.log('❌ Missing filename or pending selection');
      return;
    }

    try {
      const newHighlight = await epubService.createEPUBHighlight(filename, {
        nav_id: pendingSelection.navId,
        chapter_id: pendingSelection.chapterId,
        xpath: pendingSelection.xpath,
        start_offset: pendingSelection.startOffset,
        end_offset: pendingSelection.endOffset,
        highlight_text: pendingSelection.selectedText,
        color,
      });

      console.log('✅ Highlight created:', newHighlight);

      // Add to local state - this will trigger the useEffect to reapply all highlights
      setHighlights(prev => [...prev, newHighlight]);

      // Clear selection
      window.getSelection()?.removeAllRanges();
      setPendingSelection(null);
    } catch (error) {
      console.error('❌ Error creating highlight:', error);

      // For now, create a local highlight even if API fails
      const localHighlight: EPUBHighlight = {
        id: Date.now().toString(),
        document_id: filename,
        nav_id: pendingSelection.navId,
        chapter_id: pendingSelection.chapterId,
        xpath: pendingSelection.xpath,
        start_offset: pendingSelection.startOffset,
        end_offset: pendingSelection.endOffset,
        highlight_text: pendingSelection.selectedText,
        color,
        created_at: new Date().toISOString(),
      };

      console.log('📝 Creating local highlight for testing:', localHighlight);
      setHighlights(prev => [...prev, localHighlight]);
    }
  };

  const handleCloseHighlightMenu = () => {
    setShowHighlightMenu(false);
    setPendingSelection(null);
    setSelectedText('');

    // Clear text selection
    window.getSelection()?.removeAllRanges();
  };

  // Add text selection listener to content container
  useEffect(() => {
    // Wait for content to be loaded and rendered
    if (!currentContent) {
      console.log('❌ No content loaded yet, skipping event listener setup');
      return;
    }

    // Small delay to ensure DOM is ready after content injection
    const timeoutId = setTimeout(() => {
      const container = contentContainerRef.current;
      console.log(
        '🎯 Setting up text selection listener on container:',
        container
      );

      if (!container) {
        console.log('❌ No container found for text selection listener');
        return;
      }

      console.log('✅ Adding mouseup event listener to container');
      container.addEventListener('mouseup', handleTextSelection);
    }, 50);

    return () => {
      clearTimeout(timeoutId);
      const container = contentContainerRef.current;
      if (container) {
        console.log('🧹 Cleaning up mouseup event listener');
        container.removeEventListener('mouseup', handleTextSelection);
      }
    };
  }, [currentContent, currentNavId]);

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
    <div className="h-full bg-gray-900 text-gray-300 flex flex-col overflow-hidden">
      {/* Header with Navigation Controls */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 flex-shrink-0">
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
              {savedProgress && (
                <span
                  className={`ml-2 ${
                    justSaved
                      ? 'text-green-300 animate-pulse'
                      : 'text-green-500'
                  }`}
                >
                  📖 Progress saved
                </span>
              )}
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
                  {option.label}
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
      <div
        className="flex-1 min-h-0 overflow-auto"
        ref={contentContainerRef}
        onScroll={handleScroll}
      >
        {/* Chapter Title */}
        <div className="max-w-4xl mx-auto p-6 pb-2">
          <h1 className="text-2xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
            {getCurrentChapterTitle()}
          </h1>
        </div>

        {/* EPUB Content with Two-Container Approach */}
        <div className="epub-outer-container">
          <div
            ref={htmlRef}
            className="epub-content-container"
            data-theme={theme}
            data-font-size={fontSize}
            data-line-height={lineHeight}
          />
        </div>

        {/* Highlight Context Menu */}
        {showHighlightMenu && (
          <EPUBHighlightMenu
            position={highlightMenuPosition}
            selectedText={selectedText}
            onHighlight={handleCreateHighlight}
            onClose={handleCloseHighlightMenu}
          />
        )}
      </div>

      {/* Footer with Progress */}
      <div className="bg-gray-800 border-t border-gray-700 p-4 flex-shrink-0">
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
            {savedProgress && (
              <span className="text-blue-400">
                💾 Last read:{' '}
                {new Date(
                  savedProgress.last_updated || ''
                ).toLocaleDateString()}
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
