import { buildMonthGrid, eventsByDay, toISODate, isWithinRange } from './calendar';

describe('buildMonthGrid', () => {
  test('produces full weeks of 7 days each, Sunday-aligned', () => {
    const weeks = buildMonthGrid(2026, 5); // June 2026
    expect(weeks.length).toBeGreaterThanOrEqual(5);
    weeks.forEach((week) => expect(week).toHaveLength(7));
    // First cell of the grid must be a Sunday.
    expect(weeks[0][0].date.getDay()).toBe(0);
  });

  test('flags in-month vs adjacent-month cells', () => {
    const weeks = buildMonthGrid(2026, 5); // June 2026 — June 1 is a Monday
    const flat = weeks.flat();
    // June 1 is in-month; the leading Sunday (May 31) is not.
    const june1 = flat.find((c) => c.iso === '2026-06-01');
    const may31 = flat.find((c) => c.iso === '2026-05-31');
    expect(june1.inMonth).toBe(true);
    expect(may31.inMonth).toBe(false);
  });

  test('contains every day of the target month exactly once', () => {
    const weeks = buildMonthGrid(2026, 1); // February 2026 (28 days, non-leap)
    const inMonthDays = weeks.flat().filter((c) => c.inMonth).map((c) => c.day);
    expect(inMonthDays).toEqual([...Array(28)].map((_, i) => i + 1));
  });
});

describe('eventsByDay', () => {
  test('groups events by their date and ignores undated ones', () => {
    const events = [
      { id: 'a', date: '2026-06-14' },
      { id: 'b', date: '2026-06-14' },
      { id: 'c', date: '2026-06-19' },
      { id: 'd' }, // no date
    ];
    const map = eventsByDay(events);
    expect(map.get('2026-06-14')).toHaveLength(2);
    expect(map.get('2026-06-19')).toHaveLength(1);
    expect(map.has('undefined')).toBe(false);
  });

  test('handles empty / null input', () => {
    expect(eventsByDay(null).size).toBe(0);
    expect(eventsByDay([]).size).toBe(0);
  });
});

describe('toISODate / isWithinRange', () => {
  test('formats a local date as YYYY-MM-DD', () => {
    expect(toISODate(new Date(2026, 5, 14))).toBe('2026-06-14');
  });

  test('range check is inclusive', () => {
    expect(isWithinRange('2026-06-14', '2026-06-14', '2026-09-12')).toBe(true);
    expect(isWithinRange('2026-09-12', '2026-06-14', '2026-09-12')).toBe(true);
    expect(isWithinRange('2026-06-13', '2026-06-14', '2026-09-12')).toBe(false);
    expect(isWithinRange('2026-09-13', '2026-06-14', '2026-09-12')).toBe(false);
  });
});
