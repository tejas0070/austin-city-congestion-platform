export default function LoadingOverlay() {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-gray-950 bg-opacity-80">
      <div className="text-center">
        <div className="mb-3 h-10 w-10 animate-spin rounded-full border-4 border-gray-600 border-t-blue-500 mx-auto" />
        <p className="text-sm text-gray-400">Loading Austin traffic data…</p>
      </div>
    </div>
  );
}
