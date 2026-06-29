// Shared pill color classes for the model cards. Confidence pills key on the
// High/Medium/Low band; congestion pills key on the green/yellow/red level.
// Tinted for light surfaces, with darker "ink" text for AA contrast.

export const CONFIDENCE_PILL = {
  High: 'bg-signal-green/15 text-signal-green-ink',
  Medium: 'bg-signal-amber/20 text-signal-amber-ink',
  Low: 'bg-signal-red/15 text-signal-red-ink',
};

export const CONGESTION_PILL = {
  green: 'bg-signal-green/15 text-signal-green-ink',
  yellow: 'bg-signal-amber/20 text-signal-amber-ink',
  red: 'bg-signal-red/15 text-signal-red-ink',
};

// Accent colors for the section markers (◆ confidence is violet, ▮ congestion amber-ink).
export const CONFIDENCE_ACCENT = '#6B5B95';
export const CONGESTION_ACCENT = '#946A00';
