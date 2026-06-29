import { useState, useEffect } from 'react';
import { fetchModelInfo } from '../services/trafficService';

// Re-poll so the panel reflects the self-updater's new model without a reload.
const REFRESH_MS = 3 * 60 * 1000;

/**
 * Fetch trained-model metadata and derive a headline accuracy percentage from the
 * model's empirical interval coverage. Re-polls periodically (silently) so the
 * accuracy badge tracks the background self-updater.
 *
 * @returns {{ accuracyPct: number | null, available: boolean, loading: boolean }}
 */
export function useModelInfo() {
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // silent=true skips the loading toggle and keeps stale data on error, so a
    // background refresh never blanks or flickers the badge.
    const load = (silent) => {
      fetchModelInfo()
        .then((res) => {
          if (!cancelled) setInfo(res);
        })
        .catch(() => {
          if (!cancelled && !silent) setInfo(null);
        })
        .finally(() => {
          if (!cancelled && !silent) setLoading(false);
        });
    };

    load(false);
    const id = setInterval(() => load(true), REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
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
