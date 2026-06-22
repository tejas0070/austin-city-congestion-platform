import {
  weekBounds,
  congestionColor,
  confidenceBand,
  congestionWord,
  weekdayInitial,
  barHeightPct,
} from './modelMetrics';

describe('weekBounds', () => {
  test('returns Monday-first week for a midweek date', () => {
    // 2026-06-21 is a Sunday; its Monday-first week starts 2026-06-15.
    const { mondayISO, days } = weekBounds('2026-06-21');
    expect(mondayISO).toBe('2026-06-15');
    expect(days).toEqual([
      '2026-06-15', '2026-06-16', '2026-06-17', '2026-06-18',
      '2026-06-19', '2026-06-20', '2026-06-21',
    ]);
  });

  test('a Monday maps to itself as the week start', () => {
    const { mondayISO } = weekBounds('2026-06-15');
    expect(mondayISO).toBe('2026-06-15');
  });

  test('handles month/year rollover within the week', () => {
    // 2026-01-01 is a Thursday; its week starts Mon 2025-12-29.
    const { mondayISO, days } = weekBounds('2026-01-01');
    expect(mondayISO).toBe('2025-12-29');
    expect(days[6]).toBe('2026-01-04');
  });
});

describe('color + band helpers', () => {
  test('congestionColor maps levels and falls back to green', () => {
    expect(congestionColor('red')).toBe('#DC2626');
    expect(congestionColor('yellow')).toBe('#FACC15');
    expect(congestionColor('green')).toBe('#22C55E');
    expect(congestionColor('???')).toBe('#22C55E');
  });

  test('confidenceBand thresholds at 75 and 50', () => {
    expect(confidenceBand(90)).toBe('High');
    expect(confidenceBand(75)).toBe('High');
    expect(confidenceBand(74.9)).toBe('Medium');
    expect(confidenceBand(50)).toBe('Medium');
    expect(confidenceBand(49)).toBe('Low');
  });

  test('congestionWord and weekdayInitial', () => {
    expect(congestionWord('red')).toBe('Heavy');
    expect(congestionWord('green')).toBe('Light');
    expect(weekdayInitial('Monday')).toBe('M');
    expect(weekdayInitial('')).toBe('');
  });
});

describe('barHeightPct', () => {
  test('clamps to [floor, 100] and floors invalid input', () => {
    expect(barHeightPct(0)).toBe(6);
    expect(barHeightPct(50)).toBe(50);
    expect(barHeightPct(150)).toBe(100);
    expect(barHeightPct(undefined)).toBe(6);
    expect(barHeightPct(3, 10)).toBe(10);
  });
});
