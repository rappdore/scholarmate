import type { AggregateStats, StreakData } from '../../types/statistics';
import {
  formatDuration,
  formatReadableDate,
} from '../../utils/statisticsCalculations';
import { format, parseISO } from 'date-fns';

interface StatsSummaryCardsProps {
  aggregateStats: AggregateStats;
  streakData: StreakData;
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: string;
  subtitle?: string;
  highlighted?: boolean;
}

function StatCard({
  title,
  value,
  icon,
  subtitle,
  highlighted = false,
}: StatCardProps) {
  return (
    <div
      className={`bg-slate-800/50 backdrop-blur-sm rounded-xl p-6 border transition-all duration-300 hover:scale-105 ${
        highlighted
          ? 'border-purple-500/50 shadow-lg shadow-purple-500/20'
          : 'border-slate-700/50 hover:border-purple-500/30'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="text-3xl">{icon}</div>
        {highlighted && (
          <div className="px-2 py-1 bg-purple-500/20 border border-purple-500/30 rounded-full text-xs text-purple-300">
            Active
          </div>
        )}
      </div>
      <div className="text-slate-400 text-sm mb-2">{title}</div>
      <div
        className={`text-2xl font-bold mb-1 ${highlighted ? 'text-purple-300' : 'text-slate-200'}`}
      >
        {value}
      </div>
      {subtitle && <div className="text-xs text-slate-500">{subtitle}</div>}
    </div>
  );
}

export default function StatsSummaryCards({
  aggregateStats,
  streakData,
}: StatsSummaryCardsProps) {
  // Format total time spent
  const totalTimeFormatted = formatDuration(
    aggregateStats.total_time_spent_seconds
  );

  // Format average speed
  const avgSpeed = aggregateStats.overall_avg_time_per_page.toFixed(1);

  // Check if streak is active (current_streak > 0)
  const hasActiveStreak = streakData.current_streak > 0;

  // Format last read date
  const lastReadFormatted = aggregateStats.last_read_date
    ? formatReadableDate(aggregateStats.last_read_date)
    : 'Never';

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
      {/* Total Sessions */}
      <StatCard
        title="Total Sessions"
        value={aggregateStats.total_sessions}
        icon="📚"
        subtitle={`Avg ${aggregateStats.avg_pages_per_session.toFixed(1)} pages/session`}
      />

      {/* Pages Read */}
      <StatCard
        title="Pages Read"
        value={`${aggregateStats.total_pages_read} pages`}
        icon="📄"
        subtitle={`${aggregateStats.longest_session_pages} pages in longest session`}
      />

      {/* Time Spent */}
      <StatCard
        title="Time Spent"
        value={totalTimeFormatted}
        icon="⏱️"
        subtitle={`Across all sessions`}
      />

      {/* Average Reading Speed */}
      <StatCard
        title="Avg Reading Speed"
        value={`${avgSpeed}s`}
        icon="⚡"
        subtitle="per page"
      />

      {/* Reading Streak */}
      <StatCard
        title="Reading Streak"
        value={
          hasActiveStreak
            ? `${streakData.current_streak} days`
            : 'No active streak'
        }
        icon={hasActiveStreak ? '🔥' : '💤'}
        subtitle={`Longest: ${streakData.longest_streak} days`}
        highlighted={hasActiveStreak}
      />

      {/* Last Read */}
      <StatCard
        title="Last Read"
        value={lastReadFormatted}
        icon="📖"
        subtitle={
          aggregateStats.first_read_date
            ? `Started ${format(parseISO(aggregateStats.first_read_date), 'MMM d, yyyy')}`
            : undefined
        }
      />
    </div>
  );
}
