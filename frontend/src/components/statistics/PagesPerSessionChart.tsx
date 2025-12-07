import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import type { ReadingSession } from '../../types/statistics';

interface PagesPerSessionChartProps {
  sessions: ReadingSession[];
}

type ViewMode = 'session' | 'day';

const VIEW_MODE = {
  SESSION: 'session' as const,
  DAY: 'day' as const,
};

export default function PagesPerSessionChart({
  sessions,
}: PagesPerSessionChartProps) {
  const [viewMode, setViewMode] = useState<ViewMode>(VIEW_MODE.DAY);

  // Helper function to parse local timestamps from backend
  const parseLocalTimestamp = (timestamp: string): Date => {
    // Backend sends timestamps in format "YYYY-MM-DD HH:MM:SS" as local time
    // Split and construct Date object directly to avoid timezone issues
    const [datePart, timePart] = timestamp.split(' ');
    const [year, month, day] = datePart.split('-').map(Number);
    const [hours, minutes, seconds] = timePart.split(':').map(Number);
    return new Date(year, month - 1, day, hours, minutes, seconds);
  };

  // Transform data for session view
  const getSessionData = () => {
    const recentSessions = sessions.slice(0, 20).reverse();
    return recentSessions.map(session => {
      const localDate = parseLocalTimestamp(session.session_start);
      return {
        label: format(localDate, 'MMM d'),
        fullDate: format(localDate, 'MMM d, yyyy h:mm a'),
        pages: session.pages_read,
        sessions: 1,
      };
    });
  };

  // Transform data for day view (aggregate by day)
  const getDayData = () => {
    const dayMap = new Map<
      string,
      { pages: number; sessions: number; dates: string[] }
    >();

    sessions.forEach(session => {
      const localDate = parseLocalTimestamp(session.session_start);
      const dateKey = format(localDate, 'yyyy-MM-dd');
      const existing = dayMap.get(dateKey);

      if (existing) {
        existing.pages += session.pages_read;
        existing.sessions += 1;
        existing.dates.push(format(localDate, 'h:mm a'));
      } else {
        dayMap.set(dateKey, {
          pages: session.pages_read,
          sessions: 1,
          dates: [format(localDate, 'h:mm a')],
        });
      }
    });

    // Convert to array and sort by date (most recent last), limit to 30 days
    return Array.from(dayMap.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .slice(-30)
      .map(([dateKey, data]) => ({
        label: format(new Date(dateKey), 'MMM d'),
        fullDate: format(new Date(dateKey), 'MMM d, yyyy'),
        pages: data.pages,
        sessions: data.sessions,
        sessionTimes: data.dates.join(', '),
      }));
  };

  const chartData =
    viewMode === VIEW_MODE.SESSION ? getSessionData() : getDayData();

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-lg">
          <p className="text-slate-300 text-sm font-semibold mb-1">
            {data.fullDate}
          </p>
          <p className="text-green-400 text-sm">
            <span className="font-semibold">{data.pages} pages</span> read
          </p>
          {viewMode === VIEW_MODE.DAY && data.sessions > 1 && (
            <p className="text-slate-400 text-xs mt-1">
              {data.sessions} sessions: {data.sessionTimes}
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-slate-200">
          Pages Per {viewMode === VIEW_MODE.SESSION ? 'Session' : 'Day'}
          {viewMode === VIEW_MODE.SESSION && sessions.length > 20 && (
            <span className="text-sm text-slate-400 ml-2">
              (Last 20 sessions)
            </span>
          )}
          {viewMode === VIEW_MODE.DAY && (
            <span className="text-sm text-slate-400 ml-2">(Last 30 days)</span>
          )}
        </h2>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2 bg-slate-700/30 rounded-lg p-1">
          <button
            onClick={() => setViewMode(VIEW_MODE.SESSION)}
            className={`px-3 py-1 rounded text-sm transition-all ${
              viewMode === VIEW_MODE.SESSION
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            By Session
          </button>
          <button
            onClick={() => setViewMode(VIEW_MODE.DAY)}
            className={`px-3 py-1 rounded text-sm transition-all ${
              viewMode === VIEW_MODE.DAY
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-slate-400 hover:text-slate-300'
            }`}
          >
            By Day
          </button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="flex items-center justify-center h-64 text-slate-400">
          <div className="text-center">
            <div className="text-4xl mb-2">📊</div>
            <p>No session data available</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={chartData}
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#334155"
              opacity={0.3}
            />
            <XAxis
              dataKey="label"
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#94a3b8' }}
            />
            <YAxis
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#94a3b8' }}
              label={{
                value: 'Pages Read',
                angle: -90,
                position: 'insideLeft',
                style: { fill: '#94a3b8', fontSize: '12px' },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
              iconType="rect"
            />
            <Bar
              dataKey="pages"
              fill="#82ca9d"
              name="Pages Read"
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
