import { useState, useEffect } from 'react';
import { fetchWeekConfidence } from '../services/trafficService';
import { weekBounds } from '../utils/modelMetrics';

// Silently re-poll so the week card reflects the self-updater's new model.
const REFRESH_MS = 3 * 60 * 1000;

/**
 * Fetch the Mon–Sun week of forecast confidence + congestion containing
 * `anchorISO` ("YYYY-MM-DD"). The request is keyed on the derived Monday, so the
 * week only refetches when the anchor crosses into a different week (not on every
 * hour scrub or same-week day change).
 *
 * When the week's Monday falls outside the backend's preview horizon the endpoint
 * returns 400; that surfaces as `unavailable` rather than a hard error.
 *
 * @param {string | null} anchorISO
 */
export function useWeekConfidence(anchorISO) {
  const mondayISO = anchorISO ? weekBounds(anchorISO).mondayISO : null;
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!mondayISO) {
      setData(null);
      setError(null);
      setUnavailable(false);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;

    // silent=true keeps current data/loading so a background refresh never
    // flashes the skeleton or blanks the card on a transient error.
    const load = (silent) => {
      if (!silent) {
        setLoading(true);
        setError(null);
        setUnavailable(false);
      }
      fetchWeekConfidence(mondayISO)
        .then((res) => {
          if (!cancelled) {
            setData(res);
            setError(null);
            setUnavailable(false);
          }
        })
        .catch((err) => {
          if (cancelled || silent) return;
          setData(null);
          // A 400 means the week is beyond the forecast horizon — expected, not a fault.
          if (err?.response?.status === 400) {
            setUnavailable(true);
          } else {
            setError(err?.message ?? 'Failed to load week forecast');
          }
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
  }, [mondayISO]);

  return {
    days: data?.days ?? [],
    confidenceAvg: data?.confidence_avg ?? null,
    confidenceLabel: data?.confidence_label ?? null,
    congestionAvg: data?.congestion_avg ?? null,
    congestionLevel: data?.congestion_level ?? null,
    startDate: data?.start_date ?? mondayISO,
    endDate: data?.end_date ?? null,
    loading,
    error,
    unavailable,
  };
}
