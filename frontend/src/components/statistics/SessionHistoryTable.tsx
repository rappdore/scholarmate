import { useMemo, useState } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  type SortingState,
  type ColumnDef,
} from '@tanstack/react-table';
import { format, parseISO } from 'date-fns';
import type { ReadingSession } from '../../types/statistics';
import { formatDuration } from '../../utils/statisticsCalculations';

interface SessionHistoryTableProps {
  sessions: ReadingSession[];
}

export default function SessionHistoryTable({
  sessions,
}: SessionHistoryTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState({
    pageIndex: 0,
    pageSize: 10,
  });

  // Define columns
  const columns = useMemo<ColumnDef<ReadingSession>[]>(
    () => [
      {
        accessorKey: 'session_start',
        header: 'Date',
        cell: info => {
          const date = parseISO(info.getValue() as string);
          return format(date, 'MMM d, yyyy');
        },
      },
      {
        accessorKey: 'session_start',
        id: 'time',
        header: 'Time',
        cell: info => {
          const date = parseISO(info.getValue() as string);
          return format(date, 'h:mm a');
        },
      },
      {
        accessorKey: 'pages_read',
        header: 'Pages Read',
        cell: info => (
          <span className="font-semibold text-purple-300">
            {info.getValue() as number}
          </span>
        ),
      },
      {
        accessorKey: 'average_time_per_page',
        header: 'Avg Time/Page',
        cell: info => {
          const seconds = info.getValue() as number;
          return `${seconds.toFixed(1)}s`;
        },
      },
      {
        id: 'duration',
        header: 'Duration',
        accessorFn: row => row.pages_read * row.average_time_per_page,
        cell: info => {
          const totalSeconds = info.getValue() as number;
          return formatDuration(totalSeconds);
        },
      },
    ],
    []
  );

  const table = useReactTable({
    data: sessions,
    columns,
    state: {
      sorting,
      pagination,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <div className="bg-slate-800/50 backdrop-blur-sm rounded-xl border border-slate-700/50 p-6">
      <h2 className="text-xl font-semibold text-slate-200 mb-4">
        Session History
      </h2>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map(headerGroup => (
              <tr key={headerGroup.id} className="border-b border-slate-700/50">
                {headerGroup.headers.map(header => (
                  <th
                    key={header.id}
                    className="text-left py-3 px-4 text-sm font-semibold text-slate-300 cursor-pointer hover:text-purple-300 transition-colors"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-2">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getIsSorted() && (
                        <span className="text-purple-400">
                          {header.column.getIsSorted() === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr
                key={row.id}
                className="border-b border-slate-700/30 hover:bg-slate-700/30 transition-colors"
              >
                {row.getVisibleCells().map(cell => (
                  <td
                    key={cell.id}
                    className="py-3 px-4 text-sm text-slate-400"
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {sessions.length > 10 && (
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-700/50">
          <div className="text-sm text-slate-400">
            Showing{' '}
            {table.getState().pagination.pageIndex *
              table.getState().pagination.pageSize +
              1}{' '}
            to{' '}
            {Math.min(
              (table.getState().pagination.pageIndex + 1) *
                table.getState().pagination.pageSize,
              sessions.length
            )}{' '}
            of {sessions.length} sessions
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => table.setPageIndex(0)}
              disabled={!table.getCanPreviousPage()}
              className="px-3 py-1 rounded-lg bg-slate-700/50 text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors text-sm"
            >
              «
            </button>
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="px-3 py-1 rounded-lg bg-slate-700/50 text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors text-sm"
            >
              ‹
            </button>
            <span className="text-sm text-slate-400">
              Page {table.getState().pagination.pageIndex + 1} of{' '}
              {table.getPageCount()}
            </span>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="px-3 py-1 rounded-lg bg-slate-700/50 text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors text-sm"
            >
              ›
            </button>
            <button
              onClick={() => table.setPageIndex(table.getPageCount() - 1)}
              disabled={!table.getCanNextPage()}
              className="px-3 py-1 rounded-lg bg-slate-700/50 text-slate-300 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-700 transition-colors text-sm"
            >
              »
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
