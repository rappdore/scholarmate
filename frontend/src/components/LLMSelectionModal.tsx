import { useState, useEffect } from 'react';
import { listLLMConfigurations } from '../api/llmConfig';
import type { LLMConfiguration } from '../types/llm';

interface LLMSelectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (llm: LLMConfiguration) => void;
  excludeLLMId?: number;
  title?: string;
}

export default function LLMSelectionModal({
  isOpen,
  onClose,
  onSelect,
  excludeLLMId,
  title = 'Select LLM',
}: LLMSelectionModalProps) {
  const [llms, setLlms] = useState<LLMConfiguration[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isOpen) {
      fetchLLMs();
    }
  }, [isOpen]);

  const fetchLLMs = async () => {
    setLoading(true);
    setError(null);
    try {
      const configs = await listLLMConfigurations();
      setLlms(configs);
    } catch (err) {
      setError('Failed to load LLM configurations');
      console.error('Failed to fetch LLMs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (llm: LLMConfiguration) => {
    onSelect(llm);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (!isOpen) return null;

  // Filter out excluded LLM and apply search
  const filteredLLMs = llms
    .filter(llm => llm.id !== excludeLLMId)
    .filter(
      llm =>
        llm.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        llm.model_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        llm.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-medium text-gray-200">{title}</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 transition-colors"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Search */}
        <div className="px-6 py-3 border-b border-gray-700">
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search LLMs..."
            className="w-full px-3 py-2 bg-gray-700 text-gray-200 placeholder-gray-400 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-gray-400 animate-pulse">
                Loading LLM configurations...
              </div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="text-red-400 mb-4">{error}</div>
              <button
                onClick={fetchLLMs}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors"
              >
                Retry
              </button>
            </div>
          ) : filteredLLMs.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-gray-400 mb-2">
                {searchQuery
                  ? 'No LLMs match your search'
                  : 'No other LLMs available'}
              </div>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="text-blue-400 hover:text-blue-300 underline text-sm"
                >
                  Clear search
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {filteredLLMs.map(llm => (
                <button
                  key={llm.id}
                  onClick={() => handleSelect(llm)}
                  className="text-left p-4 bg-gray-700 hover:bg-gray-600 border border-gray-600 hover:border-blue-500 rounded-lg transition-all group"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-base font-medium text-gray-200 group-hover:text-white">
                          {llm.name}
                        </h3>
                        {llm.is_active && (
                          <span className="px-2 py-0.5 bg-green-900/30 text-green-400 text-xs rounded-full border border-green-700">
                            Active
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-gray-400 mb-2">
                        {llm.model_name}
                      </div>
                      {llm.description && (
                        <div className="text-sm text-gray-500">
                          {llm.description}
                        </div>
                      )}
                      <div className="text-xs text-gray-500 mt-2">
                        {llm.base_url}
                      </div>
                    </div>
                    <div className="ml-4">
                      <svg
                        className="w-5 h-5 text-gray-500 group-hover:text-blue-400 transition-colors"
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
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-700 bg-gray-800/50">
          <div className="text-xs text-gray-500">
            {filteredLLMs.length > 0 ? (
              <>
                Showing {filteredLLMs.length}{' '}
                {filteredLLMs.length === 1 ? 'LLM' : 'LLMs'}
              </>
            ) : (
              'No LLMs to display'
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
