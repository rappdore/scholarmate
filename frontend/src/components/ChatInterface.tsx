import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'highlight.js/styles/github.css';
import 'katex/dist/katex.min.css'; // KaTeX CSS for math rendering
import '../styles/katex-dark.css'; // Custom dark theme for KaTeX
import type { Components } from 'react-markdown';
import { chatService, notesService } from '../services/api';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
  timestamp: Date;
}

interface ChatInterfaceProps {
  filename?: string;
  currentPage: number;
}

export default function ChatInterface({
  filename,
  currentPage,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const clearChat = () => {
    setMessages([]);
  };

  const saveChatAsNote = async () => {
    if (!filename || messages.length === 0) return;

    setSaving(true);
    try {
      // Convert messages to a formatted string
      const chatContent = messages
        .map(msg => `**${msg.isUser ? 'You' : 'AI'}**: ${msg.text}`)
        .join('\n\n');

      const title =
        noteTitle.trim() ||
        `Chat on page ${currentPage} - ${new Date().toLocaleDateString()}`;

      await notesService.saveChatNote(
        filename,
        currentPage,
        title,
        chatContent
      );

      setShowSaveDialog(false);
      setNoteTitle('');

      // Show success message (you could add a toast notification here)
      console.log('Chat saved as note successfully!');
    } catch (error) {
      console.error('Error saving chat note:', error);
      // Show error message (you could add a toast notification here)
    } finally {
      setSaving(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!inputText.trim() || !filename) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputText,
      isUser: true,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputText;
    setInputText('');
    setLoading(true);
    setStreaming(true);

    // Create placeholder AI message for streaming
    const aiMessageId = (Date.now() + 1).toString();
    const aiMessage: Message = {
      id: aiMessageId,
      text: '',
      isUser: false,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, aiMessage]);

    try {
      // Convert messages to chat history format
      const chatHistory = messages.map(msg => ({
        role: msg.isUser ? 'user' : 'assistant',
        content: msg.text,
      }));

      // Stream the AI response
      const stream = chatService.streamChat(
        currentInput,
        filename,
        currentPage,
        chatHistory
      );

      let fullResponse = '';
      for await (const chunk of stream) {
        fullResponse += chunk;
        setMessages(prev =>
          prev.map(msg =>
            msg.id === aiMessageId ? { ...msg, text: fullResponse } : msg
          )
        );
      }
    } catch (error) {
      console.error('Chat failed:', error);
      const errorText = `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please make sure the AI service is running.`;

      setMessages(prev =>
        prev.map(msg =>
          msg.id === aiMessageId ? { ...msg, text: errorText } : msg
        )
      );
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
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
    h4: ({ children }) => (
      <h4 className="text-xs font-medium text-gray-200 mt-2 mb-1 first:mt-0">
        {children}
      </h4>
    ),
    h5: ({ children }) => (
      <h5 className="text-xs font-medium text-gray-200 mt-1 mb-1 first:mt-0">
        {children}
      </h5>
    ),
    h6: ({ children }) => (
      <h6 className="text-xs font-medium text-gray-300 mt-1 mb-1 first:mt-0">
        {children}
      </h6>
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
    table: ({ children }) => (
      <div className="overflow-x-auto mb-2">
        <table className="min-w-full text-sm text-gray-200 border border-gray-500">
          {children}
        </table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-gray-600">{children}</thead>,
    tbody: ({ children }) => <tbody className="bg-gray-700">{children}</tbody>,
    tr: ({ children }) => (
      <tr className="border-b border-gray-500">{children}</tr>
    ),
    th: ({ children }) => (
      <th className="px-2 py-1 text-left text-gray-100 font-medium">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-2 py-1 text-gray-200">{children}</td>
    ),
  } as Components;

  return (
    <div className="h-full flex flex-col bg-gray-900 border-t border-gray-700">
      {/* Header */}
      <div className="border-b border-gray-700 px-4 py-2 bg-gray-800 flex justify-between items-center">
        <h3 className="text-sm font-medium text-gray-200">
          Chat about {filename ? `${filename} (Page ${currentPage})` : 'PDF'}
        </h3>
        {messages.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowSaveDialog(true)}
              disabled={!filename}
              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors disabled:bg-gray-600 disabled:cursor-not-allowed"
              title="Save chat as note"
            >
              Save Note
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

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.length === 0 ? (
          <div className="text-gray-400 text-sm text-center">
            {filename
              ? 'Ask questions about the PDF content...'
              : 'Open a PDF to start chatting'}
          </div>
        ) : (
          messages.map(message => (
            <div
              key={message.id}
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-xs lg:max-w-md px-3 py-2 rounded-lg text-sm ${
                  message.isUser
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-200'
                }`}
              >
                {message.isUser ? (
                  message.text
                ) : (
                  <div className="max-w-none text-gray-200">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm, remarkMath]}
                      rehypePlugins={[rehypeHighlight, rehypeKatex]}
                      components={markdownComponents}
                    >
                      {message.text}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {streaming && (
          <div className="flex justify-start">
            <div className="bg-gray-700 text-gray-200 px-3 py-2 rounded-lg text-sm">
              <span className="inline-block animate-pulse">
                AI is typing...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-700 p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              filename ? 'Ask about this PDF...' : 'Open a PDF to chat'
            }
            disabled={!filename || loading}
            className="flex-1 px-3 py-2 border border-gray-600 bg-gray-800 text-gray-200 placeholder-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-700 disabled:text-gray-500"
          />
          <button
            onClick={sendMessage}
            disabled={!inputText.trim() || !filename || loading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:bg-gray-600 disabled:cursor-not-allowed hover:bg-blue-500 transition-colors"
          >
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>

      {/* Save Note Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 w-96 max-w-90vw">
            <h3 className="text-lg font-medium text-gray-200 mb-4">
              Save Chat as Note
            </h3>

            <div className="mb-4">
              <label className="block text-sm text-gray-300 mb-2">
                Note Title
              </label>
              <input
                type="text"
                value={noteTitle}
                onChange={e => setNoteTitle(e.target.value)}
                placeholder={`Chat on page ${currentPage} - ${new Date().toLocaleDateString()}`}
                className="w-full px-3 py-2 border border-gray-600 bg-gray-700 text-gray-200 placeholder-gray-400 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="mb-4 text-sm text-gray-400">
              This will save the entire chat conversation ({messages.length}{' '}
              messages) linked to page {currentPage} of {filename}.
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
                onClick={saveChatAsNote}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save Note'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
