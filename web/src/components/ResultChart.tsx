import { Fragment, useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { pad } from '../format';
import { cx } from './ui';

/** One mark on the chart. Marks follow dental charting: blue is done, red needs attention. */
export type Glyph = 'pass' | 'partial' | 'fail' | 'none';
export type Mark =
  | { state: Glyph; label: string }
  | { state: 'measure'; value: number; text: string; flags?: string; label: string };

export type ChartColumn = { id: string; number: number; title?: string };
export type ChartRow = { key: string; label: string; marks: Record<string, Mark>; tally: { value: ReactNode; unit: string } };

const BAND = 30;

/** Filled dot = correct, ring = partly correct, red cross = failed, dashed ring = no answer to judge. */
export function MarkGlyph({ state, className }: { state: Glyph; className?: string }) {
  return <span aria-hidden="true" className={cx({
    pass: 'rounded-full bg-pass',
    partial: 'rounded-full border-2 border-pass',
    fail: 'cross text-fail',
    none: 'rounded-full border-[1.5px] border-dashed border-muted opacity-60',
  }[state], className)} />;
}

export function KeyItem({ mark, children }: { mark?: Glyph; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-[7px]">
      {mark && <MarkGlyph state={mark} className={mark === 'fail' ? 'inline-block size-3.5' : 'inline-block size-[11px]'} />}
      {children}
    </span>
  );
}

/** The result chart: one row per model, one column per case, grouped like the arches of a tooth chart.
    A single long group wraps into bands so every mark stays visible without scrolling sideways. */
export function ResultChart({ title, groups, rows, selected, onSelect, legend, cellMin = 22 }: {
  title: string; groups: { label: string; columns: ChartColumn[] }[]; rows: ChartRow[];
  selected?: string; onSelect: (id: string) => void; legend: ReactNode; cellMin?: number;
}) {
  const [reveal, setReveal] = useState(true);
  useEffect(() => { const t = setTimeout(() => setReveal(false), 1600); return () => clearTimeout(t); }, []);
  const only = groups.length === 1 ? groups[0].columns : [];
  const bands = only.length > BAND * 1.2
    ? chunk(only, Math.ceil(only.length / Math.ceil(only.length / BAND))).map((columns, i) => [{ label: i === 0 ? groups[0].label : '', columns }])
    : [groups];

  return (
    <section aria-label={title} className="rounded-xl border border-rule bg-sheet px-3 pt-4 pb-3.5 md:px-6 md:pt-[22px] md:pb-[18px]">
      {bands.map((band, b) => (
        <div key={b} className="overflow-x-auto pb-1 not-first:mt-5">
          <Band groups={band} rows={rows} selected={selected} onSelect={onSelect} showTally={b === 0} reveal={reveal} cellMin={cellMin} />
        </div>
      ))}
      <div className="mt-3.5 flex flex-wrap gap-x-[22px] gap-y-2 text-sm text-muted">{legend}</div>
    </section>
  );
}

function Band({ groups, rows, selected, onSelect, showTally, reveal, cellMin }: {
  groups: { label: string; columns: ChartColumn[] }[]; rows: ChartRow[];
  selected?: string; onSelect: (id: string) => void; showTally: boolean; reveal: boolean; cellMin: number;
}) {
  // Fixed label and tally columns keep stacked bands aligned with each other.
  const template = `9.5rem ${groups.map(g => `repeat(${g.columns.length},minmax(${cellMin}px,1fr))`).join(' 18px ')} 5.5rem`;
  return (
    <div className="grid min-w-[640px]" style={{ gridTemplateColumns: template }}>
      <span />
      {groups.map((g, i) => (
        <Fragment key={i}>
          {i > 0 && <span />}
          <span className="mb-2 border-b-2 border-form pb-[7px] text-sm text-form" style={{ gridColumn: `span ${g.columns.length}` }}>{g.label || ' '}</span>
        </Fragment>
      ))}
      <span />
      <span />
      {groups.map((g, i) => (
        <Fragment key={i}>
          {i > 0 && <span />}
          {g.columns.map(c => <span key={c.id} title={c.title} className="pb-2 text-center font-num text-[13px]/none text-muted tabular-nums">{pad(c.number)}</span>)}
        </Fragment>
      ))}
      <span />
      {rows.map((row, r) => (
        <Fragment key={row.key}>
          <span className="flex items-center pr-[18px] text-[15px] font-semibold whitespace-nowrap">{row.label}</span>
          {groups.map((g, i) => (
            <Fragment key={i}>
              {i > 0 && <span />}
              {g.columns.map((c, j) => (
                <Cell key={c.id} mark={row.marks[c.id]} current={c.id === selected} delay={reveal ? (j + i * 24) * 18 : undefined}
                      top={r === 0} left={j === 0} onClick={() => onSelect(c.id)} />
              ))}
            </Fragment>
          ))}
          <span className="flex items-center justify-end pl-[18px] font-num text-[26px]/none whitespace-nowrap tabular-nums">
            {showTally && <>{row.tally.value}<small className="ml-0.5 font-sans text-sm text-muted">{row.tally.unit}</small></>}
          </span>
        </Fragment>
      ))}
    </div>
  );
}

function Cell({ mark, current, delay, top, left, onClick }: {
  mark: Mark; current: boolean; delay?: number; top: boolean; left: boolean; onClick: () => void;
}) {
  const motion = delay != null ? 'motion-safe:animate-mark' : '';
  const style = delay != null ? { animationDelay: `${delay}ms` } as CSSProperties : undefined;
  return (
    <button type="button" aria-label={mark.label} aria-pressed={current} onClick={onClick}
            className={cx('relative block aspect-square max-h-[46px] w-full cursor-pointer border-0 border-r border-b border-grid bg-transparent hover:bg-pass-wash',
                          top && 'border-t', left && 'border-l', current && 'bg-pass-wash shadow-[inset_0_0_0_2px_var(--color-pass)]')}>
      {mark.state === 'measure' ? (
        <>
          <span aria-hidden="true" className={cx('absolute inset-x-0 bottom-0 bg-pass/18', motion)} style={{ ...style, height: `${Math.round(mark.value * 100)}%` }} />
          <span className="absolute inset-0 grid place-items-center font-num text-sm/none tabular-nums">{mark.text}</span>
          {mark.flags && <span className="absolute top-[3px] right-1 text-[10px]/none font-bold text-fail">{mark.flags}</span>}
        </>
      ) : (
        <MarkGlyph state={mark.state} className={cx('absolute', mark.state === 'fail' ? 'inset-[24%]' : 'inset-[26%]', motion)} />
      )}
    </button>
  );
}

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size));
  return out;
}
