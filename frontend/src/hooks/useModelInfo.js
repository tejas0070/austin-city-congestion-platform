import { useState, useEffect } from 'react';
import { fetchModelInfo } from '../services/trafficService';

/**
 * Fetch trained-model metadata once on mount and derive a headline accuracy
 * percentage from the model's empirical interval coverage (how often the 80%
 * prediction interval actually contains the real value).
 *
 * @returns {{ accuracyPct: number | null, available: boolean, loading: boolean }}
 */
export function useModelInfo() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchModelInfo()
      .then((res) => {
        if (!cancelled) setInfo(res);
      })
      .catch(() => {
        if (!cancelled) setInfo(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const coverage = info?.empirical_coverage;
  const accuracyPct =
    typeof coverage === 'number' ? Math.round(coverage * 100) : null;

  return {
    accuracyPct,
    available: Boolean(info?.available),
    loading,
  };
}
