import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import regression from 'regression';
import type { ReadingSession } from '../../types/statistics';

interface ReadingSpeedChartProps {
  sessions: ReadingSession[];
}

export default function ReadingSpeedChart({
  sessions,
}: ReadingSpeedChartProps) {
  // Transform data for chart (reverse to show chronological order)
  const reversedSessions = sessions.slice().reverse();

  // Calculate regression using appropriate model based on data size
  const speeds = reversedSessions.map(s => s.average_time_per_page);
  const regressionData = speeds.map((y, x) => [x, y] as [number, number]);

  // Use polynomial regression only when we have enough data points
  // Otherwise fall back to linear regression to avoid overfitting
  const POLYNOMIAL_THRESHOLD = 6;
  const usePolynomial = speeds.length >= POLYNOMIAL_THRESHOLD;

  const result = usePolynomial
    ? regression.polynomial(regressionData, { order: 2 })
    : regression.linear(regressionData);

  // Extract coefficients for derivative calculation
  // For polynomial: [a, b, c] where y = ax² + bx + c
  // For linear: [m, b] where y = mx + b
  const coefficients = result.equation;
  const rSquared = result.r2;

  const chartData = reversedSessions.map((session, index) => ({
    date: format(parseISO(session.session_start), 'MMM d'),
    fullDate: format(parseISO(session.session_start), 'MMM d, yyyy h:mm a'),
    speed: parseFloat(session.average_time_per_page.toFixed(1)),
    trend: parseFloat(result.predict(index)[1].toFixed(1)),
  }));

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const speedData = payload.find((p: any) => p.dataKey === 'speed');
      if (speedData) {
        return (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-lg">
            <p className="text-slate-300 text-sm font-semibold mb-1">
              {speedData.payload.fullDate}
            </p>
            <p className="text-purple-400 text-sm">
              <span className="font-semibold">{speedData.value}s</span> per page
            </p>
          </div>
        );
      }
    }
    return null;
  };

  // Determine trend direction for display based on derivative at the end
  const getTrendInfo = () => {
    const lastIndex = speeds.length - 1;
    let derivative: number;

    if (usePolynomial) {
      // Polynomial: f'(x) = 2ax + b
      const [a, b] = coefficients;
      derivative = 2 * a * lastIndex + b;
    } else {
      // Linear: f'(x) = m (constant slope)
      const [m] = coefficients;
      derivative = m;
    }

    if (derivative < -0.5) {
      return { direction: 'Improving', icon: '📈', color: 'text-green-400' };
    } else if (derivative > 0.5) {
      return { direction: 'Slowing', icon: '📉', color: 'text-yellow-400' };
    } else {
      return { direction: 'Stable', icon: '➡️', color: 'text-blue-400' };
    }
  };

  const trendInfo = getTrendInfo();

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-slate-200">
          Reading Speed Over Time
        </h2>
        {sessions.length >= 2 && (
          <div className="flex items-center gap-3">
            <div
              className={`flex items-center gap-1 text-sm ${trendInfo.color}`}
            >
              <span>{trendInfo.icon}</span>
              <span>{trendInfo.direction}</span>
            </div>
            {usePolynomial && (
              <div className="text-sm text-slate-400">
                R² = {rSquared.toFixed(3)}
              </div>
            )}
          </div>
        )}
      </div>

      {sessions.length < 2 ? (
        <div className="flex items-center justify-center h-64 text-slate-400">
          <div className="text-center">
            <div className="text-4xl mb-2">📊</div>
            <p>Need at least 2 sessions to show trends</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart
            data={chartData}
            margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#334155"
              opacity={0.3}
            />
            <XAxis
              dataKey="date"
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#94a3b8' }}
            />
            <YAxis
              stroke="#94a3b8"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#94a3b8' }}
              label={{
                value: 'Seconds/Page',
                angle: -90,
                position: 'insideLeft',
                style: { fill: '#94a3b8', fontSize: '12px' },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }}
              iconType="line"
            />
            {/* Trend line (polynomial or linear regression) */}
            <Line
              type="monotone"
              dataKey="trend"
              stroke="#60a5fa"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              name={usePolynomial ? 'Polynomial Trend' : 'Linear Trend'}
              opacity={0.6}
            />
            {/* Actual reading speed */}
            <Line
              type="monotone"
              dataKey="speed"
              stroke="#a78bfa"
              strokeWidth={2}
              dot={{ fill: '#a78bfa', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, fill: '#c4b5fd' }}
              name="Reading Speed"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
