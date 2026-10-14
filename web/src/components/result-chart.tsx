import { Fragment, useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { pad } from "../format";
import { cx } from "../class-names";

type MarkGlyphProps = { state: Glyph; className?: string };

type KeyItemProps = { mark?: Glyph; children: ReactNode };

type ResultChartProps = {
  title: string;
  groups: { label: string; columns: ChartColumn[] }[];
  rows: ChartRow[];
  selected?: string;
  onSelect: (id: string) => void;
  legend: ReactNode;
  cellMin?: number;
};

type BandProps = {
  groups: { label: string; columns: ChartColumn[] }[];
  rows: ChartRow[];
  selected?: string;
  onSelect: (id: string) => void;
  showTally: boolean;
  reveal: boolean;
  cellMin: number;
};

type CellProps = {
  mark: Mark;
  current: boolean;
  delay?: number;
  top: boolean;
  left: boolean;
  onClick: () => void;
};

/** One mark on the chart. Marks follow dental charting: blue is done, red needs attention. */
export type Glyph = "pass" | "partial" | "fail" | "none";

export type Mark =
  | { state: Glyph; label: string }
  | { state: "measure"; value: number; text: string; flags?: string; label: string };

export type ChartColumn = { id: string; number: number; title?: string };

export type ChartRow = {
  key: string;
  label: string;
  marks: Record<string, Mark>;
  tally: { value: ReactNode; unit: string };
};

const BAND = 30;

/** Filled dot = correct, ring = partly correct, red cross = failed, dashed ring = no answer to judge. */
export function MarkGlyph({ state, className }: MarkGlyphProps) {
  return (
    <span
      aria-hidden="true"
      className={cx(
        {
          pass: "rounded-full bg-pass",
          partial: "rounded-full border-2 border-pass",
          fail: "text-fail cross",
          none: "rounded-full border-[1.5px] border-dashed border-muted opacity-60",
        }[state],
        className,
      )}
    />
  );
}

export function KeyItem({ mark, children }: KeyItemProps) {
  return (
    <span className="inline-flex items-center gap-compact-gap">
      {mark && (
        <MarkGlyph
          state={mark}
          className={mark === "fail" ? "inline-block size-3.5" : "inline-block size-pass-glyph"}
        />
      )}
      {children}
    </span>
  );
}

/** The result chart: one row per model, one column per case, grouped like the arches of a tooth chart.
    A single long group wraps into bands so every mark stays visible without scrolling sideways. */
export function ResultChart({
  title,
  groups,
  rows,
  selected,
  onSelect,
  legend,
  cellMin = 22,
}: ResultChartProps) {
  const [reveal, setReveal] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setReveal(false), 1600);

    return () => clearTimeout(t);
  }, []);
  const only = groups.length === 1 ? groups[0].columns : [];

  const bands =
    only.length > BAND * 1.2
      ? chunk(only, Math.ceil(only.length / Math.ceil(only.length / BAND))).map((columns, i) => [
          { label: i === 0 ? groups[0].label : "", columns },
        ])
      : [groups];

  return (
    <section
      aria-label={title}
      className="rounded-xl border border-rule bg-sheet px-3 pbs-4 pbe-3.5 md:px-6 md:pbs-section-inset md:pbe-detail-inset"
    >
      {bands.map((band, b) => (
        <div
          key={band
            .map((group) => `${group.label}:${group.columns.map((column) => column.id).join(":")}`)
            .join("|")}
          className="overflow-x-auto pbe-1 not-first:mbs-5"
        >
          <Band
            groups={band}
            rows={rows}
            selected={selected}
            onSelect={onSelect}
            showTally={b === 0}
            reveal={reveal}
            cellMin={cellMin}
          />
        </div>
      ))}
      <div className="mbs-3.5 flex flex-wrap gap-x-section-inset gap-y-2 text-sm text-muted">
        {legend}
      </div>
    </section>
  );
}

