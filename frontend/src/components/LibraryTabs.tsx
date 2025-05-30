import React from 'react';
import type { BookStatus } from '../types/pdf';

interface LibraryTabsProps {
  activeTab: 'all' | BookStatus;
  counts: { all: number; new: number; reading: number; finished: number };
  onTabChange: (tab: 'all' | BookStatus) => void;
}

const LibraryTabs: React.FC<LibraryTabsProps> = ({
  activeTab,
  counts,
  onTabChange,
}) => {
  const tabs = [
    { key: 'reading' as const, label: 'Reading', count: counts.reading },
    { key: 'new' as const, label: 'New', count: counts.new },
    { key: 'finished' as const, label: 'Finished', count: counts.finished },
    { key: 'all' as const, label: 'All Books', count: counts.all },
  ];

  return (
    <div className="border-b border-slate-600/50 mb-6">
      <nav className="-mb-px flex space-x-8" aria-label="Tabs">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`
              whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm transition-colors duration-150 ease-in-out
              ${
                activeTab === tab.key
                  ? 'border-purple-400 text-purple-300'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-500'
              }
            `}
            aria-current={activeTab === tab.key ? 'page' : undefined}
          >
            <span className="flex items-center space-x-2">
              <span>{tab.label}</span>
              {tab.count > 0 && (
                <span
                  className={`
                    inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none rounded-full
                    ${
                      activeTab === tab.key
                        ? 'bg-purple-500/20 text-purple-200 border border-purple-400/30'
                        : 'bg-slate-700/50 text-slate-300 border border-slate-600/30'
                    }
                  `}
                >
                  {tab.count}
                </span>
              )}
            </span>
          </button>
        ))}
      </nav>
    </div>
  );
};

export default LibraryTabs;
