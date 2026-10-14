import { forwardRef, useLayoutEffect, useRef, type ReactNode } from "react";
import { pad } from "../format";
import type { Glyph } from "./result-chart";
import { Button, H3, Raw } from "./ui";
import { cx } from "../class-names";

type PromptProps = { children: ReactNode };

type TargetProps = { title: string; answer: string; note: string };

type AnswersProps = { children: ReactNode };

type AnswerProps = {
  title: string;
  verdict: Verdict;
  raw?: string | null;
  prose?: boolean;
  missing: { title: string; detail: string };
  reason?: string;
  foot?: string;
};

type EvidenceProps = {
  summary: string;
  open?: boolean;
  children: ReactNode;
};

type ExcerptProps = {
  tag: string;
  text: string;
  title: string;
  url: string;
  detail?: string;
};

type SourceLinkProps = {
  title: string;
  url: string;
  detail?: string | null;
};

export type ListItem = { id: string; number: number; text: string; sub: string };

/** Read every answer: a filterable list of cases beside the selected case. */
type InspectorProps = {
  items: ListItem[];
  total: number;
  noun: string;
  selected?: string;
  onSelect: (id: string) => void;
  tools: ReactNode;
  heading: (item: ListItem) => string;
  children: ReactNode;
};

export const Inspector = forwardRef<HTMLElement, InspectorProps>(function Inspector(
  { items, total, noun, selected, onSelect, tools, heading, children },
  ref,
) {
  const index = items.findIndex((i) => i.id === selected);
  const current = items[index];
  const list = useRef<HTMLDivElement>(null);
  // Keep the selected case visible in the list without moving the page.
  useLayoutEffect(() => {
    const box = list.current;
    const item = box?.querySelector<HTMLElement>("[aria-current=true]");

    if (!box || !item) {
      return;
    }

    if (item.offsetTop < box.scrollTop) {
      box.scrollTop = item.offsetTop;
    } else if (item.offsetTop + item.offsetHeight > box.scrollTop + box.clientHeight) {
      box.scrollTop = item.offsetTop + item.offsetHeight - box.clientHeight;
    }
  }, [selected]);

  const empty = (
    <p className="p-3.5 text-sm text-muted">
      No {noun} match. Clear the filters to see all of them.
    </p>
  );

  return (
    <div className="grid min-h-inspector-floor overflow-hidden rounded-xl border border-rule bg-sheet md:grid-cols-inspector lg:grid-cols-inspector-wide">
      <aside className="flex min-h-0 flex-col border-be border-rule bg-well md:border-e md:border-be-0">
        <div className="grid gap-2 border-be border-rule p-3.5">
          {tools}
          <span className="text-caption text-muted">
            {items.length} of {total} {noun}
          </span>
        </div>
        <div ref={list} className="relative max-h-case-list overflow-auto md:max-h-chart-floor">
          {items.map((item) => (
            <button
              type="button"
              key={item.id}
              aria-current={item.id === selected}
              onClick={() => onSelect(item.id)}
              className="group grid w-full cursor-pointer grid-cols-result-row gap-x-2.5 gap-y-mark-line border-0 border-be border-grid bg-transparent px-3.5 py-3 text-start text-control/snug hover:bg-sheet/60 aria-current:bg-sheet aria-current:shadow-selected-row"
            >
              <span className="font-num text-muted tabular-nums group-aria-current:text-pass">
                {pad(item.number)}
              </span>
              <span className="line-clamp-2">{item.text || "(Empty)"}</span>
              <span className="col-start-2 truncate text-caption text-muted">{item.sub}</span>
            </button>
          ))}
          {!items.length && empty}
        </div>
      </aside>
      <article
        ref={ref}
        aria-live="polite"
        tabIndex={-1}
        className="min-w-0 scroll-mbs-4 p-detail-inset md:px-8 md:py-7"
      >
        {current ? (
          <>
            <div className="flex items-center justify-between gap-4 text-sm text-form">
              <span>{heading(current)}</span>
              <div className="flex gap-1.5">
                <Button disabled={index <= 0} onClick={() => onSelect(items[index - 1].id)}>
                  Previous
                </Button>
                <Button
                  disabled={index >= items.length - 1}
                  onClick={() => onSelect(items[index + 1].id)}
                >
                  Next
                </Button>
              </div>
            </div>
            {children}
          </>
        ) : (
          empty
        )}
      </article>
    </div>
  );
});

/** The case as the models saw it. */
export const Prompt = ({ children }: PromptProps) => (
  <p className="mbs-4 mbe-6 max-w-empty font-display text-question/relaxed-copy">{children}</p>
);

/** The frozen reference answer, marked in the charting blue. */
export function Target({ title, answer, note }: TargetProps) {
  return (
    <div className="mbe-7 border-s-3 border-pass py-1 ps-4">
      <H3 className="text-sm text-pass">{title}</H3>
      <p className="font-display text-lg/snug">{answer}</p>
      <small className="mbs-1 block text-caption text-muted">{note}</small>
    </div>
  );
}

export const Answers = ({ children }: AnswersProps) => (
  <div className="grid gap-6 inspector-wide:grid-cols-2">{children}</div>
);

export type Verdict = { state: Glyph; text: string };

/** One model's saved answer, its verdict, and how it was produced. */
export function Answer({ title, verdict, raw, prose, missing, reason, foot }: AnswerProps) {
  return (
    <section className="min-w-0">
      <div className="mbe-2 flex items-baseline justify-between gap-3">
        <H3 className="mbe-0">{title}</H3>
        <span
          className={cx(
            "text-sm",
            {
              pass: "font-semibold text-pass",
              partial: "font-semibold text-ink",
              fail: "font-semibold text-fail",
              none: "text-muted",
            }[verdict.state],
          )}
        >
          {verdict.text}
        </span>
      </div>
      {raw !== null && raw !== undefined ? (
        <Raw prose={prose}>{raw}</Raw>
      ) : (
        <div className="flex min-h-36 flex-col justify-center rounded-lg border border-dashed border-rule px-4 py-3.5 text-control text-muted">
          <strong className="text-ink">{missing.title}</strong>
          <span>{missing.detail}</span>
        </div>
      )}
      {reason && <p className="mbs-3 border-bs border-rule pbs-3 text-sm text-muted">{reason}</p>}
      {foot && <div className="mbs-1.5 text-caption text-muted">{foot}</div>}
    </section>
  );
}

export function Evidence({ summary, open, children }: EvidenceProps) {
  return (
    <details open={open} className="mbs-7 border-bs border-rule pbs-4">
      <summary className="cursor-pointer text-control font-semibold text-form">{summary}</summary>
      <div className="mbs-1">{children}</div>
    </details>
  );
}

export function Excerpt({ tag, text, title, url, detail }: ExcerptProps) {
  return (
    <div className="grid grid-cols-case-row gap-2.5 pbs-3.5 text-control">
      <span className="font-num text-pass">{tag}</span>
      <div>
        <blockquote className="mbe-1 leading-relaxed">{text}</blockquote>
        <SourceLink title={title} url={url} detail={detail} />
      </div>
    </div>
  );
}

export function SourceLink({ title, url, detail }: SourceLinkProps) {
  return (
    <p className="text-caption">
      <a href={url} target="_blank" rel="noopener noreferrer">
        {title}
      </a>
      {detail ? <span className="text-muted">, {detail}</span> : null}
    </p>
  );
}
