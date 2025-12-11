import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize from 'rehype-sanitize';
import { defaultSchema } from 'hast-util-sanitize';
import 'highlight.js/styles/github.css';
import 'katex/dist/katex.min.css';
import '../styles/katex-dark.css';
import type { Components } from 'react-markdown';
import { getActiveLLMConfiguration } from '../api/llmConfig';
import type { LLMConfiguration } from '../types/llm';
import LLMSelectionModal from './LLMSelectionModal';
import { dualChatService } from '../services/dualChatService';
import { notesService } from '../services/api';
import { ThinkingBlock } from './ThinkBlock';

// Normalize LaTeX math delimiters (same as ChatInterface)
function normalizeMathDelimiters(markdown: string): string {
  if (!markdown) return markdown;

  const fencedSplit = markdown.split(/(```[\s\S]*?```)/g);

  const processOutsideCode = (segment: string): string => {
    const inlineSplit = segment.split(/(`[^`]*`)/g);
    return inlineSplit
      .map((part, idx) => {
        if (idx % 2 === 1 && part.startsWith('`')) return part;

        let replaced = part.replace(
          /\\\[([\s\S]*?)\\\]/g,
          (_m, inner) => `$$${inner}$$`
        );
        replaced = replaced.replace(
          /\\\(((?:.|\n)*?)\\\)/g,
          (_m, inner) => `$${inner}$`
        );
        return replaced;
      })
      .join('');
  };

  return fencedSplit
    .map((chunk, idx) => {
      if (idx % 2 === 1 && chunk.startsWith('```')) return chunk;
      return processOutsideCode(chunk);
    })
    .join('');
}

interface DualMessage {
  id: string;
  isUser: boolean;
  timestamp: Date;

  // NEW: Separate thinking and response content
  thinkingContent: string;
  responseContent: string;
  isThinkingComplete: boolean;
  isResponseComplete: boolean;
  hasThinking: boolean;

  // DEPRECATED: Keep for backward compatibility with user messages
  text?: string;
}

interface DualChatInterfaceProps {
  filename?: string;
  currentPage?: number;
}

