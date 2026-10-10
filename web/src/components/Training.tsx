import type { ReactNode } from 'react';
import type { LossRow } from '../api';
import { H2 } from './ui';

/** Training loss (thin, muted) against validation loss (blue, with checkpoints). */
export function LossChart({ rows }: { rows: LossRow[] }) {
  const W = 520, H = 230, L = 40, R = 12, T = 12, B = 34;
  if (!rows.length) return <p className="text-muted">No training loss was recorded for this run.</p>;
  const train = rows.filter(r => r.kind === 'train' && r.train_loss != null);
  const valid = rows.filter(r => r.kind === 'validation' && r.val_loss != null);
  const top = Math.ceil(Math.max(...rows.map(r => r.train_loss ?? r.val_loss ?? 0)) * 1.05) || 1;
  const steps = Math.max(...rows.map(r => r.iteration)) || 1;
  const x = (s: number) => L + (s / steps) * (W - L - R), y = (v: number) => H - B - (v / top) * (H - T - B);
  const yStep = top > 4 ? 2 : 1, yTicks = Array.from({ length: Math.floor(top / yStep) + 1 }, (_, i) => i * yStep);
  const xTicks = [0, 1, 2, 3, 4].map(i => Math.round((steps * i) / 4));
  const line = (pts: LossRow[], key: 'train_loss' | 'val_loss') => pts.map(r => `${x(r.iteration)},${y(r[key]!)}`).join(' ');
  const first = valid[0]?.val_loss, last = valid.at(-1)?.val_loss;
  const span = valid.length > 1 ? `${first!.toFixed(2)} to ${last!.toFixed(2)}` : null;
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" className="block h-auto w-full fill-muted font-num text-[12px]"
           aria-label={span ? `Validation loss went from ${span} over ${steps} updates.` : `Loss over ${steps} updates.`}>
        {yTicks.map(v => (
          <g key={v}>
            <line className="stroke-grid" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {xTicks.map((s, i) => <text key={i} x={x(s)} y={H - B + 18} textAnchor={i === 0 ? 'start' : i === 4 ? 'end' : 'middle'}>{s}</text>)}
        <text x={W - R} y={H - 2} textAnchor="end">Training updates</text>
        <polyline className="fill-none stroke-muted" points={line(train, 'train_loss')} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
        <polyline className="fill-none stroke-pass" points={line(valid, 'val_loss')} strokeWidth={2.4} strokeLinejoin="round" strokeLinecap="round" />
        {valid.length <= 40 && valid.map(r => <circle key={r.iteration} className="fill-pass" cx={x(r.iteration)} cy={y(r.val_loss!)} r={3.2} />)}
      </svg>
      <div className="mt-1.5 flex gap-5 text-sm text-muted">
        <span className="inline-flex items-center gap-[7px]"><i className="h-[3px] w-[18px] bg-pass" />Validation loss</span>
        <span className="inline-flex items-center gap-[7px]"><i className="h-0.5 w-[18px] bg-muted" />Training loss</span>
      </div>
      <p className="mt-2.5 text-sm text-muted">
        {span
          ? `Validation loss went from ${span}. That is a teacher-forced score; it does not measure the answers the model generates.`
          : 'Validation loss is shown at each recorded checkpoint.'}
      </p>
    </>
  );
}

/** The run's measured facts, printed like the vitals box on a chart. */
export function Facts({ facts }: { facts: [string, ReactNode][] }) {
  return (
    <dl className="m-0 grid grid-cols-2 border-t-2 border-form">
      {facts.map(([k, v]) => (
        <div key={k} className="border-b border-rule pt-3 pb-3.5 odd:pr-4 even:border-l even:pl-4">
          <dt className="text-sm text-form">{k}</dt>
          <dd className="mt-0.5 font-num text-[28px]/tight tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Loss on the left, the run's facts on the right. A run without recorded loss shows its facts alone. */
export function TrainingRun({ title, loss, model, facts, note }: {
  title: string; loss?: LossRow[]; model: ReactNode; facts: [string, ReactNode][]; note?: ReactNode;
}) {
  const runFacts = (
    <div className="min-w-0">
      <H2>Training run</H2>
      <p className="mb-4 text-muted">{model}</p>
      <Facts facts={facts} />
      {note && <p className="mt-4 text-sm wrap-anywhere text-muted">{note}</p>}
    </div>
  );
  return (
    <section aria-label={title} className="border-b border-rule py-11">
      {loss
        ? <div className="grid gap-10 md:grid-cols-2 md:gap-12"><div className="min-w-0"><H2>{title}</H2><LossChart rows={loss} /></div>{runFacts}</div>
        : <div className="max-w-[640px]">{runFacts}</div>}
    </section>
  );
}
