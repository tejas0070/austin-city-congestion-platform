const LEGEND_ITEMS = [
  { color: 'bg-green-500', label: 'Free flow' },
  { color: 'bg-yellow-400', label: 'Moderate' },
  { color: 'bg-red-500', label: 'Heavy' },
];

export default function TrafficLegend() {
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
    </div>
  );
}