export default function DualChatInterface({
  filename,
  currentPage,
}: DualChatInterfaceProps) {
  // LLM state
  const [primaryLLM, setPrimaryLLM] = useState<LLMConfiguration | null>(null);
  const [secondaryLLM, setSecondaryLLM] = useState<LLMConfiguration | null>(
    null
  );
  const [showLLMModal, setShowLLMModal] = useState(false);
  const [llmLoading, setLlmLoading] = useState(false);

  // Message state
  const [llm1Messages, setLlm1Messages] = useState<DualMessage[]>([]);
  const [llm2Messages, setLlm2Messages] = useState<DualMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [abortController, setAbortController] =
    useState<AbortController | null>(null);
  const [currentRequestId, setCurrentRequestId] = useState<string | null>(null);

  // Save note dialog state
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [saving, setSaving] = useState(false);

  // Refs for auto-scroll
  const llm1ContainerRef = useRef<HTMLDivElement>(null);
  const llm2ContainerRef = useRef<HTMLDivElement>(null);

  // Fetch active LLM configuration on mount
  useEffect(() => {
    const fetchActiveLLM = async () => {
      setLlmLoading(true);
      try {
        const config = await getActiveLLMConfiguration();
        setPrimaryLLM(config);
      } catch (error) {
        console.error('Failed to fetch active LLM configuration:', error);
        setPrimaryLLM(null);
      } finally {
        setLlmLoading(false);
      }
    };

    fetchActiveLLM();

    // Listen for LLM config changes
    const handleLLMConfigChange = () => {
      fetchActiveLLM();
    };

    window.addEventListener('llm-config-changed', handleLLMConfigChange);

    return () => {
      window.removeEventListener('llm-config-changed', handleLLMConfigChange);
    };
  }, []);

  const scrollToBottom = (container: HTMLDivElement | null) => {
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom(llm1ContainerRef.current);
  }, [llm1Messages]);

  useEffect(() => {
    scrollToBottom(llm2ContainerRef.current);
  }, [llm2Messages]);

  const clearChat = () => {
    setLlm1Messages([]);
    setLlm2Messages([]);
  };

  const saveChatAsNotes = async () => {
    if (!filename || !currentPage || !primaryLLM || !secondaryLLM) return;
    if (llm1Messages.length === 0 && llm2Messages.length === 0) return;

    setSaving(true);
    try {
      // CRITICAL: Convert LLM1 messages, omit thinking content
      const llm1Content = llm1Messages
        .map(msg => {
          if (msg.isUser) {
            return `**You**: ${msg.text}`;
          } else {
            // Only save the response content, omit thinking
            return `**AI**: ${msg.responseContent}`;
          }
        })
        .join('\n\n');

      // CRITICAL: Convert LLM2 messages, omit thinking content
      const llm2Content = llm2Messages
        .map(msg => {
          if (msg.isUser) {
            return `**You**: ${msg.text}`;
          } else {
            // Only save the response content, omit thinking
            return `**AI**: ${msg.responseContent}`;
          }
        })
        .join('\n\n');

      const baseTitle =
        noteTitle.trim() ||
        `Dual Chat on page ${currentPage} - ${new Date().toLocaleDateString()}`;

      // Save both conversations as separate notes
      const llm1Title = `${baseTitle} - ${primaryLLM.name}`;
      const llm2Title = `${baseTitle} - ${secondaryLLM.name}`;

      await Promise.all([
        notesService.saveChatNote(
          filename,
          currentPage,
          llm1Title,
          llm1Content
        ),
        notesService.saveChatNote(
          filename,
          currentPage,
          llm2Title,
          llm2Content
        ),
      ]);

      setShowSaveDialog(false);
      setNoteTitle('');

      console.log('Both chat conversations saved as notes (thinking omitted)!');
    } catch (error) {
      console.error('Error saving dual chat notes:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleSelectSecondaryLLM = (llm: LLMConfiguration) => {
    setSecondaryLLM(llm);
    setShowLLMModal(false);
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !filename || !secondaryLLM) return;

    // Detect if this is a new chat BEFORE adding messages
    const isNewChat = llm1Messages.length === 0 && llm2Messages.length === 0;

    const userMessage: DualMessage = {
      id: Date.now().toString(),
      text: inputText, // User messages still use text field
      isUser: true,
      timestamp: new Date(),
      thinkingContent: '',
      responseContent: '',
      isThinkingComplete: false,
      isResponseComplete: true, // User messages are always complete
      hasThinking: false,
    };

    // Add user message to both conversations
    setLlm1Messages(prev => [...prev, userMessage]);
    setLlm2Messages(prev => [...prev, userMessage]);

    const currentInput = inputText;
    setInputText('');
    setLoading(true);
    setStreaming(true);

    // Create placeholder AI messages for both LLMs
    const aiMessage1Id = (Date.now() + 1).toString();
    const aiMessage2Id = (Date.now() + 2).toString();

    const aiMessage1: DualMessage = {
      id: aiMessage1Id,
      thinkingContent: '',
      responseContent: '',
      isThinkingComplete: false,
      isResponseComplete: false,
      hasThinking: false,
      isUser: false,
      timestamp: new Date(),
    };

    const aiMessage2: DualMessage = {
      id: aiMessage2Id,
      thinkingContent: '',
      responseContent: '',
      isThinkingComplete: false,
      isResponseComplete: false,
      hasThinking: false,
      isUser: false,
      timestamp: new Date(),
    };

    setLlm1Messages(prev => [...prev, aiMessage1]);
    setLlm2Messages(prev => [...prev, aiMessage2]);

    // Create abort controller for this request
    const controller = new AbortController();
    setAbortController(controller);

    try {
      // Convert messages to chat history format
      // CRITICAL: Only send response content, NOT thinking content
      const llm1History = llm1Messages.map(msg => ({
        role: msg.isUser ? 'user' : 'assistant',
        content: msg.isUser ? msg.text || '' : msg.responseContent,
      }));

      const llm2History = llm2Messages.map(msg => ({
        role: msg.isUser ? 'user' : 'assistant',
        content: msg.isUser ? msg.text || '' : msg.responseContent,
      }));

      // Stream from backend with structured thinking/response separation
      let requestId: string | null = null;

      for await (const data of dualChatService.streamDualChat(
        currentInput,
        filename,
        currentPage!,
        llm1History,
        llm2History,
        primaryLLM.id,
        secondaryLLM.id,
        controller.signal,
        isNewChat
      )) {
        // Handle request_id
        if (data.request_id) {
          requestId = data.request_id;
          setCurrentRequestId(requestId);
          continue;
        }

        // Handle LLM 1 structured data
        if (data.llm1) {
          if (data.llm1.error) {
            setLlm1Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage1Id
                  ? { ...msg, responseContent: `Error: ${data.llm1!.error}` }
                  : msg
              )
            );
          } else if (data.llm1.type === 'thinking') {
            setLlm1Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage1Id
                  ? {
                      ...msg,
                      thinkingContent:
                        msg.thinkingContent + (data.llm1!.content || ''),
                      hasThinking: true,
                    }
                  : msg
              )
            );
          } else if (data.llm1.type === 'response') {
            setLlm1Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage1Id
                  ? {
                      ...msg,
                      responseContent:
                        msg.responseContent + (data.llm1!.content || ''),
                    }
                  : msg
              )
            );
          } else if (data.llm1.type === 'metadata') {
            if (data.llm1.metadata?.thinking_complete !== undefined) {
              setLlm1Messages(prev =>
                prev.map(msg =>
                  msg.id === aiMessage1Id
                    ? {
                        ...msg,
                        isThinkingComplete:
                          data.llm1!.metadata?.thinking_complete ?? false,
                      }
                    : msg
                )
              );
            }
          }
        }

        // Handle LLM 2 structured data
        if (data.llm2) {
          if (data.llm2.error) {
            setLlm2Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage2Id
                  ? { ...msg, responseContent: `Error: ${data.llm2!.error}` }
                  : msg
              )
            );
          } else if (data.llm2.type === 'thinking') {
            setLlm2Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage2Id
                  ? {
                      ...msg,
                      thinkingContent:
                        msg.thinkingContent + (data.llm2!.content || ''),
                      hasThinking: true,
                    }
                  : msg
              )
            );
          } else if (data.llm2.type === 'response') {
            setLlm2Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage2Id
                  ? {
                      ...msg,
                      responseContent:
                        msg.responseContent + (data.llm2!.content || ''),
                    }
                  : msg
              )
            );
          } else if (data.llm2.type === 'metadata') {
            if (data.llm2.metadata?.thinking_complete !== undefined) {
              setLlm2Messages(prev =>
                prev.map(msg =>
                  msg.id === aiMessage2Id
                    ? {
                        ...msg,
                        isThinkingComplete:
                          data.llm2!.metadata?.thinking_complete ?? false,
                      }
                    : msg
                )
              );
            }
          }
        }

        // Handle completion
        if (data.done) {
          // Mark both messages as complete
          setLlm1Messages(prev =>
            prev.map(msg =>
              msg.id === aiMessage1Id
                ? { ...msg, isResponseComplete: true }
                : msg
            )
          );
          setLlm2Messages(prev =>
            prev.map(msg =>
              msg.id === aiMessage2Id
                ? { ...msg, isResponseComplete: true }
                : msg
            )
          );
          break;
        }
      }
    } catch (error) {
      console.error('Dual chat failed:', error);

      // Check if the error is due to abort
      if (error instanceof Error && error.name === 'AbortError') {
        const abortText = 'Message generation stopped by user.';
        setLlm1Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage1Id
              ? { ...msg, responseContent: abortText, isResponseComplete: true }
              : msg
          )
        );
        setLlm2Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage2Id
              ? { ...msg, responseContent: abortText, isResponseComplete: true }
              : msg
          )
        );
      } else {
        const errorText = `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`;
        setLlm1Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage1Id
              ? { ...msg, responseContent: errorText, isResponseComplete: true }
              : msg
          )
        );
        setLlm2Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage2Id
              ? { ...msg, responseContent: errorText, isResponseComplete: true }
              : msg
          )
        );
      }
    } finally {
      setLoading(false);
      setStreaming(false);
      setAbortController(null);
      setCurrentRequestId(null);
    }
  };

  const markdownComponents = {
    code: ({ className, children, ...props }) => {
      return (
        <code
          className={`${className || ''} bg-gray-600 text-gray-100 px-1 py-0.5 rounded text-xs font-mono`}
          {...props}
        >
          {children}
        </code>
      );
    },
    span: ({ className, children, ...props }) => {
      if (className?.includes('katex')) {
        return (
          <span className={`${className} text-gray-200`} {...props}>
            {children}
          </span>
        );
      }
      return (
        <span className={`${className || ''} text-gray-200`} {...props}>
          {children}
        </span>
      );
    },
    pre: ({ children }) => (
      <pre className="bg-gray-600 text-gray-100 p-2 rounded-md overflow-x-auto text-xs border border-gray-500">
        {children}
      </pre>
    ),
    h1: ({ children }) => (
      <h1 className="text-base font-bold text-gray-100 mt-3 mb-2 first:mt-0">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-sm font-bold text-gray-100 mt-2 mb-1 first:mt-0">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-xs font-bold text-gray-100 mt-2 mb-1 first:mt-0">
        {children}
      </h3>
    ),
    p: ({ children }) => (
      <p className="text-sm text-gray-200 leading-relaxed mb-1">{children}</p>
    ),
    strong: ({ children }) => (
      <strong className="text-gray-100 font-semibold">{children}</strong>
    ),
    em: ({ children }) => <em className="text-gray-200 italic">{children}</em>,
    ul: ({ children }) => (
      <ul className="text-sm text-gray-200 mb-1 pl-3 space-y-0.5 list-disc list-inside">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="text-sm text-gray-200 mb-1 pl-3 space-y-0.5 list-decimal list-inside">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="text-gray-200">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-blue-400 pl-2 py-0.5 bg-blue-900/20 text-sm text-gray-200 italic">
        {children}
      </blockquote>
    ),
    a: ({ href, children }) => (
      <a
        href={href}
        className="text-blue-300 hover:text-blue-200 underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {children}
      </a>
    ),
  } as Components;

  // Render individual message pane
  const renderMessagePane = (
    messages: DualMessage[],
    llmName: string,
    llmModel: string,
    containerRef: React.RefObject<HTMLDivElement>,
    borderColor: string
  ) => (
    <div className="flex flex-col h-full">
      {/* Pane Header */}
      <div
        className={`px-3 py-2 bg-gray-800 border-b border-gray-700 border-l-4 ${borderColor}`}
      >
        <div className="text-xs font-medium text-gray-200">{llmName}</div>
        <div className="text-xs text-gray-400">{llmModel}</div>
      </div>

      {/* Messages */}
      <div ref={containerRef} className="flex-1 overflow-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-gray-400 text-sm text-center mt-8">
            Ready to chat
          </div>
        ) : (
          messages.map(message => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`px-3 py-2 rounded-lg text-sm ${
                  message.isUser
                    ? 'bg-blue-600 text-white max-w-xs'
                    : 'bg-gray-700 text-gray-200 w-full'
                }`}
              >
                {message.isUser ? (
                  message.text
                ) : (
                  <div className="max-w-none text-gray-200">
                    {/* Show thinking content if present */}
                    {message.hasThinking && (
                      <ThinkingBlock
                        content={message.thinkingContent}
                        isStreaming={streaming && !message.isThinkingComplete}
                        isComplete={message.isThinkingComplete}
                      />
                    )}
                    {/* Show response content */}
                    {message.responseContent ? (
                      !message.isResponseComplete ? (
                        // Show plain text while this message is streaming
                        <div className="whitespace-pre-wrap">
                          {message.responseContent}
                        </div>
                      ) : (
                        // Parse markdown when this message is complete
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[
                            rehypeRaw,
                            [rehypeSanitize, defaultSchema],
                            rehypeHighlight,
                            rehypeKatex,
                          ]}
                          skipHtml={false}
                          components={markdownComponents}
                        >
                          {normalizeMathDelimiters(message.responseContent)}
                        </ReactMarkdown>
                      )
                    ) : (
                      // Fallback to old text field for backward compatibility
                      message.text && (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm, remarkMath]}
                          rehypePlugins={[
                            rehypeRaw,
                            [rehypeSanitize, defaultSchema],
                            rehypeHighlight,
                            rehypeKatex,
                          ]}
                          skipHtml={false}
                          components={markdownComponents}
                        >
                          {normalizeMathDelimiters(message.text)}
                        </ReactMarkdown>
                      )
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );

  // Show empty state if no secondary LLM selected
  if (!secondaryLLM) {
    return (
      <div className="h-full flex flex-col bg-gray-900">
        {/* Header */}
        <div className="border-b border-gray-700 px-4 py-2 bg-gray-800">
          <h3 className="text-sm font-medium text-gray-200">
            Dual LLM Chat{' '}
            {filename ? `- ${filename} (Page ${currentPage})` : ''}
          </h3>
        </div>

        {/* Empty State */}
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center max-w-md">
            <div className="text-6xl mb-4">🤖 🤖</div>
            <h3 className="text-xl font-medium text-gray-200 mb-2">
              Dual LLM Chat
            </h3>
            <p className="text-gray-400 mb-6">
              Compare responses from two different AI models side-by-side.
              Perfect for understanding different perspectives on complex
              topics.
            </p>
            <div className="mb-4 p-4 bg-gray-800 rounded-lg border border-gray-700">
              <div className="text-sm text-gray-300 mb-2">
                <strong>Primary LLM:</strong>
              </div>
              {llmLoading ? (
                <div className="text-sm text-gray-400 animate-pulse">
                  Loading...
                </div>
              ) : primaryLLM ? (
                <div className="text-sm">
                  <div className="text-gray-200 font-medium">
                    {primaryLLM.name}
                  </div>
                  <div className="text-gray-400">{primaryLLM.model_name}</div>
                </div>
              ) : (
                <div className="text-sm text-yellow-500">
                  No active LLM configured
                </div>
              )}
            </div>
            <button
              onClick={() => setShowLLMModal(true)}
              disabled={!primaryLLM || !filename}
              className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:bg-gray-600 disabled:cursor-not-allowed"
            >
              Select Second LLM
            </button>
            {!filename && (
              <p className="text-xs text-gray-500 mt-2">
                Open a PDF to start chatting
              </p>
            )}
          </div>
        </div>

        {/* LLM Selection Modal */}
        {showLLMModal && primaryLLM && (
          <LLMSelectionModal
            isOpen={showLLMModal}
            onClose={() => setShowLLMModal(false)}
            onSelect={handleSelectSecondaryLLM}
            excludeLLMId={primaryLLM.id}
            title="Select Second LLM"
          />
        )}
      </div>
    );
  }

  // Main dual chat interface
  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-700 px-4 py-2 bg-gray-800">
        <div className="flex justify-between items-center">
          <div className="flex flex-col gap-1 flex-1">
            <h3 className="text-sm font-medium text-gray-200">
              Dual Chat {filename ? `- ${filename} (Page ${currentPage})` : ''}
            </h3>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                <span className="text-gray-400">{primaryLLM.name}</span>
              </div>
              <span className="text-gray-600">vs</span>
              <div className="flex items-center gap-1">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-purple-500"></span>
                <span className="text-gray-400">{secondaryLLM.name}</span>
              </div>
              <button
                onClick={() => setShowLLMModal(true)}
                className="ml-2 text-blue-400 hover:text-blue-300 underline"
              >
                Change
              </button>
            </div>
          </div>
          {llm1Messages.length > 0 && (
            <div className="flex gap-2">
              <button
                onClick={() => setShowSaveDialog(true)}
                disabled={!filename}
                className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors disabled:bg-gray-600 disabled:cursor-not-allowed"
                title="Save both conversations as notes"
              >
                Save Notes
              </button>
              <button
                onClick={clearChat}
                className="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded hover:bg-gray-500 transition-colors"
                title="Clear chat"
              >
                Clear Chat
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Split Pane View */}
      <div className="flex-1 flex overflow-hidden">
        {/* LLM 1 Pane */}
        <div className="flex-1 flex flex-col border-r border-gray-700">
          {renderMessagePane(
            llm1Messages,
            primaryLLM.name,
            primaryLLM.model_name,
            llm1ContainerRef,
            'border-blue-500'
          )}
        </div>

        {/* LLM 2 Pane */}
        <div className="flex-1 flex flex-col">
          {renderMessagePane(
            llm2Messages,
            secondaryLLM.name,
            secondaryLLM.model_name,
            llm2ContainerRef,
            'border-purple-500'
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2 items-end">
          <textarea
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                if (!streaming && inputText.trim() && filename && !loading) {
                  sendMessage();
                }
              }
            }}
            placeholder={
              filename
                ? `Ask about this PDF... (${navigator.platform.includes('Mac') ? 'Cmd' : 'Ctrl'}+Enter to send)`
                : 'Open a PDF to chat'
            }
            disabled={!filename || loading}
            rows={3}
            className="flex-1 px-3 py-2 border border-gray-600 bg-gray-800 text-gray-200 placeholder-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-700 disabled:text-gray-500 resize-y min-h-[76px]"
          />
          <button
            onClick={sendMessage}
            disabled={!inputText.trim() || !filename || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>

      {/* LLM Selection Modal */}
      {showLLMModal && primaryLLM && (
        <LLMSelectionModal
          isOpen={showLLMModal}
          onClose={() => setShowLLMModal(false)}
          onSelect={handleSelectSecondaryLLM}
          excludeLLMId={primaryLLM.id}
          title="Select Second LLM"
        />
      )}

      {/* Save Note Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 w-[500px] max-w-90vw">
            <h3 className="text-lg font-medium text-gray-200 mb-4">
              Save Dual Chat as Notes
            </h3>

            <div className="mb-4">
              <label className="block text-sm text-gray-300 mb-2">
                Base Note Title (Optional)
              </label>
              <input
                type="text"
                value={noteTitle}
                onChange={e => setNoteTitle(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !saving) {
                    e.preventDefault();
                    saveChatAsNotes();
                  }
                }}
                placeholder={`Dual Chat on page ${currentPage} - ${new Date().toLocaleDateString()}`}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 placeholder-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="mb-4 p-4 bg-gray-900 rounded-lg border border-gray-700 space-y-3">
              <div className="text-sm text-gray-300 mb-2">
                This will create <strong>TWO</strong> separate notes:
              </div>

              <div className="flex items-start gap-2">
                <div className="text-blue-400 mt-0.5">📝</div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-200">
                    Note 1: Conversation with{' '}
                    {primaryLLM?.name || 'Primary LLM'}
                  </div>
                  <div className="text-xs text-gray-400">
                    • {llm1Messages.length} messages
                    {currentPage && ` • Linked to page ${currentPage}`}
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-2">
                <div className="text-purple-400 mt-0.5">📝</div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-200">
                    Note 2: Conversation with{' '}
                    {secondaryLLM?.name || 'Secondary LLM'}
                  </div>
                  <div className="text-xs text-gray-400">
                    • {llm2Messages.length} messages
                    {currentPage && ` • Linked to page ${currentPage}`}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => {
                  setShowSaveDialog(false);
                  setNoteTitle('');
                }}
                disabled={saving}
                className="px-4 py-2 text-gray-300 border border-gray-600 rounded-md hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={saveChatAsNotes}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save Both Notes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
