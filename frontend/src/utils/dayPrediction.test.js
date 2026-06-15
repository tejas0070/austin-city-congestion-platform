import { buildDayFC, hourField } from './dayPrediction';

const SEGMENTS = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
      properties: { segment_id: 's0', road_name: 'A' } },
    { type: 'Feature', geometry: { type: 'LineString', coordinates: [[2, 2], [3, 3]] },
      properties: { segment_id: 's1', road_name: 'B' } },
  ],
};

// 3 hours, 2 segments.
const SERIES = [
  [0, 2], // hour 0
  [1, 1], // hour 1
  [2, 0], // hour 2
];

describe('buildDayFC', () => {
  test('encodes one congestion column per hour', () => {
    const fc = buildDayFC(SEGMENTS, SERIES);
    expect(fc.features[0].properties.cg_0).toBe(0);
    expect(fc.features[0].properties.cg_1).toBe(1);
    expect(fc.features[0].properties.cg_2).toBe(2);
    expect(fc.features[1].properties.cg_0).toBe(2);
    expect(fc.features[1].properties.cg_2).toBe(0);
  });

  test('preserves static properties', () => {
    const fc = buildDayFC(SEGMENTS, SERIES);
    expect(fc.features[0].properties.segment_id).toBe('s0');
  });

  test('does not mutate the input segments', () => {
    buildDayFC(SEGMENTS, SERIES);
    expect(SEGMENTS.features[0].properties).not.toHaveProperty('cg_0');
  });

  test('defaults missing values to 0', () => {
    const fc = buildDayFC(SEGMENTS, [[5]]); // one value for two segments
    expect(fc.features[1].properties.cg_0).toBe(0);
  });

  test('returns null on invalid input', () => {
    expect(buildDayFC(null, SERIES)).toBeNull();
    expect(buildDayFC(SEGMENTS, null)).toBeNull();
    expect(buildDayFC(SEGMENTS, [])).toBeNull();
  });
});

describe('hourField', () => {
  test('formats the per-hour column name', () => {
    expect(hourField(0)).toBe('cg_0');
    expect(hourField(17)).toBe('cg_17');
  });
});
