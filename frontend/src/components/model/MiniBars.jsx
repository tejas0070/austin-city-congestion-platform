/**
 * Generic bar strip used for both the 24-hour and 7-day model graphs.
 *
 * Layout invariant: a bar's optional top/bottom labels live in their OWN fixed-
 * height rows above and below the bar area — never positioned over the bar — so
 * text can never overlap the graph. Bar height encodes the value as a percent of
 * the flexible middle row.
 *
 * @param {{
 *   bars: Array<{ heightPct: number, color: string, topLabel?: string|number,
 *                 bottomLabel?: string, title?: string, selected?: boolean }>,
 *   areaHeight?: number,
 *   gap?: number,
 *   onSelect?: (index: number) => void,
 *   axis?: string[],
 * }} props
 */
export default function MiniBars({ bars, areaHeight = 48, gap = 2, onSelect, axis }) {
  const hasTop = bars.some((b) => b.topLabel !== undefined && b.topLabel !== null);
  const hasBottom = bars.some((b) => b.bottomLabel);
  const interactive = typeof onSelect === 'function';

  return (
    <div>
      <div className="flex items-stretch" style={{ gap, height: areaHeight }}>
        {bars.map((bar, i) => {
          const Tag = interactive ? 'button' : 'div';
          return (
            <Tag
              key={i}
              type={interactive ? 'button' : undefined}
              onClick={interactive ? () => onSelect(i) : undefined}
              title={bar.title}
              className={`flex min-w-0 flex-1 flex-col items-center ${
                interactive ? 'cursor-pointer' : ''
              }`}
            >
              {hasTop && (
                <span className="h-3.5 text-[9px] font-bold leading-none text-gray-300">
                  {bar.topLabel ?? ''}
                </span>
              )}
              <span className="flex w-full flex-1 items-end">
                <span
                  className="w-full rounded-sm"
                  style={{
                    height: `${bar.heightPct}%`,
                    backgroundColor: bar.color,
                    outline: bar.selected ? '2px solid #fff' : 'none',
                    outlineOffset: '1px',
                  }}
                />
              </span>
              {hasBottom && (
                <span
                  className={`mt-1 h-3 text-[10px] leading-none ${
                    bar.selected ? 'font-extrabold text-white' : 'text-gray-500'
                  }`}
                >
                  {bar.bottomLabel ?? ''}
                </span>
              )}
            </Tag>
          );
        })}
      </div>
      {axis && (
        <div className="mt-1 flex justify-between text-[8px] text-gray-600">
          {axis.map((label, i) => (
            <span key={i}>{label}</span>
          ))}
        </div>
      )}
    </div>
  );
}
