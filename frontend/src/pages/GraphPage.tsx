import { useParams, useSearchParams, Link } from 'react-router-dom';

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>();
  const [searchParams] = useSearchParams();
  const bookType = searchParams.get('type') as 'epub' | 'pdf' | null;

  return (
    <div className="h-[calc(100vh-4rem)] flex items-center justify-center bg-gray-900">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-6">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-24 w-24 mx-auto text-purple-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-gray-200 mb-4">
          Knowledge Graph
        </h1>
        <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
          <p className="text-gray-400 text-sm mb-2">
            <span className="text-gray-500">Book ID:</span>{' '}
            <span className="text-gray-300">{bookId}</span>
          </p>
          <p className="text-gray-400 text-sm">
            <span className="text-gray-500">Type:</span>{' '}
            <span className="text-gray-300">{bookType || 'Unknown'}</span>
          </p>
        </div>
        <p className="text-gray-400 mb-8">
          Interactive graph visualization is coming in Phase 4. This page will
          display an interactive D3.js force-directed graph showing all concepts
          and their relationships from this book.
        </p>
        <div className="flex flex-col gap-3">
          {bookType && bookId && (
            <Link
              to={`/read/${bookType}/${bookId}`}
              className="inline-block px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
            >
              Back to Reader
            </Link>
          )}
          <Link
            to="/"
            className="inline-block px-6 py-3 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors"
          >
            Back to Library
          </Link>
        </div>
      </div>
    </div>
  );
}
