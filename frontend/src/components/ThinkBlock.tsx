import { useState } from 'react';

export interface ThinkingBlockProps {
  content: string;
  isStreaming?: boolean;
  isComplete?: boolean;
}

/**
 * ThinkingBlock component displays LLM thinking content in a collapsible block.
 * Used to show the reasoning process separately from the final response.
 */
export function ThinkingBlock({
  content,
  isStreaming = false,
  isComplete = false,
}: ThinkingBlockProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if there's no content
  if (!content) {
    return null;
  }

  return (
    <div className="mb-3 border border-gray-600 rounded-lg overflow-hidden bg-gray-800/50">
      {/* Header - clickable to expand/collapse */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between text-xs text-gray-400 hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-yellow-400">🧠</span>
          <span className="font-medium">
            {isStreaming ? 'Thinking...' : 'Thinking Process'}
          </span>
          {isComplete && !isStreaming && (
            <span className="text-green-400">✓</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-500">{content.length} chars</span>
          <svg
            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>

      {/* Content - shown when expanded */}
      {isExpanded && (
        <div className="px-3 py-2 border-t border-gray-600 bg-gray-800">
          <div className="text-xs text-gray-300 font-mono whitespace-pre-wrap">
            {content}
            {isStreaming && (
              <span className="inline-block ml-1 w-2 h-3 bg-yellow-400 animate-pulse" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
