/**
 * Header card for the model panel: a label plus a green accuracy badge derived
 * from the model's empirical interval coverage. The tooltip states what the
 * number means so it is never mistaken for "exactly right N% of the time".
 *
 * @param {{ accuracyPct: number | null, loading?: boolean }} props
 */
export default function ModelAccuracyBadge({ accuracyPct, loading }) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-gray-700 bg-gray-900 p-3">
      <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
        Forecast model
      </span>
      {typeof accuracyPct === 'number' ? (
        <span
          title="The forecast's predicted range contains the real value about this often."
          className="inline-flex items-baseline gap-1 rounded-lg bg-green-500/15 px-2 py-1"
        >
          <b className="text-base text-green-300">{accuracyPct}%</b>
          <span className="text-[9px] uppercase tracking-wide text-green-600">accurate</span>
        </span>
      ) : (
        <span className="text-[11px] text-gray-500">{loading ? 'Loading…' : 'N/A'}</span>
      )}
    </div>
  );
}
