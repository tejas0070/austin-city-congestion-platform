import MiniBars from './MiniBars';

/**
 * One metric section inside a model card: an accented section label, a big
 * number with a band pill and a sub-note, then a bar graph. Used for both the
 * Confidence (blue) and Congestion (g/y/r) readouts at day and week scale.
 *
 * @param {{
 *   marker: string,
 *   markerColor: string,
 *   title: string,
 *   value: string,
 *   pillText?: string,
 *   pillClass?: string,
 *   subNote?: string,
 *   bars?: Array<object>,
 *   areaHeight?: number,
 *   gap?: number,
 *   onSelect?: (index: number) => void,
 *   axis?: string[],
 *   emptyNote?: string,
 * }} props
 */
export default function MetricReadout({
  marker,
  markerColor,
  title,
  value,
  pillText,
  pillClass,
  subNote,
  bars,
  areaHeight,
  gap,
  onSelect,
  axis,
  emptyNote,
}) {
  return (
    <div>
      <div
        className="mb-2 text-[9px] font-extrabold uppercase tracking-wider"
        style={{ color: markerColor }}
      >
        <span aria-hidden="true">{marker}</span> {title}
      </div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <div className="text-2xl font-extrabold leading-none text-white">
          {value}
          {pillText && (
            <span
              className={`ml-1.5 inline-block rounded px-1.5 py-0.5 align-middle text-[10px] font-bold ${pillClass}`}
            >
              {pillText}
            </span>
          )}
        </div>
        {subNote && <span className="shrink-0 text-[11px] text-gray-400">{subNote}</span>}
      </div>
      {bars && bars.length > 0 ? (
        <MiniBars bars={bars} areaHeight={areaHeight} gap={gap} onSelect={onSelect} axis={axis} />
      ) : (
        emptyNote && <p className="py-2 text-[11px] text-gray-500">{emptyNote}</p>
      )}
    </div>
  );
}
