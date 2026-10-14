import { Link, Outlet } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

type SheetProps = {
  title: string;
  footer: ReactNode;
  children: ReactNode;
};

const sheets = [
  { to: "/", title: "Sentence completion", note: "Extract and cite from excerpts" },
  { to: "/qa", title: "Dental Q&A", note: "Answer without excerpts" },
  { to: "/development", title: "Reviewed answers", note: "Graded by an assistant" },
] as const;

const gutter = "px-4 md:px-8 lg:px-12";

/** The chart folder: index tabs on the left (on top on phones), the open experiment as a sheet beside them. */
export function Folder() {
  return (
    <div className="mx-auto grid min-h-screen max-w-page-limit grid-cols-1 grid-rows-folder md:grid-cols-folder md:grid-rows-folder-wide lg:grid-cols-folder-wide">
      <header className="flex flex-col gap-4 self-start px-4 pbs-5 md:sticky md:inset-bs-0 md:row-span-2 md:h-screen md:gap-8 md:py-7 md:ps-5 md:pe-0">
        <Link
          to="/"
          className="flex items-center gap-2.5 pe-4 font-display text-lg/tight text-balance text-ink no-underline"
        >
          <svg
            viewBox="0 0 22 24"
            aria-hidden="true"
            className="h-6 w-section-inset flex-none text-form"
          >
            <path
              d="M3.5 2.8c2-1.9 5-1.2 7.5.1 2.5-1.3 5.5-2 7.5-.1 2 2 1.8 6 .8 9-1 3-1 6-2 9.2-.5 1.5-2 1.5-2.5 0l-1.6-5.2c-.3-1-1.6-1-2 0l-1.6 5.2c-.5 1.5-2 1.5-2.5 0-1-3.2-1-6.2-2-9.2s-1.2-7 .4-9z"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinejoin="round"
            />
          </svg>
          Oral-board study lab
        </Link>
        <nav
          aria-label="Experiments"
          className="-mx-4 flex gap-1 overflow-x-auto px-4 md:mx-0 md:flex-col md:gap-1.5 md:overflow-visible md:px-0"
        >
          {sheets.map((s) => (
            <Link
              key={s.to}
              to={s.to}
              activeOptions={{ exact: true, includeSearch: false }}
              className="relative block flex-none rounded-t-tab border border-be-0 border-rule bg-tab px-3.5 py-2.5 text-control/snug text-muted no-underline hover:text-ink md:rounded-s-tab md:rounded-se-none md:border-e-0 md:border-be md:py-3 md:ps-detail-inset md:pe-4"
              activeProps={{
                "aria-current": "page",
                className: "z-10 -mb-px bg-sheet! font-semibold text-ink! md:mb-0 md:-mr-px",
              }}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-2.5 -inset-bs-px h-mark-line rounded-b-sm bg-form md:inset-y-2.5 md:-inset-s-px md:inset-e-auto md:h-auto md:w-mark-line md:rounded-e-sm md:rounded-es-none"
                    />
                  )}
                  {s.title}
                  <span className="mbs-0.5 hidden text-caption font-normal text-muted md:block">
                    {s.note}
                  </span>
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
export function Sheet({ title, footer, children }: SheetProps) {
  useEffect(() => {
    document.title = `${title} · Oral-board study lab`;
  }, [title]);

  return (
    <>
      <main
        className={`min-w-0 border-bs border-rule bg-sheet pbs-2 md:border-s md:border-bs-0 ${gutter}`}
      >
        {children}
      </main>
      <footer
        className={`border-bs border-rule bg-sheet pbs-7 pbe-11 text-sm text-pretty text-muted md:border-s ${gutter}`}
      >
        <p className="max-w-footer">{footer}</p>
      </footer>
    </>
  );
}
