import {
  formatClock,
  formatEventDate,
  titleCase,
  congestionStatus,
  severityLabel,
  withLiveTooltips,
  withPredictedTooltips,
  withEventTooltips,
  withDayTooltips,
  incidentRows,
} from './mapTooltips';

describe('formatClock', () => {
  test('formats an HH:MM time as "6:00PM"', () => {
    expect(formatClock('18:00')).toBe('6:00PM');
  });

  test('formats a morning time as AM with no leading zero hour', () => {
    expect(formatClock('09:05')).toBe('9:05AM');
  });

  test('formats an ISO datetime by its time portion', () => {
    expect(formatClock('2026-06-20T19:30')).toBe('7:30PM');
  });

  test('treats midnight and noon correctly', () => {
    expect(formatClock('00:00')).toBe('12:00AM');
    expect(formatClock('12:00')).toBe('12:00PM');
  });

  test('returns empty string for missing or unparseable input', () => {
    expect(formatClock('')).toBe('');
    expect(formatClock(null)).toBe('');
    expect(formatClock('not-a-time')).toBe('');
    expect(formatClock('25:00')).toBe('');
  });
});

describe('formatEventDate', () => {
  test('formats an ISO date as "Mon D, YYYY"', () => {
    expect(formatEventDate('2026-06-14')).toBe('Jun 14, 2026');
  });

  test('returns empty string when missing', () => {
    expect(formatEventDate('')).toBe('');
  });
});

describe('titleCase', () => {
  test('expands snake_case to Title Case', () => {
    expect(titleCase('incident_type')).toBe('Incident Type');
  });

  test('capitalizes a single word', () => {
    expect(titleCase('accident')).toBe('Accident');
  });

  test('returns empty string for empty input', () => {
    expect(titleCase('')).toBe('');
    expect(titleCase(undefined)).toBe('');
  });
});

describe('congestionStatus', () => {
  test('maps colour levels to plain words', () => {
    expect(congestionStatus('green')).toBe('Light');
    expect(congestionStatus('yellow')).toBe('Moderate');
    expect(congestionStatus('red')).toBe('Heavy');
  });

  test('falls back to Unknown', () => {
    expect(congestionStatus('purple')).toBe('Unknown');
  });
});

describe('severityLabel', () => {
  test('maps 1–4 to words', () => {
    expect(severityLabel(1)).toBe('Minor');
    expect(severityLabel(4)).toBe('Severe');
  });

  test('falls back to Unknown', () => {
    expect(severityLabel(9)).toBe('Unknown');
  });
});

describe('withLiveTooltips', () => {
  const fc = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
        properties: {
          segment_id: 's0',
          road_name: 'I-35',
          road_class: 'motorway',
          congestion_pct: 47.3,
          congestion_level: 'yellow',
          congestion_index: 1,
        },
      },
    ],
  };

  test('produces clean labels and keeps the colour binding', () => {
    const out = withLiveTooltips(fc);
    const p = out.features[0].properties;
    expect(p).toEqual({
      congestion_index: 1,
      Road: 'I-35',
      Congestion: '47%',
      Status: 'Moderate',
    });
  });

  test('drops internal columns (no underscores leak)', () => {
    const p = withLiveTooltips(fc).features[0].properties;
    expect(p).not.toHaveProperty('segment_id');
    expect(p).not.toHaveProperty('road_class');
    expect(p).not.toHaveProperty('congestion_pct');
  });

  test('does not mutate the input', () => {
    withLiveTooltips(fc);
    expect(fc.features[0].properties).toHaveProperty('segment_id', 's0');
  });

  test('passes empty collections through', () => {
    expect(withLiveTooltips({ features: [] })).toEqual({ features: [] });
  });
});

describe('withPredictedTooltips', () => {
  const fc = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1]] },
        properties: {
          road_name: 'MoPac',
          congestion_pct: 62.6,
          congestion_low: 50.2,
          congestion_high: 74.8,
          confidence_pct: 82,
          confidence_label: 'High',
          congestion_index: 2,
          predicted_for: '2026-06-20T18:00',
        },
      },
    ],
  };

  test('folds interval + confidence + forecast time into clean labels', () => {
    const p = withPredictedTooltips(fc).features[0].properties;
    expect(p).toEqual({
      congestion_index: 2,
      Road: 'MoPac',
      Congestion: '63%',
      'Forecast Range': '50–75%',
      Confidence: '82% (High)',
      'Forecast Time': '6:00PM',
    });
  });

  test('leaves range and confidence blank when quantiles are absent', () => {
    const noQuant = {
      features: [
        { properties: { road_name: 'R', congestion_pct: 10, congestion_index: 0, predicted_for: '2026-06-20T08:00' } },
      ],
    };
    const p = withPredictedTooltips(noQuant).features[0].properties;
    expect(p['Forecast Range']).toBe('');
    expect(p.Confidence).toBe('');
    expect(p['Forecast Time']).toBe('8:00AM');
  });
});

describe('withEventTooltips', () => {
  const fc = {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [-97.71, 30.38] },
        properties: {
          id: 'afc_01',
          source: 'austin_fc',
          name: 'Austin FC vs LA Galaxy',
          venue: 'Q2 Stadium',
          date: '2026-06-14',
          time: '19:30',
          category: 'Sports',
          expected_attendance: 20738,
          days_until: 5,
        },
      },
    ],
  };

  test('drops id/source/days_until and formats date + time', () => {
    const p = withEventTooltips(fc).features[0].properties;
    expect(p).toEqual({
      Event: 'Austin FC vs LA Galaxy',
      Venue: 'Q2 Stadium',
      Date: 'Jun 14, 2026',
      Time: '7:30PM',
      Category: 'Sports',
      Attendance: 20738,
    });
    expect(p).not.toHaveProperty('id');
    expect(p).not.toHaveProperty('days_until');
  });
});

describe('withDayTooltips', () => {
  test('adds Road while keeping cg_* hour columns', () => {
    const fc = {
      features: [
        { properties: { segment_id: 's0', road_name: 'A', cg_0: 1, cg_1: 2 } },
      ],
    };
    const p = withDayTooltips(fc).features[0].properties;
    expect(p.Road).toBe('A');
    expect(p.cg_0).toBe(1);
    expect(p.cg_1).toBe(2);
  });
});

describe('incidentRows', () => {
  const incidents = {
    features: [
      {
        geometry: { coordinates: [-97.73, 30.28] },
        properties: {
          incident_id: 'sim_0',
          incident_type: 'accident',
          description: 'Multi-vehicle collision',
          severity: 3,
          start_time: '2026-06-20T12:00:00Z',
        },
      },
    ],
  };

  test('produces icon-layer rows with clean labels', () => {
    const [row] = incidentRows(incidents);
    expect(row).toEqual({
      lat: 30.28,
      lng: -97.73,
      icon: 'place',
      severity: 3,
      Type: 'Accident',
      Description: 'Multi-vehicle collision',
      Severity: 'Major',
    });
  });

  test('returns an empty array when there are no incidents', () => {
    expect(incidentRows(undefined)).toEqual([]);
    expect(incidentRows({ features: [] })).toEqual([]);
  });
});
