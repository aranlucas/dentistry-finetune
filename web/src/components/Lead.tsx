import type { ReactNode } from 'react';
import { H2, Select, cx } from './ui';

export type RunOption = { value: string; label: string; disabled?: boolean };

/** Page headline (the measured finding), its context, and the run being shown. */
export function Lead({ headline, lede, run }: { headline: ReactNode; lede: ReactNode; run?: ReactNode }) {
  return (
    <div className="grid gap-6 py-7 md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:gap-10 md:pt-11">
      <div>
        <h1 className="mb-4 max-w-[18em] font-display text-[clamp(32px,4.2vw,50px)]/[1.1] tracking-[-0.012em] text-balance">{headline}</h1>
        <p className="max-w-[64ch] text-[17px] text-muted">{lede}</p>
      </div>
      {run}
    </div>
  );
}

/** Choose which run a sheet shows. A few short options read as a switch; longer lists become a menu. */
export function RunPicker({ legend, options, value, onChange, note }: {
  legend: string; options: RunOption[]; value: string | undefined; onChange: (v: string) => void; note?: ReactNode;
}) {
  const compact = options.length <= 3 && options.every(o => o.label.length <= 24);
  return (
    <fieldset className="m-0 min-w-0 border-0 p-0">
      <legend className="mb-1.5 p-0 text-sm text-form">{legend}</legend>
      {compact ? (
        <div className="inline-flex gap-0.5 rounded-full border border-rule bg-well p-[3px]">
          {options.map(o => (
            <label key={o.value} className="relative cursor-pointer rounded-full px-[15px] py-[7px] text-sm whitespace-nowrap has-checked:bg-ink has-checked:font-semibold has-checked:text-sheet has-disabled:cursor-default has-disabled:opacity-45 has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-pass">
              <input type="radio" name={legend} value={o.value} checked={o.value === value} disabled={o.disabled}
                     onChange={() => onChange(o.value)} className="absolute inset-0 m-0 cursor-pointer opacity-0 focus-visible:outline-none" />
              {o.label}
            </label>
          ))}
        </div>
      ) : (
        <Select aria-label={legend} value={value} onChange={e => onChange(e.target.value)} className="w-[min(380px,100%)]">
          {options.map(o => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
        </Select>
      )}
      {note && <p className="mt-2 max-w-[32ch] text-[13px] text-muted">{note}</p>}
    </fieldset>
  );
}

export function Alert({ error, hint }: { error: unknown; hint?: string }) {
  if (!error) return null;
  return (
    <div role="alert" className="mt-6 rounded-lg bg-fail-wash px-4 py-3.5 text-fail">
      {error instanceof Error ? error.message : String(error)}{hint ? ` ${hint}` : ''}
    </div>
  );
}

/** Two facing notes under the chart: what the measurement shows, and what it doesn't. */
export function Finding({ shows, showsTitle = 'What the chart shows', limits, limitsTitle = 'What it doesn’t show' }: {
  shows: ReactNode; showsTitle?: string; limits: ReactNode; limitsTitle?: string;
}) {
  return (
    <div className="grid gap-6 border-b border-rule pt-9 pb-10 md:grid-cols-2 md:gap-12">
      <div><H2 className="text-[22px]">{showsTitle}</H2><p className="max-w-[60ch] text-muted">{shows}</p></div>
      <div className="border-t-2 border-rule pt-5 md:border-t-0 md:border-l-2 md:pt-0 md:pl-6">
        <H2 className="text-[22px]">{limitsTitle}</H2><p className="max-w-[60ch] text-muted">{limits}</p>
      </div>
    </div>
  );
}

export function Section({ id, title, intro, action, className, children }: {
  id?: string; title: string; intro?: ReactNode; action?: ReactNode; className?: string; children: ReactNode;
}) {
  const head = `${id ?? title.replace(/\W+/g, '-').toLowerCase()}-title`;
  return (
    <section id={id} aria-labelledby={head} className={cx('scroll-mt-4 border-b border-rule py-11 last:border-b-0', className)}>
      <div className="mb-[22px] flex flex-col items-start gap-6 md:flex-row md:items-end md:justify-between">
        <div><H2 id={head}>{title}</H2>{intro && <p className="max-w-[64ch] text-muted">{intro}</p>}</div>
        {action}
      </div>
      {children}
    </section>
  );
}
