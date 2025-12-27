import type { Document } from '../../types/document';
import { getBookStatus } from '../../utils/bookStatus';

interface StatisticsHeaderProps {
  pdfId: number | undefined;
  documentInfo: Document | null;
}

export default function StatisticsHeader({
  pdfId,
  documentInfo,
}: StatisticsHeaderProps) {
  const getStatusBadge = () => {
    if (!documentInfo) return null;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const status = getBookStatus(documentInfo as any);

    const statusConfig = {
      new: {
        label: 'New',
        color: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
        icon: '📚',
      },
      reading: {
        label: 'Reading',
        color: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
        icon: '📖',
      },
      finished: {
        label: 'Finished',
        color: 'bg-green-500/20 text-green-300 border-green-500/30',
        icon: '✅',
      },
    };

    const config = statusConfig[status as keyof typeof statusConfig];

    // Return null if status is invalid
    if (!config) return null;

    return (
      <div
        className={`text-sm px-3 py-1.5 rounded-full border flex items-center gap-1.5 ${config.color}`}
      >
        <span>{config.icon}</span>
        <span>{config.label}</span>
      </div>
    );
  };

  return (
    <div className="mb-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="text-4xl">📊</div>
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-3xl font-bold text-slate-200">
              Reading Statistics
            </h1>
            {getStatusBadge()}
          </div>
          <p className="text-slate-400 font-mono text-sm">
            {documentInfo?.filename}
          </p>
        </div>
      </div>
    </div>
  );
}
