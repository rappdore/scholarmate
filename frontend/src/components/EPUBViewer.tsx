import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from 'react';
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
import { ttsService } from '../services/ttsService';
import {
  highlightByOffset,
  clearAllHighlights as clearTTSHighlights,
} from '../utils/ttsHighlight';
import {
  type TextPositionMap,
  buildTextPositionMap,
} from '../utils/textPositionMap';
import { useEpubSessionTracking } from '../hooks/useEpubSessionTracking';
import type { NavSection } from '../types/epubStatistics';
import { useEPUBHighlightsContext } from '../contexts/EPUBHighlightsContext';

interface EPUBViewerProps {
  epubId?: number;
  filename?: string;
  onNavIdChange?: (navId: string) => void;
  onChapterInfoChange?: (chapterId: string, chapterTitle: string) => void;
  onScrollProgressChange?: (scrollProgress: number) => void;
  targetHighlight?: EPUBHighlight | null;
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
  epubId,
  filename,
  onNavIdChange,
  onChapterInfoChange,
  onScrollProgressChange,
  targetHighlight,
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
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = sessionStorage.getItem('epub-reader-theme');
    return (saved as Theme) || 'sepia';
  });
  const [fontSize, setFontSize] = useState<FontSize>(() => {
    const saved = sessionStorage.getItem('epub-reader-font-size');
    return (saved as FontSize) || 'medium';
  });
  const [lineHeight, setLineHeight] = useState<LineHeight>(() => {
    const saved = sessionStorage.getItem('epub-reader-line-height');
    return (saved as LineHeight) || 'normal';
  });
  const [showSettings, setShowSettings] = useState(false);
  const [justSaved, setJustSaved] = useState(false);

  // Progress tracking state
  const [isProgressLoaded, setIsProgressLoaded] = useState(false);
  const [savedProgress, setSavedProgress] = useState<EPUBProgress | null>(null);
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  // Scroll tracking
  const contentContainerRef = useRef<HTMLDivElement>(null);
  const [scrollPosition, setScrollPosition] = useState(0);

  // Highlighting state - use shared context
  const {
    createHighlight: createContextHighlight,
    setCurrentEpubId,
    getHighlightsForSection,
  } = useEPUBHighlightsContext();

  // Get highlights for current section only (for rendering in the viewer)
  const sectionHighlights = useMemo(() => {
    if (!currentNavId) return [];
    return getHighlightsForSection(currentNavId);
  }, [currentNavId, getHighlightsForSection]);

  const [showHighlightMenu, setShowHighlightMenu] = useState(false);
  const [highlightMenuPosition, setHighlightMenuPosition] = useState({
    x: 0,
    y: 0,
  });
  const [selectedText, setSelectedText] = useState('');
  const [pendingSelection, setPendingSelection] = useState<{
    startXPath: string;
    startOffset: number;
    endXPath: string;
    endOffset: number;
    text: string;
    navId: string;
    chapterId?: string;
  } | null>(null);

  // Ref for the HTML container that holds the injected EPUB content
  const htmlRef = useRef<HTMLDivElement>(null);

  // TTS state
  const [isTTSPlaying, setIsTTSPlaying] = useState(false);
  const ttsCleanupRef = useRef<(() => void) | null>(null);
  const textPositionMapRef = useRef<TextPositionMap | null>(null);
  // Base offset: where the TTS text starts in the full document
  // Backend offsets are relative to the text sent, so we add this to get absolute positions
  const ttsBaseOffsetRef = useRef<number>(0);

  // Track scroll height for progress calculation
  const [scrollHeight, setScrollHeight] = useState(0);
  const [clientHeight, setClientHeight] = useState(0);

  // Extract nav sections with word counts for session tracking
  const navSections = useMemo<NavSection[] | undefined>(() => {
    const allSections = savedProgress?.nav_metadata?.all_sections;
    if (!allSections || !Array.isArray(allSections)) return undefined;

    return allSections.map(section => ({
      id: section.id,
      title: section.title || '',
      href: section.href || '',
      word_count: section.word_count || 0,
    }));
  }, [savedProgress?.nav_metadata]);

  // Calculate scroll progress (0.0 - 1.0) within current section
  const scrollProgressRatio = useMemo(() => {
    if (!scrollHeight || !clientHeight || scrollHeight <= clientHeight) {
      return 0;
    }
    const maxScroll = scrollHeight - clientHeight;
    if (maxScroll <= 0) return 1;
    return Math.min(1, Math.max(0, scrollPosition / maxScroll));
  }, [scrollPosition, scrollHeight, clientHeight]);

  // Notify parent of scroll progress changes (for chat context)
  useEffect(() => {
    onScrollProgressChange?.(scrollProgressRatio);
  }, [scrollProgressRatio, onScrollProgressChange]);

  // Get book status for tracking
  const bookStatus = (savedProgress?.status || 'new') as
    | 'new'
    | 'reading'
    | 'finished';

  // Session tracking hook
  const { trackingEnabled, setTrackingEnabled, wordsRead } =
    useEpubSessionTracking({
      epubId,
      navSections,
      currentNavId,
      scrollProgress: scrollProgressRatio,
      bookStatus,
    });

  useEffect(() => {
    if (!epubId) return;
    loadNavigation();
    loadStyles();
    loadProgress();
    setInitialLoadDone(false); // Reset initial load flag for new EPUB
  }, [epubId]);

  // Persist reader settings to sessionStorage
  useEffect(() => {
    sessionStorage.setItem('epub-reader-theme', theme);
  }, [theme]);

  useEffect(() => {
    sessionStorage.setItem('epub-reader-font-size', fontSize);
  }, [fontSize]);

  useEffect(() => {
    sessionStorage.setItem('epub-reader-line-height', lineHeight);
  }, [lineHeight]);

  // Set current EPUB ID in context when it changes (this triggers highlight loading)
  useEffect(() => {
    setCurrentEpubId(epubId ?? null);
  }, [epubId, setCurrentEpubId]);

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

  // Re-apply highlights whenever the section highlights change (e.g. after creating a new one or color update)
  useEffect(() => {
    if (!currentContent) return;

    // Allow effect to run even with 0 highlights to clear stale DOM highlights
    if (sectionHighlights.length === 0) {
      clearAllHighlights();
      return;
    }

    // Re-apply on next tick so the DOM has settled after state updates
    setTimeout(() => {
      applyHighlightsToContent();
    }, 20);
  }, [sectionHighlights]);

  // Load saved progress and restore position
  const loadProgress = async () => {
    if (!epubId) return;

    try {
      const progress = await epubService.getEPUBProgress(epubId);
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
    if (!epubId || !isProgressLoaded) return;

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
        scroll_position: Math.round(currentScrollPos ?? scrollPosition),
        total_sections: contentData?.total_sections || navigation?.spine_length,
        progress_percentage: progressPercentage,
        nav_metadata: navMetadata,
      };

      await epubService.saveEPUBProgress(epubId, progressData);
      // Also update the local state to ensure UI is consistent
      // IMPORTANT: Preserve the existing nav_metadata from backend (has word counts)
      // Don't overwrite it with the locally-built navMetadata (no word counts)
      setSavedProgress(prev => ({
        ...(prev ?? ({} as EPUBProgress)),
        ...progressData,
        nav_metadata: prev?.nav_metadata ?? progressData.nav_metadata,
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
    if (!epubId || !currentNavId || !isProgressLoaded || !currentContent)
      return;

    const timeoutId = setTimeout(() => {
      saveProgress(currentNavId, currentContent, scrollPosition);
    }, 1000); // Debounce scroll saves

    return () => clearTimeout(timeoutId);
  }, [epubId, currentNavId, scrollPosition, isProgressLoaded, currentContent]);

  // Handle scroll position tracking
  const handleScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const target = event.target as HTMLDivElement;
    setScrollPosition(target.scrollTop);
    setScrollHeight(target.scrollHeight);
    setClientHeight(target.clientHeight);
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
  ): Array<{ id: string; title: string; href?: string }> => {
    if (flatNav && flatNav.length > 0) {
      return flatNav
        .filter(isReadableFlatItem)
        .map(item => ({ id: item.id, title: item.title, href: item.href }));
    }

    if (!navItems) return [];

    const sections: Array<{ id: string; title: string; href?: string }> = [];

    const extractSections = (items: EPUBNavigationItem[]) => {
      for (const item of items) {
        sections.push({ id: item.id, title: item.title, href: item.href });
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
        all_sections: Array<{ id: string; title: string; href?: string }>;
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
    if (!epubId) return;

    try {
      const stylesData = await epubService.getStyles(epubId);
      setEpubStyles(stylesData);
    } catch (err) {
      console.error('Error loading EPUB styles:', err);
      // Non-critical error, continue without styles
    }
  };

  const loadNavigation = async () => {
    if (!epubId) return;

    try {
      setLoading(true);
      setError(null);

      const navData = await epubService.getNavigation(epubId);
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
    if (!navigation || !isProgressLoaded || !epubId || initialLoadDone) return;

    // Try to restore from saved progress, otherwise load first chapter
    const navIdToLoad =
      savedProgress?.current_nav_id && savedProgress.current_nav_id !== 'start'
        ? savedProgress.current_nav_id
        : chapterOptions.length > 0
          ? chapterOptions[0].id
          : null;

    if (navIdToLoad) {
      // Enable scroll restoration only if we have a saved position for this nav_id
      if (
        savedProgress?.current_nav_id === navIdToLoad &&
        savedProgress?.scroll_position > 0
      ) {
        shouldRestoreScrollRef.current = true;
      }
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

  // Track whether we should restore scroll (only on initial load)
  const shouldRestoreScrollRef = useRef(false);

  // Restore scroll position after content loads (only on initial load)
  useEffect(() => {
    if (
      currentContent &&
      savedProgress &&
      contentContainerRef.current &&
      shouldRestoreScrollRef.current
    ) {
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
      // Only restore once
      shouldRestoreScrollRef.current = false;
    }
  }, [currentContent, savedProgress]);

  // Track pending highlight to scroll to after navigation
  const pendingHighlightRef = useRef<EPUBHighlight | null>(null);

  // Handle targetHighlight prop - navigate to and scroll to the highlight
  useEffect(() => {
    if (!targetHighlight || !epubId) return;

    const navigateToHighlight = async () => {
      const targetNavId = targetHighlight.nav_id;

      // If we're already on the correct nav_id, just scroll to the highlight
      if (currentNavId === targetNavId) {
        scrollToHighlightElement(targetHighlight);
      } else {
        // Store the highlight to scroll to after content loads
        pendingHighlightRef.current = targetHighlight;
        // Navigate to the section containing the highlight
        await loadContent(targetNavId);
      }
    };

    navigateToHighlight();
  }, [targetHighlight, epubId]);

  // Scroll to pending highlight after content loads
  useEffect(() => {
    if (
      pendingHighlightRef.current &&
      currentContent &&
      currentContent.nav_id === pendingHighlightRef.current.nav_id
    ) {
      // Wait for highlights to be applied to the DOM
      setTimeout(() => {
        if (pendingHighlightRef.current) {
          scrollToHighlightElement(pendingHighlightRef.current);
          pendingHighlightRef.current = null;
        }
      }, 150); // Wait for applyHighlightsToContent to complete
    }
  }, [currentContent, sectionHighlights]);

  // Scroll to a highlight element in the content
  const scrollToHighlightElement = (highlight: EPUBHighlight) => {
    if (!contentContainerRef.current) return;

    // Find the highlight span by data-highlight-id
    const highlightElement = contentContainerRef.current.querySelector(
      `[data-highlight-id="${highlight.id}"]`
    );

    if (highlightElement) {
      // Scroll the highlight into view with some padding at the top
      highlightElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Add a brief flash effect to draw attention
      highlightElement.classList.add('epub-highlight-flash');
      setTimeout(() => {
        highlightElement.classList.remove('epub-highlight-flash');
      }, 2000);
    } else {
      console.warn('Could not find highlight element:', highlight.id);
    }
  };

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
    if (!epubId) return;

    try {
      setCurrentNavId(navId);
      const contentData = await epubService.getContent(epubId, navId);
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

  const applyHighlightsToContent = () => {
    console.log(
      '🎨 Applying highlights to content, count:',
      sectionHighlights.length
    );

    // Clear existing highlights first
    clearAllHighlights();

    // Apply each highlight
    sectionHighlights.forEach((highlight, index) => {
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
        setSelectedText(selection.text);
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

    if (!pendingSelection) {
      console.log('❌ Missing pending selection');
      return;
    }

    // Use context's createHighlight - it handles API call and state update
    const newHighlight = await createContextHighlight({
      nav_id: pendingSelection.navId,
      chapter_id: pendingSelection.chapterId,
      start_xpath: pendingSelection.startXPath,
      start_offset: pendingSelection.startOffset,
      end_xpath: pendingSelection.endXPath,
      end_offset: pendingSelection.endOffset,
      highlight_text: pendingSelection.text,
      color,
    });

    if (newHighlight) {
      console.log('✅ Highlight created via context:', newHighlight);
    } else {
      console.error('❌ Failed to create highlight');
    }

    // Clear selection
    window.getSelection()?.removeAllRanges();
    setPendingSelection(null);
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

  // TTS service setup
  useEffect(() => {
    ttsService.setHandlers({
      onStateChange: state => {
        setIsTTSPlaying(state === 'playing');
        if (state === 'idle') {
          // Cleanup any remaining highlights
          if (ttsCleanupRef.current) {
            ttsCleanupRef.current();
            ttsCleanupRef.current = null;
          }
          if (htmlRef.current) {
            clearTTSHighlights(htmlRef.current);
          }
          // Clear the position map when TTS stops
          textPositionMapRef.current = null;
        }
      },
      onSentenceStart: (_index, _text, startOffset, endOffset) => {
        // Remove previous highlight
        if (ttsCleanupRef.current) {
          ttsCleanupRef.current();
        }

        // Add new highlight using offsets
        // Backend offsets are relative to the text sent, so add base offset
        // to get absolute positions in the full document
        if (textPositionMapRef.current) {
          const absoluteStart = ttsBaseOffsetRef.current + startOffset;
          const absoluteEnd = ttsBaseOffsetRef.current + endOffset;
          ttsCleanupRef.current = highlightByOffset(
            textPositionMapRef.current,
            absoluteStart,
            absoluteEnd
          );
        }
      },
      onSentenceEnd: () => {
        // Highlight will be replaced by next sentence_start
      },
      onDone: () => {
        setIsTTSPlaying(false);
        if (ttsCleanupRef.current) {
          ttsCleanupRef.current();
          ttsCleanupRef.current = null;
        }
        textPositionMapRef.current = null;
      },
      onError: msg => {
        console.error('TTS Error:', msg);
        setIsTTSPlaying(false);
        textPositionMapRef.current = null;
      },
    });

    return () => {
      ttsService.stop();
      textPositionMapRef.current = null;
    };
  }, []);

  // TTS handlers
  const handleReadAloud = useCallback((text: string) => {
    if (!htmlRef.current) return;

    // Build position map BEFORE starting TTS so we can map offsets to DOM
    textPositionMapRef.current = buildTextPositionMap(htmlRef.current);

    // Find where the selected text starts in the full document
    // This is needed because backend offsets are relative to the text sent
    const fullText = textPositionMapRef.current.fullText;
    const baseOffset = fullText.indexOf(text);
    ttsBaseOffsetRef.current = baseOffset >= 0 ? baseOffset : 0;

    ttsService.start(text);
  }, []);

  // Helper function to calculate precise character offset from selection
  const getSelectionCharacterOffset = useCallback((): number | null => {
    if (!htmlRef.current) return null;

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      return null;
    }

    const range = selection.getRangeAt(0);
    const container = htmlRef.current;

    // Ensure selection is within the EPUB container
    if (!container.contains(range.startContainer)) {
      return null;
    }

    // Walk through all text nodes to calculate cumulative offset
    let currentOffset = 0;
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT,
      null
    );

    let node: Text | null;
    while ((node = walker.nextNode() as Text)) {
      if (node === range.startContainer) {
        // Found our start node, add the start offset within this text node
        return currentOffset + range.startOffset;
      }
      // Add the full length of this text node to our running total
      currentOffset += node.textContent?.length || 0;
    }

    return null;
  }, []);

  const handleContinueReading = useCallback(() => {
    if (!htmlRef.current) return;

    // Build position map BEFORE starting TTS so we can map offsets to DOM
    textPositionMapRef.current = buildTextPositionMap(htmlRef.current);

    const fullText = textPositionMapRef.current.fullText;

    // Calculate precise character offset using the current selection
    const startOffset = getSelectionCharacterOffset();

    if (startOffset === null) {
      // Fallback: if we can't determine offset, try using pending selection
      if (pendingSelection) {
        // For fallback, find where the pending selection starts
        const baseOffset = fullText.indexOf(pendingSelection.text);
        ttsBaseOffsetRef.current = baseOffset >= 0 ? baseOffset : 0;
        ttsService.start(pendingSelection.text);
      }
      return;
    }

    // Set base offset to where the sliced text starts
    ttsBaseOffsetRef.current = startOffset;

    // Get text from the precise selection point to the end of the chapter
    const textFromSelection = fullText.slice(startOffset);

    // Start TTS with the remaining text
    ttsService.start(textFromSelection);
  }, [getSelectionCharacterOffset, pendingSelection]);

  const handleStopTTS = useCallback(() => {
    ttsService.stop();
  }, []);

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
              {Math.round(scrollProgressRatio * 100)}% through section
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
            {/* Tracking Toggle Button */}
            <button
              onClick={() => setTrackingEnabled(!trackingEnabled)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-sm ${
                trackingEnabled
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-gray-600 hover:bg-gray-500 text-gray-300'
              }`}
              title={
                trackingEnabled
                  ? 'Tracking reading progress'
                  : 'Not tracking (browsing mode)'
              }
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                {trackingEnabled ? (
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                ) : (
                  <circle
                    cx="12"
                    cy="12"
                    r="8"
                    strokeWidth="2"
                    stroke="currentColor"
                    fill="none"
                  />
                )}
              </svg>
              {trackingEnabled ? 'Tracking' : 'Paused'}
            </button>
            {/* TTS Stop Button */}
            {isTTSPlaying && (
              <button
                onClick={handleStopTTS}
                className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors text-sm"
                title="Stop Reading"
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <rect x="6" y="6" width="12" height="12" rx="1" />
                </svg>
                Stop
              </button>
            )}
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
            onReadAloud={handleReadAloud}
            onContinueReading={handleContinueReading}
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
              {currentContent.total_sections} (
              {Math.round(scrollProgressRatio * 100)}% through)
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
