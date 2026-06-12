import { useState, useEffect, useRef } from 'react';

/**
 * Fetch data keyed by a numeric id, with the cancellation guard every data
 * hook in this app needs: a slow response for a previous key must not
 * overwrite newer state, and nothing may setState after unmount.
 *
 * The fetcher is read through a ref so callers can pass inline closures
 * without retriggering the effect; only `key` changes refetch.
 */
export function useAsyncData<T>(
  key: number | undefined,
  fetcher: (key: number) => Promise<T>,
  errorText: string
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const errorTextRef = useRef(errorText);
  errorTextRef.current = errorText;

  useEffect(() => {
    if (key === undefined) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetcherRef
      .current(key)
      .then(result => {
        if (!cancelled) setData(result);
      })
      .catch(err => {
        console.error(`[useAsyncData] ${errorTextRef.current}:`, err);
        if (!cancelled) setError(errorTextRef.current);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [key]);

  return { data, loading, error };
}
