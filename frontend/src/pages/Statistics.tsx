import { useParams } from 'react-router-dom';
import { useStatistics } from '../hooks/useStatistics';
import StatisticsHeader from '../components/statistics/StatisticsHeader';
import StatsSummaryCards from '../components/statistics/StatsSummaryCards';
import ReadingSpeedChart from '../components/statistics/ReadingSpeedChart';
import PagesPerSessionChart from '../components/statistics/PagesPerSessionChart';
import SessionHistoryTable from '../components/statistics/SessionHistoryTable';

export default function Statistics() {
  const { filename } = useParams<{ filename: string }>();

  const { sessions, documentInfo, aggregateStats, streakData, loading, error } =
    useStatistics(filename || '');

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <StatisticsHeader
          filename={decodeURIComponent(filename || '')}
          documentInfo={documentInfo}
        />

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
            <p className="text-red-400">⚠️ {error}</p>
          </div>
        )}

        {/* Empty State */}
        {!loading &&
          !error &&
          (!sessions ||
            !sessions.sessions ||
            sessions.sessions.length === 0) && (
            <div className="bg-slate-800/50 backdrop-blur-sm rounded-lg border border-slate-700/50 p-12 text-center">
              <div className="text-6xl mb-4">📊</div>
              <h2 className="text-2xl font-semibold text-slate-300 mb-2">
                No Reading Data Yet
              </h2>
              <p className="text-slate-400">
                Start reading to see your statistics appear here!
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
              <StatsSummaryCards
                aggregateStats={aggregateStats}
                streakData={streakData}
              />

              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <ReadingSpeedChart sessions={sessions.sessions} />
                <PagesPerSessionChart sessions={sessions.sessions} />
              </div>

              {/* Session History Table */}
              <SessionHistoryTable sessions={sessions.sessions} />
            </div>
          )}
      </div>
    </div>
  );
}
