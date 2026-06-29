export default function LoadingOverlay() {
  return (
    <div className="pointer-events-none absolute inset-0 z-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-stone bg-surface/95 px-7 py-6 shadow-float backdrop-blur">
        <div className="h-9 w-9 animate-spin rounded-full border-[3px] border-stone border-t-violet" />
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-ink-soft">
          Loading Austin traffic
        </p>
      </div>
    </div>
  );
}
