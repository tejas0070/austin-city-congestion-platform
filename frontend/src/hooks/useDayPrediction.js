import { useState, useEffect } from 'react';
import { fetchDayPrediction } from '../services/trafficService';

/**
 * Fetch whole-day predicted congestion for a date ("YYYY-MM-DD"), or nothing
 * when `date` is null (default mode). Returns the geometry, per-hour metadata,
 * the congestion-index matrix, and load state.
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
    setLoading(true);
    fetchDayPrediction(date)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setData(null);
          setError(err?.message ?? 'Failed to load day prediction');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [date]);

  return {
    segments: data?.segments ?? null,
    hours: data?.hours ?? [],
    series: data?.series ?? [],
    weatherSource: data?.weather_source ?? null,
    loading,
    error,
  };
}
