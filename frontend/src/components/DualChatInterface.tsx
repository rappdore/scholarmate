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
  text: string;
  isUser: boolean;
  timestamp: Date;
}

interface DualChatInterfaceProps {
  filename?: string;
  currentPage?: number;
}

export default function DualChatInterface({
  filename,
  currentPage,
}: DualChatInterfaceProps) {
  // Extend sanitize schema to allow custom <think> tag
  const sanitizeSchema = {
    ...defaultSchema,
    tagNames: [...(defaultSchema.tagNames || []), 'think'],
    attributes: {
      ...(defaultSchema.attributes || {}),
      think: ['className'],
    },
  };

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

  const handleSelectSecondaryLLM = (llm: LLMConfiguration) => {
    setSecondaryLLM(llm);
    setShowLLMModal(false);
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !filename || !secondaryLLM) return;

    const userMessage: DualMessage = {
      id: Date.now().toString(),
      text: inputText,
      isUser: true,
      timestamp: new Date(),
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
      text: '',
      isUser: false,
      timestamp: new Date(),
    };

    const aiMessage2: DualMessage = {
      id: aiMessage2Id,
      text: '',
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
      const llm1History = llm1Messages
        .filter(msg => !msg.isUser || msg.text !== currentInput)
        .map(msg => ({
          role: msg.isUser ? 'user' : 'assistant',
          content: msg.text,
        }));

      const llm2History = llm2Messages
        .filter(msg => !msg.isUser || msg.text !== currentInput)
        .map(msg => ({
          role: msg.isUser ? 'user' : 'assistant',
          content: msg.text,
        }));

      // Detect if this is a new chat
      const isNewChat = llm1Messages.length === 0 && llm2Messages.length === 0;

      // Stream from real backend
      let llm1FullResponse = '';
      let llm2FullResponse = '';
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

        // Handle LLM 1 content
        if (data.llm1) {
          if (data.llm1.content) {
            llm1FullResponse += data.llm1.content;
            setLlm1Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage1Id
                  ? { ...msg, text: llm1FullResponse }
                  : msg
              )
            );
          }
          if (data.llm1.error) {
            setLlm1Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage1Id
                  ? { ...msg, text: `Error: ${data.llm1!.error}` }
                  : msg
              )
            );
          }
        }

        // Handle LLM 2 content
        if (data.llm2) {
          if (data.llm2.content) {
            llm2FullResponse += data.llm2.content;
            setLlm2Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage2Id
                  ? { ...msg, text: llm2FullResponse }
                  : msg
              )
            );
          }
          if (data.llm2.error) {
            setLlm2Messages(prev =>
              prev.map(msg =>
                msg.id === aiMessage2Id
                  ? { ...msg, text: `Error: ${data.llm2!.error}` }
                  : msg
              )
            );
          }
        }

        // Handle completion
        if (data.done) {
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
            msg.id === aiMessage1Id ? { ...msg, text: abortText } : msg
          )
        );
        setLlm2Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage2Id ? { ...msg, text: abortText } : msg
          )
        );
      } else {
        const errorText = `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`;
        setLlm1Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage1Id ? { ...msg, text: errorText } : msg
          )
        );
        setLlm2Messages(prev =>
          prev.map(msg =>
            msg.id === aiMessage2Id ? { ...msg, text: errorText } : msg
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

  // Collapsible renderer for <think> blocks
  const ThinkBlock = ({ children }: { children: React.ReactNode }) => {
    const [open, setOpen] = useState(false);
    return (
      <div className="my-2 border border-yellow-700/60 bg-yellow-900/20 rounded">
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="w-full text-left px-2 py-1 text-xs font-medium text-yellow-200 flex items-center justify-between hover:bg-yellow-800/30"
        >
          <span>Model thoughts</span>
          <span className="text-yellow-300">{open ? '−' : '+'}</span>
        </button>
        {open && (
          <div className="px-2 pb-2 text-xs text-gray-200 space-y-1">
            {children}
          </div>
        )}
      </div>
    );
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
    think: ({ children }: { children: React.ReactNode }) => (
      <ThinkBlock>{children}</ThinkBlock>
    ),
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
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[
                        rehypeRaw,
                        [rehypeSanitize, sanitizeSchema],
                        rehypeHighlight,
                        rehypeKatex,
                      ]}
                      skipHtml={false}
                      components={markdownComponents}
                    >
                      {normalizeMathDelimiters(message.text)}
                    </ReactMarkdown>
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
            <button
              onClick={clearChat}
              className="px-3 py-1 text-xs bg-gray-600 text-gray-200 rounded hover:bg-gray-500 transition-colors"
              title="Clear chat"
            >
              Clear Chat
            </button>
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
    </div>
  );
}
