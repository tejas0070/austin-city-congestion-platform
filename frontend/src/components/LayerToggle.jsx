import { cn } from '../lib/utils';

/**
 * Row-style layer control that reads as a real switch: a labelled row with a
 * track+knob on the right. State is exposed to assistive tech via role="switch"
 * and aria-checked, and the on/off meaning is carried by position + color + the
 * accessible state (never color alone).
 *
 * @param {{ label: string, enabled: boolean, onToggle: () => void }} props
 */
export default function LayerToggle({ label, enabled, onToggle }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={onToggle}
      className={cn(
        'flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-offset-2 focus-visible:ring-offset-surface',
        enabled
          ? 'border-violet/30 bg-violet-tint text-ink'
          : 'border-stone bg-surface-hi text-ink-soft hover:border-stone hover:bg-stone-soft'
      )}
    >
      <span className="font-medium">{label}</span>
      <span
        aria-hidden="true"
        className={cn(
          'relative h-5 w-9 shrink-0 rounded-full transition-colors',
          enabled ? 'bg-violet' : 'bg-stone'
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-transform',
            enabled ? 'translate-x-[1.125rem]' : 'translate-x-0.5'
          )}
        />
      </span>
    </button>
  );
}
