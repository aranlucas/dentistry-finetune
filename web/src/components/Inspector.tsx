import { forwardRef, useLayoutEffect, useRef, type ReactNode } from 'react';
import { pad } from '../format';
import type { Glyph } from './ResultChart';
import { Button, H3, Raw, cx } from './ui';

export type ListItem = { id: string; number: number; text: string; sub: string };

/** Read every answer: a filterable list of cases beside the selected case. */
export const Inspector = forwardRef<HTMLElement, {
  items: ListItem[]; total: number; noun: string; selected?: string; onSelect: (id: string) => void;
  tools: ReactNode; heading: (item: ListItem) => string; children: ReactNode;
}>(function Inspector({ items, total, noun, selected, onSelect, tools, heading, children }, ref) {
  const index = items.findIndex(i => i.id === selected), current = items[index];
  const list = useRef<HTMLDivElement>(null);
  // Keep the selected case visible in the list without moving the page.
  useLayoutEffect(() => {
    const box = list.current, item = box?.querySelector<HTMLElement>('[aria-current=true]');
    if (!box || !item) return;
    if (item.offsetTop < box.scrollTop) box.scrollTop = item.offsetTop;
    else if (item.offsetTop + item.offsetHeight > box.scrollTop + box.clientHeight) box.scrollTop = item.offsetTop + item.offsetHeight - box.clientHeight;
  }, [selected]);
  const empty = <p className="p-3.5 text-sm text-muted">No {noun} match. Clear the filters to see all of them.</p>;
  return (
    <div className="grid min-h-[560px] overflow-hidden rounded-xl border border-rule bg-sheet md:grid-cols-[240px_minmax(0,1fr)] lg:grid-cols-[290px_minmax(0,1fr)]">
      <aside className="flex min-h-0 flex-col border-b border-rule bg-well md:border-r md:border-b-0">
        <div className="grid gap-2 border-b border-rule p-3.5">
          {tools}
          <span className="text-[13px] text-muted">{items.length} of {total} {noun}</span>
        </div>
        <div ref={list} className="relative max-h-[220px] overflow-auto md:max-h-[640px]">
          {items.map(item => (
            <button type="button" key={item.id} aria-current={item.id === selected} onClick={() => onSelect(item.id)}
                    className="group grid w-full cursor-pointer grid-cols-[28px_minmax(0,1fr)] gap-x-2.5 gap-y-[3px] border-0 border-b border-grid bg-transparent px-3.5 py-3 text-left text-[15px]/snug hover:bg-sheet/60 aria-[current=true]:bg-sheet aria-[current=true]:shadow-[inset_3px_0_0_var(--color-pass)]">
              <span className="font-num text-muted tabular-nums group-aria-[current=true]:text-pass">{pad(item.number)}</span>
              <span className="line-clamp-2">{item.text || '(Empty)'}</span>
              <span className="col-start-2 truncate text-[13px] text-muted">{item.sub}</span>
            </button>
          ))}
          {!items.length && empty}
        </div>
      </aside>
      <article ref={ref} aria-live="polite" tabIndex={-1} className="min-w-0 scroll-mt-4 p-[18px] md:px-8 md:py-7">
        {current ? (
          <>
            <div className="flex items-center justify-between gap-4 text-sm text-form">
              <span>{heading(current)}</span>
              <div className="flex gap-1.5">
                <Button disabled={index <= 0} onClick={() => onSelect(items[index - 1].id)}>Previous</Button>
                <Button disabled={index >= items.length - 1} onClick={() => onSelect(items[index + 1].id)}>Next</Button>
              </div>
            </div>
            {children}
          </>
        ) : empty}
      </article>
    </div>
  );
});

/** The case as the models saw it. */
export const Prompt = ({ children }: { children: ReactNode }) =>
  <p className="mt-4 mb-6 max-w-[44ch] font-display text-[clamp(22px,2.4vw,28px)]/[1.35]">{children}</p>;

/** The frozen reference answer, marked in the charting blue. */
export function Target({ title, answer, note }: { title: string; answer: string; note: string }) {
  return (
    <div className="mb-7 border-l-[3px] border-pass py-1 pl-4">
      <H3 className="text-sm text-pass">{title}</H3>
      <p className="font-display text-lg/snug">{answer}</p>
      <small className="mt-1 block text-[13px] text-muted">{note}</small>
    </div>
  );
}

export const Answers = ({ children }: { children: ReactNode }) =>
  <div className="grid gap-6 min-[1100px]:grid-cols-2">{children}</div>;

export type Verdict = { state: Glyph; text: string };

/** One model's saved answer, its verdict, and how it was produced. */
export function Answer({ title, verdict, raw, prose, missing, reason, foot }: {
  title: string; verdict: Verdict; raw?: string | null; prose?: boolean;
  missing: { title: string; detail: string }; reason?: string; foot?: string;
}) {
  return (
    <section className="min-w-0">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <H3 className="mb-0">{title}</H3>
        <span className={cx('text-sm', {
          pass: 'font-semibold text-pass', partial: 'font-semibold text-ink', fail: 'font-semibold text-fail', none: 'text-muted',
        }[verdict.state])}>{verdict.text}</span>
      </div>
      {raw != null
        ? <Raw prose={prose}>{raw}</Raw>
        : <div className="flex min-h-36 flex-col justify-center rounded-lg border border-dashed border-rule px-4 py-3.5 text-[15px] text-muted">
            <strong className="text-ink">{missing.title}</strong><span>{missing.detail}</span>
          </div>}
      {reason && <p className="mt-3 border-t border-rule pt-3 text-sm text-muted">{reason}</p>}
      {foot && <div className="mt-1.5 text-[13px] text-muted">{foot}</div>}
    </section>
  );
}

export function Evidence({ summary, open, children }: { summary: string; open?: boolean; children: ReactNode }) {
  return (
    <details open={open} className="mt-7 border-t border-rule pt-4">
      <summary className="cursor-pointer text-[15px] font-semibold text-form">{summary}</summary>
      <div className="mt-1">{children}</div>
    </details>
  );
}

export function Excerpt({ tag, text, title, url, detail }: { tag: string; text: string; title: string; url: string; detail?: string }) {
  return (
    <div className="grid grid-cols-[36px_minmax(0,1fr)] gap-2.5 pt-3.5 text-[15px]">
      <span className="font-num text-pass">{tag}</span>
      <div>
        <blockquote className="mb-1 leading-relaxed">{text}</blockquote>
        <SourceLink title={title} url={url} detail={detail} />
      </div>
    </div>
  );
}

export function SourceLink({ title, url, detail }: { title: string; url: string; detail?: string | null }) {
  return <p className="text-[13px]"><a href={url} target="_blank" rel="noopener noreferrer">{title}</a>{detail ? <span className="text-muted">, {detail}</span> : null}</p>;
}
