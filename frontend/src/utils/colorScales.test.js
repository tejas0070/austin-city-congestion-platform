import { getCongestionColor, getSeverityColor, CONGESTION_COLORS, SEVERITY_COLORS } from './colorScales';

describe('getCongestionColor', () => {
  test('returns green for green level', () => {
    expect(getCongestionColor('green')).toEqual(CONGESTION_COLORS.green);
  });
  test('returns yellow for yellow level', () => {
    expect(getCongestionColor('yellow')).toEqual(CONGESTION_COLORS.yellow);
  });
  test('returns red for red level', () => {
    expect(getCongestionColor('red')).toEqual(CONGESTION_COLORS.red);
  });
  test('returns green for unknown level', () => {
    expect(getCongestionColor('unknown')).toEqual(CONGESTION_COLORS.green);
  });
});

describe('getSeverityColor', () => {
  test('returns minor color for severity 1', () => {
    expect(getSeverityColor(1)).toEqual(SEVERITY_COLORS[0]);
  });
  test('returns critical color for severity 4', () => {
    expect(getSeverityColor(4)).toEqual(SEVERITY_COLORS[3]);
  });
  test('clamps below 1', () => {
    expect(getSeverityColor(0)).toEqual(SEVERITY_COLORS[0]);
  });
  test('clamps above 4', () => {
    expect(getSeverityColor(99)).toEqual(SEVERITY_COLORS[3]);
  });
});
