export default function LayerToggle({ label, enabled, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors ${
        enabled
          ? 'bg-blue-600 text-white'
          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
      }`}
    >
      <span>{label}</span>
      <span className="text-xs opacity-70">{enabled ? 'ON' : 'OFF'}</span>
    </button>
  );
}
