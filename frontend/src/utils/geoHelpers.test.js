import { isValidCoord, featureCollectionToRows } from './geoHelpers';

describe('isValidCoord', () => {
  test('returns true for valid Austin coords', () => {
    expect(isValidCoord(30.2672, -97.7431)).toBe(true);
  });
  test('returns false for out-of-range latitude', () => {
    expect(isValidCoord(91, -97.7431)).toBe(false);
  });
  test('returns false for out-of-range longitude', () => {
    expect(isValidCoord(30.2672, -181)).toBe(false);
  });
  test('returns false for non-numbers', () => {
    expect(isValidCoord('30', '-97')).toBe(false);
  });
});

describe('featureCollectionToRows', () => {
  test('converts features to flat rows', () => {
    const fc = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [-97.7431, 30.2672] },
          properties: { name: 'test', speed: 45 },
        },
      ],
    };
    const rows = featureCollectionToRows(fc);
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('test');
    expect(rows[0].speed).toBe(45);
    expect(rows[0].longitude).toBe(-97.7431);
    expect(rows[0].latitude).toBe(30.2672);
  });

  test('returns empty array for null input', () => {
    expect(featureCollectionToRows(null)).toEqual([]);
  });

  test('returns empty array for missing features', () => {
    expect(featureCollectionToRows({})).toEqual([]);
  });
});