function Band({ groups, rows, selected, onSelect, showTally, reveal, cellMin }: BandProps) {
  // Fixed label and tally columns keep stacked bands aligned with each other.
  const template = `9.5rem ${groups.map((g) => `repeat(${g.columns.length},minmax(${cellMin}px,1fr))`).join(" 18px ")} 5.5rem`;

  return (
    <div className="grid min-w-chart-floor" style={{ gridTemplateColumns: template }}>
      <span />
      {groups.map((g, i) => (
        <Fragment key={`${g.label}:${g.columns.map((column) => column.id).join(":")}`}>
          {i > 0 && <span />}
          <span
            className="mbe-2 border-be-2 border-form pbe-compact-gap text-sm text-form"
            style={{ gridColumn: `span ${g.columns.length}` }}
          >
            {g.label || " "}
          </span>
        </Fragment>
      ))}
      <span />
      <span />
      {groups.map((g, i) => (
        <Fragment key={`${g.label}:${g.columns.map((column) => column.id).join(":")}`}>
          {i > 0 && <span />}
          {g.columns.map((c) => (
            <span
              key={c.id}
              title={c.title}
              className="pbe-2 text-center font-num text-caption/none text-muted tabular-nums"
            >
              {pad(c.number)}
            </span>
          ))}
        </Fragment>
      ))}
      <span />
      {rows.map((row, r) => (
        <Fragment key={row.key}>
          <span className="flex items-center pe-detail-inset text-control font-semibold whitespace-nowrap">
            {row.label}
          </span>
          {groups.map((g, i) => (
            <Fragment key={`${g.label}:${g.columns.map((column) => column.id).join(":")}`}>
              {i > 0 && <span />}
              {g.columns.map((c, j) => (
                <Cell
                  key={c.id}
                  mark={row.marks[c.id]}
                  current={c.id === selected}
                  delay={reveal ? (j + i * 24) * 18 : undefined}
                  top={r === 0}
                  left={j === 0}
                  onClick={() => onSelect(c.id)}
                />
              ))}
            </Fragment>
          ))}
          <span className="flex items-center justify-end ps-detail-inset font-num text-stat/none whitespace-nowrap tabular-nums">
            {showTally && (
              <>
                {row.tally.value}
                <small className="ms-0.5 font-sans text-sm text-muted">{row.tally.unit}</small>
              </>
            )}
          </span>
        </Fragment>
      ))}
    </div>
  );
}

function Cell({ mark, current, delay, top, left, onClick }: CellProps) {
  const motion = delay !== null && delay !== undefined ? "motion-safe:animate-mark" : "";

  const style: CSSProperties | undefined =
    delay !== null && delay !== undefined ? { animationDelay: `${delay}ms` } : undefined;

  return (
    <button
      type="button"
      aria-label={mark.label}
      aria-pressed={current}
      onClick={onClick}
      className={cx(
        "relative block aspect-square max-h-chart-cell w-full cursor-pointer border-0 border-e border-be border-grid bg-transparent hover:bg-pass-wash",
        top && "border-bs",
        left && "border-s",
        current && "bg-pass-wash shadow-selected-mark",
      )}
    >
      {mark.state === "measure" ? (
        <>
          <span
            aria-hidden="true"
            className={cx("absolute inset-x-0 inset-be-0 bg-pass/18", motion)}
            style={{ ...style, height: `${Math.round(mark.value * 100)}%` }}
          />
          <span className="absolute inset-0 grid place-items-center font-num text-sm/none tabular-nums">
            {mark.text}
          </span>
          {mark.flags && (
            <span className="absolute inset-e-1 inset-bs-mark-line text-micro/none font-bold text-fail">
              {mark.flags}
            </span>
          )}
        </>
      ) : (
        <MarkGlyph
          state={mark.state}
          className={cx(
            "absolute",
            mark.state === "fail" ? "inset-mark-outer" : "inset-mark-inner",
            motion,
          )}
        />
      )}
    </button>
  );
}

function chunk<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];

  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size));
  }

  return out;
}
