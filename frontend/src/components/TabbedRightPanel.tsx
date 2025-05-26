import { useState } from 'react';
import AIPanel from './AIPanel';
import ChatInterface from './ChatInterface';
import NotesPanel from './NotesPanel';
import HighlightsPanel from './HighlightsPanel';

interface TabbedRightPanelProps {
  filename?: string;
  currentPage: number;
  onPageJump?: (pageNumber: number) => void;
}

type TabType = 'ai' | 'chat' | 'notes' | 'highlights';

export default function TabbedRightPanel({
  filename,
  currentPage,
  onPageJump,
}: TabbedRightPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('ai');

  const tabs = [
    { id: 'ai' as TabType, label: 'AI Analysis', icon: '🧠' },
    { id: 'chat' as TabType, label: 'Chat', icon: '💬' },
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

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'ai' && (
          <AIPanel filename={filename} currentPage={currentPage} />
        )}
        {activeTab === 'chat' && (
          <ChatInterface filename={filename} currentPage={currentPage} />
        )}
        {activeTab === 'notes' && (
          <NotesPanel filename={filename} currentPage={currentPage} />
        )}
        {activeTab === 'highlights' && (
          <HighlightsPanel
            filename={filename}
            currentPage={currentPage}
            onPageJump={onPageJump}
          />
        )}
      </div>
    </div>
  );
}
