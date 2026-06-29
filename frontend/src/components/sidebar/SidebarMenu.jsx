import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { Menu, X, ChevronRight, CalendarDays, Sun, CloudRain } from 'lucide-react';
import { cn } from '../../lib/utils';

const EASE = [0.16, 1, 0.3, 1];

/**
 * The collapsed "console" for the sidebar. A compact card with a menu toggle and
 * a wordmark; opening it reveals the labelled section list plus a Calendar
 * shortcut. Picking a section hands control back to the parent, which swaps in
 * the floating panel.
 *
 * @param {{
 *   sections: Array<{ key: string, label: string, icon: any, hint?: string }>,
 *   open: boolean,
 *   onToggle: () => void,
 *   onSelect: (key: string) => void,
 *   onOpenCalendar: () => void,
 *   weather?: { temperature_f?: number, condition?: string, rain_alert?: boolean },
 * }} props
 */
export default function SidebarMenu({ sections, open, onToggle, onSelect, onOpenCalendar, weather }) {
  const reduce = useReducedMotion();
  const WeatherIcon = weather?.rain_alert ? CloudRain : Sun;

  return (
    <div className="w-[272px] overflow-hidden rounded-2xl border border-stone bg-surface/95 shadow-float backdrop-blur">
      {/* Toggle + wordmark */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-label={open ? 'Close menu' : 'Open menu'}
        className="flex w-full items-center gap-3 px-3.5 py-3 text-left transition-colors hover:bg-stone-soft/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-inset"
      >
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-violet text-white shadow-sm">
          {open ? <X className="size-[18px]" /> : <Menu className="size-[18px]" />}
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="font-display text-sm font-bold uppercase leading-none tracking-[0.16em] text-ink">
            Austin
          </span>
          <span className="mt-1 font-mono text-[9px] uppercase leading-none tracking-[0.22em] text-ink-faint">
            Traffic Intelligence
          </span>
        </span>
        {weather && (
          <span className="ml-auto flex shrink-0 items-center gap-1.5 pr-0.5 text-ink-soft">
            <WeatherIcon className="size-3.5" aria-hidden="true" />
            <span className="font-mono text-xs tabular-nums">{Math.round(weather.temperature_f)}°</span>
          </span>
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduce ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.24, ease: EASE }}
            className="overflow-hidden border-t border-stone"
          >
            <ul className="flex flex-col p-2">
              {sections.map((section) => {
                const Icon = section.icon;
                return (
                  <li key={section.key}>
                    <button
                      type="button"
                      onClick={() => onSelect(section.key)}
                      className="group flex w-full items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors hover:bg-violet-tint focus:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-inset"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-stone-soft text-ink-soft transition-colors group-hover:bg-violet group-hover:text-white">
                        <Icon className="size-[17px]" />
                      </span>
                      <span className="flex min-w-0 flex-col">
                        <span className="text-sm font-medium leading-tight text-ink">{section.label}</span>
                        {section.hint && (
                          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-faint">
                            {section.hint}
                          </span>
                        )}
                      </span>
                      <ChevronRight className="ml-auto size-4 shrink-0 text-ink-faint transition-transform group-hover:translate-x-0.5 group-hover:text-violet" />
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="mx-2 border-t border-stone" />

            <button
              type="button"
              onClick={onOpenCalendar}
              className={cn(
                'group m-2 flex items-center gap-3 rounded-xl px-2.5 py-2.5 text-left transition-colors',
                'hover:bg-violet-tint focus:outline-none focus-visible:ring-2 focus-visible:ring-violet focus-visible:ring-inset'
              )}
            >
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-stone-soft text-ink-soft transition-colors group-hover:bg-violet group-hover:text-white">
                <CalendarDays className="size-[17px]" />
              </span>
              <span className="text-sm font-medium text-ink">Calendar</span>
              <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-ink-faint">
                Browse days
              </span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
