import type { ReactNode } from "react";
import { H2, Select } from "./ui";
import { cx } from "../class-names";

type LeadProps = {
  headline: ReactNode;
  lede: ReactNode;
  run?: ReactNode;
};

type RunPickerProps = {
  legend: string;
  options: RunOption[];
  value: string | undefined;
  onChange: (v: string) => void;
  note?: ReactNode;
};

type AlertProps = { error: Error | null; hint?: string };

type FindingProps = {
  shows: ReactNode;
  showsTitle?: string;
  limits: ReactNode;
  limitsTitle?: string;
};

type SectionProps = {
  id?: string;
  title: string;
  intro?: ReactNode;
  action?: ReactNode;
  className?: string;
  children: ReactNode;
};

export type RunOption = { value: string; label: string; disabled?: boolean };

/** Page headline (the measured finding), its context, and the run being shown. */
export function Lead({ headline, lede, run }: LeadProps) {
  return (
    <div className="grid gap-6 py-7 md:grid-cols-heading md:items-end md:gap-10 md:pbs-11">
      <div>
        <h1 className="mbe-4 max-w-title font-display text-hero/heading tracking-title text-balance">
          {headline}
        </h1>
        <p className="max-w-description text-subtitle text-muted">{lede}</p>
      </div>
      {run}
    </div>
  );
}

/** Choose which run a sheet shows. A few short options read as a switch; longer lists become a menu. */
export function RunPicker({ legend, options, value, onChange, note }: RunPickerProps) {
  const compact = options.length <= 3 && options.every((o) => o.label.length <= 24);

  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      <legend className="mbe-1.5 p-0 text-sm text-form">{legend}</legend>
      {compact ? (
        <div className="inline-flex gap-0.5 rounded-full border border-rule bg-well p-mark-line">
          {options.map((o) => (
            <label
              key={o.value}
              className="relative cursor-pointer rounded-full px-chip-inset py-compact-gap text-sm whitespace-nowrap has-checked:bg-ink has-checked:font-semibold has-checked:text-sheet has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-pass has-disabled:cursor-default has-disabled:opacity-45"
            >
              <input
                type="radio"
                name={legend}
                value={o.value}
                checked={o.value === value}
                disabled={o.disabled}
                onChange={() => onChange(o.value)}
                className="absolute inset-0 m-0 cursor-pointer opacity-0 focus-visible:outline-none"
              />
              {o.label}
            </label>
          ))}
        </div>
      ) : (
        <Select
          aria-label={legend}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-counter"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </Select>
      )}
      {note && <p className="mbs-2 max-w-summary text-caption text-muted">{note}</p>}
    </fieldset>
  );
}

export function Alert({ error, hint }: AlertProps) {
  if (!error) {
    return null;
  }

  return (
    <div role="alert" className="mbs-6 rounded-lg bg-fail-wash px-4 py-3.5 text-fail">
      {error.message}
      {hint ? ` ${hint}` : ""}
    </div>
  );
}

/** Two facing notes under the chart: what the measurement shows, and what it doesn't. */
export function Finding({
  shows,
  showsTitle = "What the chart shows",
  limits,
  limitsTitle = "What it doesn’t show",
}: FindingProps) {
  return (
    <div className="grid gap-6 border-be border-rule pbs-9 pbe-10 md:grid-cols-2 md:gap-12">
      <div>
        <H2 className="text-section">{showsTitle}</H2>
        <p className="max-w-intro text-muted">{shows}</p>
      </div>
      <div className="border-bs-2 border-rule pbs-5 md:border-s-2 md:border-bs-0 md:ps-6 md:pbs-0">
        <H2 className="text-section">{limitsTitle}</H2>
        <p className="max-w-intro text-muted">{limits}</p>
      </div>
    </div>
  );
}

export function Section({ id, title, intro, action, className, children }: SectionProps) {
  const head = `${id ?? title.replaceAll(/\W+/g, "-").toLowerCase()}-title`;

  return (
    <section
      id={id}
      aria-labelledby={head}
      className={cx("scroll-mbs-4 border-be border-rule py-11 last:border-be-0", className)}
    >
      <div className="mbe-section-inset flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <H2 id={head}>{title}</H2>
          {intro && <p className="max-w-description text-muted">{intro}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
