import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'highlight.js/styles/github.css'; // You can change this to other themes
import 'katex/dist/katex.min.css'; // KaTeX CSS for math rendering
import '../styles/katex-dark.css'; // Custom dark theme for KaTeX
import type { Components } from 'react-markdown';
import { aiService } from '../services/api';
import { ThinkingBlock } from './ThinkBlock';

interface AIPanelProps {
  pdfId?: number;
  epubId?: number;
  filename?: string;
  documentType?: 'pdf' | 'epub';
  currentPage: number; // For PDF
  currentNavId?: string; // For EPUB
  scrollProgress?: number; // For EPUB: 0.0-1.0 position within current section
}

export default function AIPanel({
  pdfId,
  epubId,
  filename,
  documentType,
  currentPage,
  currentNavId,
  scrollProgress,
}: AIPanelProps) {
  // Structured content state (same pattern as ChatInterface)
  const [responseContent, setResponseContent] = useState<string>('');
  const [thinkingContent, setThinkingContent] = useState<string>('');
  const [hasThinking, setHasThinking] = useState(false);
  const [isThinkingComplete, setIsThinkingComplete] = useState(false);

  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [autoAnalyze, setAutoAnalyze] = useState(false);
  const [aiStatus, setAiStatus] = useState<'unknown' | 'connected' | 'error'>(
    'unknown'
  );

  // Track last analyzed scroll position for EPUB auto-analyze on scroll
  const lastAnalyzedScrollProgressRef = useRef<number>(0);

  // Threshold for triggering auto-analyze on scroll (~20% of section ≈ 2k chars in typical section)
  const SCROLL_THRESHOLD = 0.2;

  // Check AI connection on mount
  useEffect(() => {
    checkAIConnection();
  }, []);

  // Clear content and reset scroll tracking when page/section changes
  useEffect(() => {
    setResponseContent('');
    setThinkingContent('');
    setHasThinking(false);
    setIsThinkingComplete(false);
    // Reset scroll tracking when section changes
    lastAnalyzedScrollProgressRef.current = 0;
  }, [pdfId, epubId, currentPage, currentNavId, documentType]);

  // Auto-analyze for PDF (on page change) and EPUB (on section change)
  useEffect(() => {
    if (!autoAnalyze) return;

    // PDF: analyze on page change
    if (documentType === 'pdf' && pdfId && currentPage) {
      analyzeDocument();
      return;
    }

    // EPUB: analyze on section change (initial analysis for new section)
    if (documentType === 'epub' && epubId && currentNavId) {
      analyzeDocument();
      lastAnalyzedScrollProgressRef.current = scrollProgress ?? 0;
    }
  }, [pdfId, epubId, currentPage, currentNavId, autoAnalyze, documentType]);

  // EPUB-specific: Auto-analyze on significant scroll progress (forward only)
  useEffect(() => {
    // Only for EPUB with auto-analyze enabled
    if (!autoAnalyze || documentType !== 'epub' || !epubId || !currentNavId) {
      return;
    }

    // Don't trigger if analysis is already in progress
    if (loading || streaming) {
      return;
    }

    const currentProgress = scrollProgress ?? 0;
    const lastProgress = lastAnalyzedScrollProgressRef.current;
    const scrollDelta = currentProgress - lastProgress;

    // Only trigger on forward scroll that exceeds threshold
    if (scrollDelta >= SCROLL_THRESHOLD) {
      analyzeDocument();
      lastAnalyzedScrollProgressRef.current = currentProgress;
    }
  }, [
    scrollProgress,
    autoAnalyze,
    documentType,
    epubId,
    currentNavId,
    loading,
    streaming,
  ]);

  const checkAIConnection = async () => {
    try {
      await aiService.checkHealth();
      setAiStatus('connected');
    } catch (error) {
      console.error('AI connection failed:', error);
      setAiStatus('error');
    }
  };

  const analyzeDocument = async () => {
    if (!documentType) return;
    if (documentType === 'pdf' && (!pdfId || !currentPage)) return;
    if (documentType === 'epub' && (!epubId || !currentNavId)) return;

    setLoading(true);
    setStreaming(true);
    setResponseContent('');
    setThinkingContent('');
    setHasThinking(false);
    setIsThinkingComplete(false);

    try {
      let textExtracted = true;

      const analysisStream =
        documentType === 'epub' && currentNavId && epubId
          ? aiService.streamAnalyzeEpubSection(
              epubId,
              currentNavId,
              scrollProgress ?? 0
            )
          : aiService.streamAnalyzePage(pdfId!, currentPage);

      for await (const chunk of analysisStream) {
        if (chunk.error) {
          throw new Error(chunk.error);
        }

        // Handle structured streaming (same pattern as ChatInterface)
        if (chunk.type === 'thinking') {
          setThinkingContent(prev => prev + (chunk.content || ''));
          setHasThinking(true);
        } else if (chunk.type === 'response') {
          setResponseContent(prev => prev + (chunk.content || ''));
        } else if (chunk.type === 'metadata') {
          if (chunk.metadata?.thinking_complete) {
            setIsThinkingComplete(true);
          }
        }

        if (chunk.text_extracted !== undefined) {
          textExtracted = chunk.text_extracted;
        }

        if (chunk.done) {
          break;
        }
      }

      if (!textExtracted) {
        setResponseContent(
          prev =>
            prev +
            '\n\n💡 Tip: This content might contain images, diagrams, or special formatting that requires visual analysis.'
        );
      }
    } catch (error) {
      console.error('Analysis failed:', error);
      setResponseContent(
        'Failed to analyze content. Please check if the AI service is running and try again.'
      );
      setThinkingContent('');
      setHasThinking(false);
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  };

  const getStatusIndicator = () => {
    switch (aiStatus) {
      case 'connected':
        return <span className="text-green-400 text-sm">● AI Connected</span>;
      case 'error':
        return <span className="text-red-400 text-sm">● AI Offline</span>;
      default:
        return <span className="text-gray-400 text-sm">● Checking...</span>;
    }
  };

  const markdownComponents = {
    code: ({ className, children, ...props }) => {
      return (
        <code
          className={`${className || ''} bg-gray-700 text-gray-200 px-1 py-0.5 rounded text-xs font-mono`}
          {...props}
        >
          {children}
        </code>
      );
    },
    // Custom styling for math elements to work with dark theme
    span: ({ className, children, ...props }) => {
      if (className?.includes('katex')) {
        return (
          <span className={`${className} text-gray-200`} {...props}>
            {children}
          </span>
        );
      }
      return (
        <span className={`${className || ''} text-gray-300`} {...props}>
          {children}
        </span>
      );
    },
    pre: ({ children }) => (
      <pre className="bg-gray-700 text-gray-200 p-3 rounded-md overflow-x-auto text-xs border border-gray-600">
        {children}
      </pre>
    ),
    h1: ({ children }) => (
      <h1 className="text-lg font-bold text-gray-100 mt-4 mb-2 first:mt-0">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-base font-bold text-gray-100 mt-3 mb-2 first:mt-0">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-sm font-bold text-gray-100 mt-2 mb-1 first:mt-0">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-sm font-medium text-gray-200 mt-2 mb-1 first:mt-0">
        {children}
      </h4>
    ),
    h5: ({ children }) => (
      <h5 className="text-sm font-medium text-gray-200 mt-1 mb-1 first:mt-0">
        {children}
      </h5>
    ),
    h6: ({ children }) => (
      <h6 className="text-sm font-medium text-gray-300 mt-1 mb-1 first:mt-0">
        {children}
      </h6>
    ),
    p: ({ children }) => (
      <p className="text-sm text-gray-300 leading-relaxed mb-2">{children}</p>
    ),
    strong: ({ children }) => (
      <strong className="text-gray-200 font-semibold">{children}</strong>
    ),
    em: ({ children }) => <em className="text-gray-300 italic">{children}</em>,
    ul: ({ children }) => (
      <ul className="text-sm text-gray-300 mb-2 pl-4 space-y-1 list-disc list-inside">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="text-sm text-gray-300 mb-2 pl-4 space-y-1 list-decimal list-inside">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="text-gray-300">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-blue-500 pl-3 py-1 bg-blue-900/30 text-sm text-gray-300 italic">
        {children}
      </blockquote>
    ),
    a: ({ href, children }) => (
      <a
        href={href}
        className="text-blue-400 hover:text-blue-300 underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto mb-2">
        <table className="min-w-full text-sm text-gray-300 border border-gray-600">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-gray-700">{children}</thead>,
    tbody: ({ children }) => <tbody className="bg-gray-800">{children}</tbody>,
    tr: ({ children }) => (
      <tr className="border-b border-gray-600">{children}</tr>
    ),
    th: ({ children }) => (
      <th className="px-2 py-1 text-left text-gray-200 font-medium">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-2 py-1 text-gray-300">{children}</td>
    ),
  } as Components;

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-700 px-4 py-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-lg font-semibold text-gray-100">AI Analysis</h2>
          {getStatusIndicator()}
        </div>
        <div className="flex items-center justify-between">
          <label className="flex items-center text-sm text-gray-300">
            <input
              type="checkbox"
              checked={autoAnalyze}
              onChange={e => setAutoAnalyze(e.target.checked)}
              className="mr-2 bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500"
            />
            Auto-analyze pages
          </label>
          <button
            onClick={analyzeDocument}
            disabled={loading || streaming || !filename || aiStatus === 'error'}
            className="px-4 py-2 bg-green-600 text-white rounded disabled:bg-gray-600 disabled:cursor-not-allowed text-sm hover:bg-green-500 transition-colors"
          >
            {loading || streaming ? 'Analyzing...' : 'Analyze Content'}
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {!filename ? (
          <div className="text-gray-400 text-center mt-8">
            Open a document to get AI insights
          </div>
        ) : aiStatus === 'error' ? (
          <div className="text-center mt-8">
            <div className="text-red-400 mb-2">AI service is not available</div>
            <div className="text-sm text-gray-400 mb-4">
              Make sure Ollama is running with qwen3-30b model at
              localhost:11434
            </div>
            <button
              onClick={checkAIConnection}
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-500 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        ) : responseContent || hasThinking ? (
          <div className="space-y-4">
            {/* Streaming indicator */}
            {streaming && (
              <div className="flex items-center space-x-2 text-sm text-blue-400 bg-blue-900/30 p-2 rounded">
                <div className="flex space-x-1">
                  <div
                    className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
                    style={{ animationDelay: '0ms' }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
                    style={{ animationDelay: '150ms' }}
                  ></div>
                  <div
                    className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"
                    style={{ animationDelay: '300ms' }}
                  ></div>
                </div>
                <span>AI is analyzing...</span>
              </div>
            )}

            {/* Thinking Block - using same component as ChatInterface */}
            {hasThinking && (
              <ThinkingBlock
                content={thinkingContent}
                isStreaming={streaming && !isThinkingComplete}
                isComplete={isThinkingComplete}
              />
            )}

            {/* Main Analysis */}
            <div className="max-w-none text-gray-300">
              {streaming ? (
                // Show plain text while streaming for performance
                <div className="whitespace-pre-wrap text-sm leading-relaxed">
                  {responseContent}
                </div>
              ) : (
                // Parse markdown when streaming is complete
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeHighlight, rehypeKatex]}
                  components={markdownComponents}
                >
                  {responseContent}
                </ReactMarkdown>
              )}
            </div>
          </div>
        ) : (
          <div className="text-gray-400 text-center mt-8">
            {autoAnalyze
              ? 'Auto-analysis enabled. Change sections to see insights.'
              : 'Click "Analyze Content" to get AI insights about the current content.'}
          </div>
        )}
      </div>
    </div>
  );
}
