import type { ReactNode } from "react";
import type { LossRow } from "../api";
import { H2 } from "./ui";

interface LossPoint {
  iteration: number;
  loss: number;
}

export type TrainingFact = [string, ReactNode];

type LossChartProps = { rows: LossRow[] };

type FactsProps = { facts: TrainingFact[] };

type TrainingRunProps = {
  title: string;
  loss?: LossRow[];
  model: ReactNode;
  facts: TrainingFact[];
  note?: ReactNode;
};

/** Training loss (thin, muted) against validation loss (blue, with checkpoints). */
export function LossChart({ rows }: LossChartProps) {
  const W = 520;
  const H = 230;
  const L = 40;
  const R = 12;
  const T = 12;
  const B = 34;

  if (!rows.length) {
    return <p className="text-muted">No training loss was recorded for this run.</p>;
  }

  const train = rows.flatMap((row) =>
    row.kind === "train" && row.train_loss !== undefined
      ? [{ iteration: row.iteration, loss: row.train_loss }]
      : [],
  );

  const valid = rows.flatMap((row) =>
    row.kind === "validation" && row.val_loss !== undefined
      ? [{ iteration: row.iteration, loss: row.val_loss }]
      : [],
  );

  const top = Math.ceil(Math.max(...rows.map((r) => r.train_loss ?? r.val_loss ?? 0)) * 1.05) || 1;
  const steps = Math.max(...rows.map((r) => r.iteration)) || 1;
  const x = (s: number) => L + (s / steps) * (W - L - R);
  const y = (v: number) => H - B - (v / top) * (H - T - B);
  const yStep = top > 4 ? 2 : 1;
  const yTicks = Array.from({ length: Math.floor(top / yStep) + 1 }, (_, i) => i * yStep);

  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => ({
    fraction,
    step: Math.round(steps * fraction),
  }));

  const line = (points: LossPoint[]) =>
    points.map((point) => `${x(point.iteration)},${y(point.loss)}`).join(" ");

  const first = valid[0]?.loss;
  const last = valid.at(-1)?.loss;

  const span =
    valid.length > 1 && first !== undefined && last !== undefined
      ? `${first.toFixed(2)} to ${last.toFixed(2)}`
      : null;

  return (
    <>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        className="block h-auto w-full fill-muted font-num text-[12px]"
        aria-label={
          span
            ? `Validation loss went from ${span} over ${steps} updates.`
            : `Loss over ${steps} updates.`
        }
      >
        {yTicks.map((v) => (
          <g key={v}>
            <line className="stroke-grid" x1={L} x2={W - R} y1={y(v)} y2={y(v)} />
            <text x={L - 8} y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {xTicks.map(({ fraction, step }) => (
          <text
            key={fraction}
            x={x(step)}
            y={H - B + 18}
            textAnchor={fraction === 0 ? "start" : fraction === 1 ? "end" : "middle"}
          >
            {step}
          </text>
        ))}
        <text x={W - R} y={H - 2} textAnchor="end">
          Training updates
        </text>
        <polyline
          className="fill-none stroke-muted"
          points={line(train)}
          strokeWidth={1.4}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        <polyline
          className="fill-none stroke-pass"
          points={line(valid)}
          strokeWidth={2.4}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {valid.length <= 40 &&
          valid.map((r) => (
            <circle
              key={r.iteration}
              className="fill-pass"
              cx={x(r.iteration)}
              cy={y(r.loss)}
              r={3.2}
            />
          ))}
      </svg>
      <div className="mt-1.5 flex gap-5 text-sm text-muted">
        <span className="inline-flex items-center gap-[7px]">
          <i className="h-[3px] w-[18px] bg-pass" />
          Validation loss
        </span>
        <span className="inline-flex items-center gap-[7px]">
          <i className="h-0.5 w-[18px] bg-muted" />
          Training loss
        </span>
      </div>
      <p className="mt-2.5 text-sm text-muted">
        {span
          ? `Validation loss went from ${span}. That is a teacher-forced score; it does not measure the answers the model generates.`
          : "Validation loss is shown at each recorded checkpoint."}
      </p>
    </>
  );
}

/** The run's measured facts, printed like the vitals box on a chart. */
export function Facts({ facts }: FactsProps) {
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
export function TrainingRun({ title, loss, model, facts, note }: TrainingRunProps) {
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
      {loss ? (
        <div className="grid gap-10 md:grid-cols-2 md:gap-12">
          <div className="min-w-0">
            <H2>{title}</H2>
            <LossChart rows={loss} />
          </div>
          {runFacts}
        </div>
      ) : (
        <div className="max-w-[640px]">{runFacts}</div>
      )}
    </section>
  );
}
