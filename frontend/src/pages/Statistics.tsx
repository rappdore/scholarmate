import { useParams } from 'react-router-dom';
import { useStatistics } from '../hooks/useStatistics';
import {
  formatDuration,
  formatReadableDate,
} from '../utils/statisticsCalculations';

export default function Statistics() {
  const { filename } = useParams<{ filename: string }>();

  // Test the hook and calculations
  const { sessions, aggregateStats, streakData, calendarData, loading, error } =
    useStatistics(filename || '');

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
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

        {/* Loading State */}
        {loading && (
          <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-8">
            <div className="text-center text-slate-400">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-400 mx-auto mb-4"></div>
              <p className="text-lg">Loading statistics...</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-900/20 border border-red-700/50 rounded-lg p-4 mb-6">
            <p className="text-red-400">⚠️ {error}</p>
          </div>
        )}

        {/* Test Display - Temporary */}
        {!loading && !error && (
          <div className="space-y-6">
            {/* Raw Data */}
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-6">
              <h2 className="text-xl font-semibold text-slate-200 mb-4">
                🧪 Test Display (Temporary)
              </h2>

              {!sessions ||
              !sessions.sessions ||
              sessions.sessions.length === 0 ? (
                <p className="text-slate-400">
                  No sessions found for this PDF.
                </p>
              ) : (
                <div className="space-y-4 text-sm">
                  {/* Aggregate Stats */}
                  <div>
                    <h3 className="font-semibold text-slate-300 mb-2">
                      Aggregate Statistics:
                    </h3>
                    <div className="bg-slate-900/50 p-4 rounded">
                      <pre className="text-slate-400 overflow-auto">
                        {JSON.stringify(aggregateStats, null, 2)}
                      </pre>
                    </div>
                  </div>

                  {/* Streak Data */}
                  <div>
                    <h3 className="font-semibold text-slate-300 mb-2">
                      Streak Data:
                    </h3>
                    <div className="bg-slate-900/50 p-4 rounded">
                      <pre className="text-slate-400 overflow-auto">
                        {JSON.stringify(streakData, null, 2)}
                      </pre>
                    </div>
                  </div>

                  {/* Calendar Data (first 5 days) */}
                  <div>
                    <h3 className="font-semibold text-slate-300 mb-2">
                      Calendar Data (first 5 days):
                    </h3>
                    <div className="bg-slate-900/50 p-4 rounded">
                      <pre className="text-slate-400 overflow-auto">
                        {JSON.stringify(calendarData?.slice(0, 5), null, 2)}
                      </pre>
                    </div>
                  </div>

                  {/* Test Formatting Functions */}
                  <div>
                    <h3 className="font-semibold text-slate-300 mb-2">
                      Formatting Tests:
                    </h3>
                    <div className="bg-slate-900/50 p-4 rounded space-y-2 text-slate-400">
                      <p>
                        <span className="text-slate-500">
                          formatDuration(125):
                        </span>{' '}
                        {formatDuration(125)}
                      </p>
                      <p>
                        <span className="text-slate-500">
                          formatDuration(3665):
                        </span>{' '}
                        {formatDuration(3665)}
                      </p>
                      {aggregateStats && (
                        <>
                          <p>
                            <span className="text-slate-500">
                              Total time formatted:
                            </span>{' '}
                            {formatDuration(
                              aggregateStats.total_time_spent_seconds
                            )}
                          </p>
                          <p>
                            <span className="text-slate-500">
                              Last read date formatted:
                            </span>{' '}
                            {formatReadableDate(aggregateStats.last_read_date)}
                          </p>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Session Count */}
                  <div>
                    <h3 className="font-semibold text-slate-300 mb-2">
                      Session Summary:
                    </h3>
                    <div className="bg-slate-900/50 p-4 rounded text-slate-400">
                      <p>Total Sessions: {sessions?.total_sessions}</p>
                      <p>
                        Total Pages: {aggregateStats?.total_pages_read} pages
                      </p>
                      <p>
                        Average Speed:{' '}
                        {aggregateStats?.overall_avg_time_per_page.toFixed(1)}{' '}
                        sec/page
                      </p>
                      <p>Current Streak: {streakData?.current_streak} days</p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
