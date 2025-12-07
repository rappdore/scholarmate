import { useParams, useNavigate } from 'react-router-dom';

export default function Statistics() {
  const { filename } = useParams<{ filename: string }>();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/')}
            className="px-3 py-2 text-sm bg-slate-700 hover:bg-slate-600 text-slate-200 hover:text-white rounded transition-colors flex items-center space-x-2 mb-4"
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
                d="M15 19l-7-7 7-7"
              />
            </svg>
            <span>Back to Library</span>
          </button>

          <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
            📊 Reading Statistics
          </h1>
          <p className="text-slate-400 mt-2">
            Book:{' '}
            <span className="text-slate-300">
              {decodeURIComponent(filename || '')}
            </span>
          </p>
        </div>

        {/* Statistics Content - To be implemented */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-8">
          <div className="text-center text-slate-400">
            <p className="text-lg">Statistics content coming soon...</p>
            <p className="mt-2 text-sm">
              This page will display reading analytics for your book.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
