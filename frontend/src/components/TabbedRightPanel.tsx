import { useState } from 'react';
import AIPanel from './AIPanel';
import ChatInterface from './ChatInterface';
import DualChatInterface from './DualChatInterface';
import NotesPanel from './NotesPanel';
import HighlightsPanel from './HighlightsPanel';
import type { DocumentType } from '../types/document';
import type { EPUBHighlight } from '../utils/epubHighlights';

interface TabbedRightPanelProps {
  pdfId?: number;
  epubId?: number;
  filename?: string;
  documentType: DocumentType | null;
  currentPage: number;
  currentNavId?: string;
  scrollProgress?: number; // For EPUBs: 0.0-1.0 position within current section
  currentChapterId?: string; // For EPUB chapter identification
  currentChapterTitle?: string; // For EPUB chapter display
  onPageJump?: (pageNumber: number) => void;
  onEPUBHighlightSelect?: (highlight: EPUBHighlight) => void;
}

type TabType = 'ai' | 'chat' | 'dual-chat' | 'notes' | 'highlights';

export default function TabbedRightPanel({
  pdfId,
  epubId,
  filename,
  documentType,
  currentPage,
  currentNavId,
  scrollProgress,
  currentChapterId,
  currentChapterTitle,
  onPageJump,
  onEPUBHighlightSelect,
}: TabbedRightPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('ai');

  // Define tabs - Dual Chat only for PDFs
  const tabs = [
    { id: 'ai' as TabType, label: 'AI Analysis', icon: '🧠' },
    { id: 'chat' as TabType, label: 'Chat', icon: '💬' },
    ...(documentType === 'pdf'
      ? [{ id: 'dual-chat' as TabType, label: 'Dual Chat', icon: '🤖' }]
      : []),
    { id: 'notes' as TabType, label: 'Notes', icon: '📝' },
    { id: 'highlights' as TabType, label: 'Highlights', icon: '🖍️' },
  ];

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Tab Headers */}
      <div className="flex border-b border-gray-700 bg-gray-800">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`
              flex-1 px-4 py-3 text-sm font-medium transition-colors
              ${
                activeTab === tab.id
                  ? 'text-white bg-gray-900 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              }
            `}
          >
            <span className="mr-2">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content.
          All panels stay mounted and inactive ones are hidden with CSS —
          deliberate (owner decision, 2026-06-12): switching tabs must preserve
          in-progress chat streams, draft input, and scroll positions, which
          unmounting would destroy. The cost is that every panel fetches on
          reader open. Do not convert to lazy mounting. */}
      <div className="flex-1 overflow-hidden">
        <div className={`h-full ${activeTab === 'ai' ? '' : 'hidden'}`}>
          <AIPanel
            pdfId={pdfId}
            epubId={epubId}
            filename={filename}
            documentType={documentType ?? undefined}
            currentPage={currentPage}
            currentNavId={currentNavId}
            scrollProgress={scrollProgress}
          />
        </div>
        <div className={`h-full ${activeTab === 'chat' ? '' : 'hidden'}`}>
          <ChatInterface
            pdfId={pdfId}
            epubId={epubId}
            filename={filename}
            currentPage={currentPage}
            currentNavId={currentNavId}
            scrollProgress={scrollProgress}
            currentChapterId={currentChapterId}
            currentChapterTitle={currentChapterTitle}
            documentType={documentType === 'pdf' ? 'pdf' : 'epub'}
          />
        </div>
        {documentType === 'pdf' && (
          <div
            className={`h-full ${activeTab === 'dual-chat' ? '' : 'hidden'}`}
          >
            <DualChatInterface
              pdfId={pdfId}
              filename={filename}
              currentPage={currentPage}
            />
          </div>
        )}
        <div className={`h-full ${activeTab === 'notes' ? '' : 'hidden'}`}>
          <NotesPanel
            pdfId={pdfId}
            epubId={epubId}
            filename={filename}
            currentPage={currentPage}
            currentNavId={currentNavId}
            currentChapterTitle={currentChapterTitle}
            documentType={documentType === 'pdf' ? 'pdf' : 'epub'}
          />
        </div>
        <div className={`h-full ${activeTab === 'highlights' ? '' : 'hidden'}`}>
          <HighlightsPanel
            pdfId={pdfId}
            epubId={epubId}
            filename={filename}
            documentType={documentType}
            currentPage={currentPage}
            onPageJump={onPageJump}
            onEPUBHighlightSelect={onEPUBHighlightSelect}
          />
        </div>
      </div>
    </div>
  );
}
