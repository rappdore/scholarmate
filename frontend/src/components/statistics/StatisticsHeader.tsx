interface StatisticsHeaderProps {
  filename: string;
}

export default function StatisticsHeader({ filename }: StatisticsHeaderProps) {
  return (
    <div className="mb-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="text-4xl">📊</div>
        <div>
          <h1 className="text-3xl font-bold text-slate-200 mb-1">
            Reading Statistics
          </h1>
          <p className="text-slate-400 font-mono text-sm">{filename}</p>
        </div>
      </div>
    </div>
  );
}
