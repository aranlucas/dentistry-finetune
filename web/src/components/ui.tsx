import { cx } from "../class-names";
// Shared primitives so every sheet uses the same controls, type, and boxes.
import type {
  ButtonHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
  InputHTMLAttributes,
} from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { primary?: boolean };

type LabelProps = { htmlFor: string; children: ReactNode };

type H2Props = {
  id?: string;
  className?: string;
  children: ReactNode;
};

type H3Props = { className?: string; children: ReactNode };

type RawProps = {
  prose?: boolean;
  className?: string;
  children: ReactNode;
};

type MutedProps = {
  small?: boolean;
  className?: string;
  children: ReactNode;
};

const control = "rounded-lg border border-rule bg-well px-3 py-2 text-[15px] hover:border-form/50";

export function Button({ primary, className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "cursor-pointer rounded-full border px-4 py-2 text-sm disabled:cursor-default disabled:opacity-50",
        primary
          ? "border-ink bg-ink font-semibold text-sheet"
          : "border-rule bg-sheet enabled:hover:border-ink",
        className,
      )}
    />
  );
}

export const Select = ({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) => (
  <select {...props} className={cx(control, "max-w-full", className)} />
);

export const Search = ({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) => (
  <input type="search" autoComplete="off" {...props} className={cx(control, "w-full", className)} />
);

export const TextArea = ({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) => (
  <textarea
    {...props}
    className={cx(control, "block min-h-[84px] w-full resize-y text-base", className)}
  />
);

export const Label = ({ htmlFor, children }: LabelProps) => (
  <label htmlFor={htmlFor} className="mt-3.5 mb-1.5 block text-sm text-form">
    {children}
  </label>
);

export const H2 = ({ id, className, children }: H2Props) => (
  <h2 id={id} className={cx("mb-2 font-display text-[26px]/tight", className)}>
    {children}
  </h2>
);

export const H3 = ({ className, children }: H3Props) => (
  <h3 className={cx("mb-1.5 text-[15px] font-semibold", className)}>{children}</h3>
);

/** Raw model text in a recessed box: monospace for JSON answers, the reading face for prose answers. */
export const Raw = ({ prose, className, children }: RawProps) => (
  <pre
    className={cx(
      "m-0 max-h-96 min-h-36 overflow-auto rounded-lg border border-rule bg-well px-4 py-3.5 wrap-anywhere whitespace-pre-wrap",
      prose ? "font-sans text-base/relaxed" : "font-mono text-[13px]/relaxed",
      className,
    )}
  >
    {children}
  </pre>
);

export const Muted = ({ small, className, children }: MutedProps) => (
  <p className={cx("text-muted", small && "text-sm", className)}>{children}</p>
);
