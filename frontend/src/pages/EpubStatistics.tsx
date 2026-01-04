import { useParams, Link } from 'react-router-dom';
import { useEpubStatistics } from '../hooks/useEpubStatistics';
import {
  formatDuration,
  formatReadableDate,
} from '../utils/statisticsCalculations';
import {
  formatWordsCount,
  formatReadingSpeed,
  wordsToPages,
} from '../utils/epubStatisticsCalculations';

export default function EpubStatistics() {
  const { documentId } = useParams<{ documentId: string }>();
  const epubId = documentId ? parseInt(documentId, 10) : undefined;

  const {
    sessions,
    documentInfo,
    progress,
    aggregateStats,
    streakData,
    loading,
    error,
  } = useEpubStatistics(epubId);

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-slate-400 hover:text-slate-200 mb-4 transition-colors"
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
            Back to Library
          </Link>

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-100">
                Reading Statistics
              </h1>
              {documentInfo && (
                <p className="text-slate-400 mt-1">
                  {documentInfo.title || documentInfo.filename}
                </p>
              )}
            </div>
            {epubId && (
              <Link
                to={`/read/epub/${epubId}`}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors flex items-center gap-2"
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
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
                Continue Reading
              </Link>
            )}
          </div>

          {/* Progress bar */}
          {progress && (
            <div className="mt-4">
              <div className="flex justify-between text-sm text-slate-400 mb-1">
                <span>Book Progress</span>
                <span>{progress.progress_percentage.toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className="bg-gradient-to-r from-purple-500 to-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress.progress_percentage}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center min-h-[400px]">
            <div className="text-slate-400 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400 mx-auto mb-4"></div>
              <p>Loading statistics...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 mb-6">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Empty State */}
        {!loading &&
          !error &&
          (!sessions ||
            !sessions.sessions ||
            sessions.sessions.length === 0) && (
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-12 text-center">
              <div className="text-6xl mb-4">📚</div>
              <h2 className="text-2xl font-semibold text-slate-300 mb-2">
                No Reading Data Yet
              </h2>
              <p className="text-slate-400">
                Start reading this EPUB to see your statistics appear here!
              </p>
            </div>
          )}

        {/* Main Content */}
        {!loading &&
          !error &&
          aggregateStats &&
          streakData &&
          sessions &&
          sessions.sessions.length > 0 && (
            <div className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Total Words Read */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                      <span className="text-xl">📖</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Words Read
                    </h3>
                  </div>
                  <p className="text-2xl font-bold text-slate-100">
                    {formatWordsCount(aggregateStats.total_words_read)}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    ~{aggregateStats.estimated_pages_read} pages
                  </p>
                </div>

                {/* Reading Speed */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                      <span className="text-xl">⚡</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Avg Reading Speed
                    </h3>
                  </div>
                  <p className="text-2xl font-bold text-slate-100">
                    {formatReadingSpeed(aggregateStats.avg_words_per_minute)}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    Range: {aggregateStats.slowest_reading_speed} -{' '}
                    {aggregateStats.fastest_reading_speed} wpm
                  </p>
                </div>

                {/* Time Spent */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                      <span className="text-xl">⏱️</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Time Spent
                    </h3>
                  </div>
                  <p className="text-2xl font-bold text-slate-100">
                    {formatDuration(aggregateStats.total_time_spent_seconds)}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    {aggregateStats.total_sessions} sessions
                  </p>
                </div>

                {/* Reading Streak */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                      <span className="text-xl">🔥</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Reading Streak
                    </h3>
                  </div>
                  <p className="text-2xl font-bold text-slate-100">
                    {streakData.current_streak} days
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    Longest: {streakData.longest_streak} days
                  </p>
                </div>

                {/* Words Per Session */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-pink-500/20 flex items-center justify-center">
                      <span className="text-xl">📊</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Avg Words/Session
                    </h3>
                  </div>
                  <p className="text-2xl font-bold text-slate-100">
                    {formatWordsCount(aggregateStats.avg_words_per_session)}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    Best:{' '}
                    {formatWordsCount(aggregateStats.longest_session_words)}
                  </p>
                </div>

                {/* Last Read */}
                <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                      <span className="text-xl">📅</span>
                    </div>
                    <h3 className="text-slate-400 text-sm font-medium">
                      Last Read
                    </h3>
                  </div>
                  <p className="text-lg font-bold text-slate-100">
                    {aggregateStats.last_read_date
                      ? formatReadableDate(aggregateStats.last_read_date)
                      : 'Never'}
                  </p>
                  {aggregateStats.first_read_date && (
                    <p className="text-sm text-slate-500 mt-1">
                      First:{' '}
                      {formatReadableDate(aggregateStats.first_read_date)}
                    </p>
                  )}
                </div>
              </div>

              {/* Session History Table */}
              <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 overflow-hidden">
                <div className="p-4 border-b border-slate-700/50">
                  <h3 className="text-lg font-semibold text-slate-200">
                    Session History
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-slate-700/30">
                        <th className="px-4 py-3 text-left text-xs font-medium text-slate-400 uppercase tracking-wider">
                          Date
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                          Words Read
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                          Est. Pages
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                          Duration
                        </th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-slate-400 uppercase tracking-wider">
                          Speed
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-700/30">
                      {sessions.sessions.map(session => {
                        const speed =
                          session.time_spent_seconds > 0
                            ? (session.words_read /
                                session.time_spent_seconds) *
                              60
                            : 0;
                        return (
                          <tr
                            key={session.session_id}
                            className="hover:bg-slate-700/20 transition-colors"
                          >
                            <td className="px-4 py-3 text-sm text-slate-300">
                              {formatReadableDate(session.session_start)}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-300 text-right">
                              {formatWordsCount(session.words_read)}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-400 text-right">
                              ~{wordsToPages(session.words_read)}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-300 text-right">
                              {formatDuration(session.time_spent_seconds)}
                            </td>
                            <td className="px-4 py-3 text-sm text-slate-300 text-right">
                              {formatReadingSpeed(speed)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
      </div>
    </div>
  );
}
