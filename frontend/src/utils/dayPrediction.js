/**
 * Build a single GeoJSON FeatureCollection for a whole day, with one congestion
 * column per hour (`cg_0`…`cg_23`). The map loads this ONCE; scrubbing hours then
 * only swaps the layer's color field, never the data.
 *
 * This avoids kepler's row-data limitation: a loaded RowDataContainer cannot be
 * updated in place (its `update` is a no-op), so replacing data per hour via
 * updateVisData silently keeps the original rows. Encoding every hour as a column
 * sidesteps that entirely.
 *
 * Pure and immutable: returns a new FeatureCollection; inputs are untouched.
 *
 * @param {{features: Array}} segments  geometry + static props (sent once per day)
 * @param {number[][]} series           per-hour arrays of congestion_index per segment
 * @returns {{type: string, features: Array} | null}
 */
export function buildDayFC(segments, series) {
  if (!segments?.features || !Array.isArray(series) || series.length === 0) return null;

  return {
    type: 'FeatureCollection',
    features: segments.features.map((feature, i) => {
      const properties = { ...feature.properties };
      for (let h = 0; h < series.length; h += 1) {
        properties[hourField(h)] = series[h]?.[i] ?? 0;
      }
      return { ...feature, properties };
    }),
  };
}

/** Column name holding the congestion index for a given hour. */
export function hourField(hour) {
  return `cg_${hour}`;
}
