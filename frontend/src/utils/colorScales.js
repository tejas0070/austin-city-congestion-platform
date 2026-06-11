export const CONGESTION_COLORS = {
  green: [0, 200, 100],
  yellow: [255, 200, 0],
  red: [220, 50, 50],
};

export function getCongestionColor(level) {
  return CONGESTION_COLORS[level] ?? CONGESTION_COLORS.green;
}

export const SEVERITY_COLORS = [
  [100, 200, 100],  // 1 - minor
  [255, 200, 0],    // 2 - moderate
  [255, 140, 0],    // 3 - major
  [220, 50, 50],    // 4 - critical
];

export function getSeverityColor(severity) {
  const idx = Math.max(0, Math.min(severity - 1, SEVERITY_COLORS.length - 1));
  return SEVERITY_COLORS[idx];
}
