const LEGEND_ITEMS = [
  { color: 'bg-green-500', label: 'Free flow' },
  { color: 'bg-yellow-400', label: 'Moderate' },
  { color: 'bg-red-500', label: 'Heavy' },
];

const CONFIDENCE_DOT = {
  High: 'bg-green-400',
  Medium: 'bg-yellow-400',
  Low: 'bg-red-400',
};

export default function TrafficLegend({ confidenceAvg, confidenceLabel }) {
  const showConfidence = typeof confidenceAvg === 'number' && !!confidenceLabel;
  return (
    <div className="rounded-lg bg-gray-850 p-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        Traffic
      </p>
      <ul className="space-y-1">
        {LEGEND_ITEMS.map(({ color, label }) => (
          <li key={label} className="flex items-center gap-2">
            <span className={`h-3 w-3 rounded-full ${color}`} />
            <span className="text-xs text-gray-300">{label}</span>
          </li>
        ))}
      </ul>
      {showConfidence && (
        <div className="mt-3 border-t border-gray-700 pt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Forecast confidence
          </p>
          <div className="mt-1 flex items-center gap-2">
            <span className={`h-3 w-3 rounded-full ${CONFIDENCE_DOT[confidenceLabel] ?? 'bg-gray-400'}`} />
            <span className="text-xs text-gray-200">
              {confidenceAvg}% ({confidenceLabel})
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
