import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SettingsModal from './SettingsModal';

export default function Header() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 bg-slate-800/95 backdrop-blur-sm border-b border-slate-700/50">
        <div className="px-4 py-3 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1
              onClick={() => navigate('/')}
              className="text-xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent cursor-pointer hover:opacity-80 transition-opacity"
            >
              📚 Scholarmate
            </h1>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 rounded-lg transition-colors group"
              title="Settings"
            >
              <svg
                className="w-5 h-5 transition-transform group-hover:rotate-45"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </button>
          </div>
        </div>
      </header>

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
      />
    </>
  );
}
