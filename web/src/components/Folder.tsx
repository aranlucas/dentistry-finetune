import { Link, Outlet } from '@tanstack/react-router';
import { useEffect, type ReactNode } from 'react';

const sheets = [
  { to: '/', title: 'Sentence completion', note: 'Extract and cite from excerpts' },
  { to: '/qa', title: 'Dental Q&A', note: 'Answer without excerpts' },
  { to: '/development', title: 'Reviewed answers', note: 'Graded by an assistant' },
] as const;

const gutter = 'px-4 md:px-8 lg:px-12';

/** The chart folder: index tabs on the left (on top on phones), the open experiment as a sheet beside them. */
export function Folder() {
  return (
    <div className="mx-auto grid min-h-screen max-w-[1440px] grid-cols-[minmax(0,1fr)] grid-rows-[auto_1fr_auto] md:grid-cols-[216px_minmax(0,1fr)] md:grid-rows-[1fr_auto] lg:grid-cols-[232px_minmax(0,1fr)]">
      <header className="flex flex-col gap-4 self-start px-4 pt-5 md:sticky md:top-0 md:row-span-2 md:h-screen md:gap-8 md:py-7 md:pr-0 md:pl-5">
        <Link to="/" className="flex items-center gap-2.5 pr-4 font-display text-lg/tight text-balance text-ink no-underline">
          <svg viewBox="0 0 22 24" aria-hidden="true" className="h-6 w-[22px] flex-none text-form">
            <path d="M3.5 2.8c2-1.9 5-1.2 7.5.1 2.5-1.3 5.5-2 7.5-.1 2 2 1.8 6 .8 9-1 3-1 6-2 9.2-.5 1.5-2 1.5-2.5 0l-1.6-5.2c-.3-1-1.6-1-2 0l-1.6 5.2c-.5 1.5-2 1.5-2.5 0-1-3.2-1-6.2-2-9.2s-1.2-7 .4-9z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
          Oral-board study lab
        </Link>
        <nav aria-label="Experiments" className="-mx-4 flex gap-1 overflow-x-auto px-4 md:mx-0 md:flex-col md:gap-1.5 md:overflow-visible md:px-0">
          {sheets.map(s => (
            <Link key={s.to} to={s.to} activeOptions={{ exact: true, includeSearch: false }}
                  className="relative block flex-none rounded-t-[10px] border border-b-0 border-rule bg-[color-mix(in_srgb,var(--color-sheet)_45%,var(--color-paper))] px-3.5 py-2.5 text-[15px]/snug text-muted no-underline hover:text-ink md:rounded-l-[10px] md:rounded-tr-none md:border-r-0 md:border-b md:py-3 md:pr-4 md:pl-[18px]"
                  activeProps={{ 'aria-current': 'page', className: 'z-10 -mb-px bg-sheet! font-semibold text-ink! md:mb-0 md:-mr-px' }}>
              {({ isActive }) => (
                <>
                  {isActive && <span aria-hidden="true" className="absolute -top-px right-2.5 left-2.5 h-[3px] rounded-b-sm bg-form md:top-2.5 md:right-auto md:bottom-2.5 md:-left-px md:h-auto md:w-[3px] md:rounded-r-sm md:rounded-bl-none" />}
                  {s.title}
                  <span className="mt-0.5 hidden text-[13px] font-normal text-muted md:block">{s.note}</span>
                </>
              )}
            </Link>
          ))}
        </nav>
      </header>
      <Outlet />
    </div>
  );
}

/** One sheet: its content and its own footnote. */
export function Sheet({ title, footer, children }: { title: string; footer: ReactNode; children: ReactNode }) {
  useEffect(() => { document.title = `${title} · Oral-board study lab`; }, [title]);
  return (
    <>
      <main className={`min-w-0 border-t border-rule bg-sheet pt-2 md:border-t-0 md:border-l ${gutter}`}>{children}</main>
      <footer className={`border-t border-rule bg-sheet pt-7 pb-11 text-sm text-pretty text-muted md:border-l ${gutter}`}>
        <p className="max-w-[90ch]">{footer}</p>
      </footer>
    </>
  );
}
