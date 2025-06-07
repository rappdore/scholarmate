import { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'highlight.js/styles/github.css';
import 'katex/dist/katex.min.css';
import '../styles/katex-dark.css';
import type { Components } from 'react-markdown';
import { notesService, epubNotesService } from '../services/api';

interface PDFNote {
  id: number;
  pdf_filename: string;
  page_number: number;
  title: string;
  chat_content: string;
  created_at: string;
  updated_at: string;
}

interface EPUBNote {
  id: number;
  epub_filename: string;
  nav_id: string;
  chapter_id: string;
  chapter_title: string;
  title: string;
  chat_content: string;
  created_at: string;
  updated_at: string;
}

type Note = PDFNote | EPUBNote;

interface NotesPanelProps {
  filename?: string;
  currentPage: number;
  currentNavId?: string; // For EPUBs
  currentChapterId?: string; // For EPUB chapter identification
  currentChapterTitle?: string; // For EPUB chapter display
  documentType: 'pdf' | 'epub';
}

export default function NotesPanel({
  filename,
  currentPage,
  currentNavId,
  currentChapterId,
  currentChapterTitle,
  documentType,
}: NotesPanelProps) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedNote, setExpandedNote] = useState<number | null>(null);

  // Load notes for the current document (PDF or EPUB)
  useEffect(() => {
    if (!filename) {
      setNotes([]);
      return;
    }

    const loadNotes = async () => {
      setLoading(true);
      setError(null);
      try {
        let fetchedNotes;
        if (documentType === 'pdf') {
          fetchedNotes = await notesService.getChatNotesForPdf(filename);
        } else if (documentType === 'epub') {
          fetchedNotes = await epubNotesService.getChatNotesForEpub(filename);
        } else {
          throw new Error(`Unsupported document type: ${documentType}`);
        }
        setNotes(fetchedNotes);
      } catch (err) {
        console.error('Error loading notes:', err);
        setError('Failed to load notes');
      } finally {
        setLoading(false);
      }
    };

    loadNotes();
  }, [filename, documentType]);

  const deleteNote = async (noteId: number) => {
    try {
      if (documentType === 'pdf') {
        await notesService.deleteChatNote(noteId);
      } else if (documentType === 'epub') {
        await epubNotesService.deleteChatNote(noteId);
      }
      setNotes(notes.filter(note => note.id !== noteId));
      if (expandedNote === noteId) {
        setExpandedNote(null);
      }
    } catch (err) {
      console.error('Error deleting note:', err);
      setError('Failed to delete note');
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
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
      <pre className="bg-gray-700 text-gray-200 p-2 rounded-md overflow-x-auto text-xs border border-gray-600">
        {children}
      </pre>
    ),
    h1: ({ children }) => (
      <h1 className="text-sm font-bold text-gray-100 mt-3 mb-2 first:mt-0">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-sm font-semibold text-gray-200 mt-3 mb-2 first:mt-0">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-sm font-medium text-gray-200 mt-2 mb-1 first:mt-0">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-xs font-medium text-gray-300 mt-2 mb-1 first:mt-0">
        {children}
      </h4>
    ),
    h5: ({ children }) => (
      <h5 className="text-xs font-medium text-gray-300 mt-1 mb-1 first:mt-0">
        {children}
      </h5>
    ),
    h6: ({ children }) => (
      <h6 className="text-xs font-medium text-gray-400 mt-1 mb-1 first:mt-0">
        {children}
      </h6>
    ),
    p: ({ children }) => (
      <p className="text-xs text-gray-300 leading-relaxed mb-2">{children}</p>
    ),
    strong: ({ children }) => (
      <strong className="text-gray-200 font-semibold">{children}</strong>
    ),
    em: ({ children }) => <em className="text-gray-300 italic">{children}</em>,
    ul: ({ children }) => (
      <ul className="text-xs text-gray-300 list-disc list-inside mb-2 space-y-1">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="text-xs text-gray-300 list-decimal list-inside mb-2 space-y-1">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="text-gray-300">{children}</li>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-gray-600 pl-3 text-xs text-gray-400 italic mb-2">
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
        <table className="min-w-full text-xs text-gray-300 border border-gray-600">
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

  // Helper functions to check note context
  const isCurrentContext = (note: Note): boolean => {
    if (documentType === 'pdf') {
      return (note as PDFNote).page_number === currentPage;
    } else if (documentType === 'epub') {
      return (note as EPUBNote).nav_id === currentNavId;
    }
    return false;
  };

  const getLocationLabel = (note: Note): string => {
    if (documentType === 'pdf') {
      return `Page ${(note as PDFNote).page_number}`;
    } else if (documentType === 'epub') {
      const epubNote = note as EPUBNote;
      return `${epubNote.chapter_title || 'Unknown Chapter'}`;
    }
    return 'Unknown location';
  };

  const getSortKey = (note: Note): string | number => {
    if (documentType === 'pdf') {
      return (note as PDFNote).page_number;
    } else if (documentType === 'epub') {
      return (note as EPUBNote).nav_id;
    }
    return 0;
  };

  // Separate notes by current context and other contexts
  const currentContextNotes = notes.filter(isCurrentContext);
  const otherContextNotes = notes.filter(note => !isCurrentContext(note));

  if (!filename) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-900">
        <p className="text-gray-400 text-sm">
          Open a {documentType?.toUpperCase() || 'document'} to view notes
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-700 px-4 py-3 bg-gray-800">
        <h3 className="text-sm font-medium text-gray-200">
          Notes for {filename}
        </h3>
        <p className="text-xs text-gray-400 mt-1">
          {notes.length} {notes.length === 1 ? 'note' : 'notes'} saved
        </p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-400 text-sm">Loading notes...</div>
          </div>
        ) : error ? (
          <div className="p-4">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        ) : notes.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center">
              <div className="text-gray-500 text-2xl mb-2">📝</div>
              <p className="text-gray-400 text-sm">No notes saved yet</p>
              <p className="text-gray-500 text-xs mt-1">
                Save chat conversations to create notes
              </p>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Current Context Notes */}
            {currentContextNotes.length > 0 && (
              <div>
                <h4 className="text-xs font-semibold text-purple-400 mb-3 uppercase tracking-wider">
                  {documentType === 'pdf'
                    ? `Current Page (${currentPage})`
                    : `Current Section (${currentChapterTitle || 'Unknown'})`}
                </h4>
                <div className="space-y-3">
                  {currentContextNotes.map((note: Note) => (
                    <div
                      key={note.id}
                      className="bg-gray-800 border border-purple-500/30 rounded-lg"
                    >
                      <div
                        className="p-3 cursor-pointer hover:bg-gray-750 transition-colors"
                        onClick={() =>
                          setExpandedNote(
                            expandedNote === note.id ? null : note.id
                          )
                        }
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h5 className="text-sm font-medium text-gray-200 line-clamp-2">
                            {note.title}
                          </h5>
                          <button
                            onClick={e => {
                              e.stopPropagation();
                              deleteNote(note.id);
                            }}
                            className="text-gray-400 hover:text-red-400 transition-colors ml-2 flex-shrink-0"
                            title="Delete note"
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
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                              />
                            </svg>
                          </button>
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-400">
                          <span>{getLocationLabel(note)}</span>
                          <span>{formatDate(note.created_at)}</span>
                        </div>
                      </div>
                      {expandedNote === note.id && (
                        <div className="px-3 pb-3">
                          <div className="flex justify-end mb-2">
                            <button
                              onClick={() => setExpandedNote(null)}
                              className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                            >
                              Hide conversation
                            </button>
                          </div>
                          <div className="pt-2 border-t border-gray-700">
                            <div className="max-w-none text-gray-300">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm, remarkMath]}
                                rehypePlugins={[rehypeHighlight, rehypeKatex]}
                                components={markdownComponents}
                              >
                                {note.chat_content}
                              </ReactMarkdown>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Other Context Notes */}
            {otherContextNotes.length > 0 && (
              <div>
                {currentContextNotes.length > 0 && (
                  <div className="border-t border-gray-700 pt-4 mt-4">
                    <h4 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">
                      {documentType === 'pdf'
                        ? 'Other Pages'
                        : 'Other Sections'}
                    </h4>
                  </div>
                )}
                <div className="space-y-3">
                  {otherContextNotes
                    .sort((a: Note, b: Note) => {
                      const aKey = getSortKey(a);
                      const bKey = getSortKey(b);
                      if (
                        typeof aKey === 'number' &&
                        typeof bKey === 'number'
                      ) {
                        return aKey - bKey;
                      }
                      return String(aKey).localeCompare(String(bKey));
                    })
                    .map((note: Note) => (
                      <div
                        key={note.id}
                        className="bg-gray-800 border border-gray-700 rounded-lg"
                      >
                        <div
                          className="p-3 cursor-pointer hover:bg-gray-750 transition-colors"
                          onClick={() =>
                            setExpandedNote(
                              expandedNote === note.id ? null : note.id
                            )
                          }
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <h5 className="text-sm font-medium text-gray-200 line-clamp-2">
                                {note.title}
                              </h5>
                            </div>
                            <button
                              onClick={e => {
                                e.stopPropagation();
                                deleteNote(note.id);
                              }}
                              className="text-gray-400 hover:text-red-400 transition-colors ml-2 flex-shrink-0"
                              title="Delete note"
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
                                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                                />
                              </svg>
                            </button>
                          </div>
                          <div className="flex items-center justify-between text-xs text-gray-400">
                            <span className="text-blue-400">
                              {getLocationLabel(note)}
                            </span>
                            <span>{formatDate(note.created_at)}</span>
                          </div>
                        </div>
                        {expandedNote === note.id && (
                          <div className="px-3 pb-3">
                            <div className="flex justify-end mb-2">
                              <button
                                onClick={() => setExpandedNote(null)}
                                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                              >
                                Hide conversation
                              </button>
                            </div>
                            <div className="pt-2 border-t border-gray-700">
                              <div className="max-w-none text-gray-300">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm, remarkMath]}
                                  rehypePlugins={[rehypeHighlight, rehypeKatex]}
                                  components={markdownComponents}
                                >
                                  {note.chat_content}
                                </ReactMarkdown>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
