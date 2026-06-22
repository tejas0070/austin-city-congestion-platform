// Shared pill color classes for the model cards. Confidence pills key on the
// High/Medium/Low band; congestion pills key on the green/yellow/red level.

export const CONFIDENCE_PILL = {
  High: 'bg-green-500/20 text-green-300',
  Medium: 'bg-yellow-500/20 text-yellow-300',
  Low: 'bg-red-500/20 text-red-300',
};

export const CONGESTION_PILL = {
  green: 'bg-green-500/20 text-green-300',
  yellow: 'bg-yellow-500/20 text-yellow-300',
  red: 'bg-red-500/20 text-red-300',
};

// Accent colors for the section markers (◆ confidence is blue, ▮ congestion amber).
export const CONFIDENCE_ACCENT = '#6f93d6';
export const CONGESTION_ACCENT = '#caa24a';
