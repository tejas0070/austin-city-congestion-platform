import { useState, useEffect } from 'react';
import { fetchDayPrediction } from '../services/trafficService';

// Silently re-poll so the day card reflects the self-updater's new model.
const REFRESH_MS = 3 * 60 * 1000;

/**
 * Fetch whole-day predicted congestion for a date ("YYYY-MM-DD"), or nothing
 * when `date` is null (default mode). Returns the geometry, per-hour metadata,
 * the congestion-index matrix, and load state. Re-polls silently so the panel
 * tracks background model updates without a reload.
 *
 * @param {string | null} date
 */
export function useDayPrediction(date) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!date) {
      setData(null);
      setError(null);
      setLoading(false);
      return undefined;
    }

    let cancelled = false;

    // silent=true keeps the current data/loading state so a background refresh
    // never flashes the skeleton or blanks the card on a transient error.
    const load = (silent) => {
      if (!silent) setLoading(true);
      fetchDayPrediction(date)
        .then((res) => {
          if (!cancelled) {
            setData(res);
            setError(null);
          }
        })
        .catch((err) => {
          if (!cancelled && !silent) {
            setData(null);
            setError(err?.message ?? 'Failed to load day prediction');
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
  }, [date]);

  return {
    segments: data?.segments ?? null,
    hours: data?.hours ?? [],
    series: data?.series ?? [],
    weatherSource: data?.weather_source ?? null,
    // Whole-day average forecast confidence (mean of the 24 hourly averages),
    // null when the model has no quantile/confidence signal.
    confidenceAvg: data?.confidence_avg ?? null,
    confidenceLabel: data?.confidence_label ?? null,
    // Whole-day average congestion (mean of the 24 hourly congestion averages).
    congestionAvg: data?.congestion_avg ?? null,
    congestionLevel: data?.congestion_level ?? null,
    loading,
    error,
  };
}
