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

const control = "rounded-lg border border-rule bg-well px-3 py-2 text-control hover:border-form/50";

export function Button({ primary, className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "cursor-pointer rounded-full border px-4 py-2 text-sm disabled:cursor-default disabled:opacity-50",
        primary
          ? "border-ink bg-ink font-semibold text-sheet"
          : "border-rule bg-sheet hover:enabled:border-ink",
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
    className={cx(control, "block min-h-input-floor w-full resize-y text-base", className)}
  />
);

export const Label = ({ htmlFor, children }: LabelProps) => (
  <label htmlFor={htmlFor} className="mbs-3.5 mbe-1.5 block text-sm text-form">
    {children}
  </label>
);

export const H2 = ({ id, className, children }: H2Props) => (
  <h2 id={id} className={cx("mbe-2 font-display text-stat/tight", className)}>
    {children}
  </h2>
);

export const H3 = ({ className, children }: H3Props) => (
  <h3 className={cx("mbe-1.5 text-control font-semibold", className)}>{children}</h3>
);

/** Raw model text in a recessed box: monospace for JSON answers, the reading face for prose answers. */
export const Raw = ({ prose, className, children }: RawProps) => (
  <pre
    className={cx(
      "m-0 max-h-96 min-h-36 overflow-auto rounded-lg border border-rule bg-well px-4 py-3.5 wrap-anywhere whitespace-pre-wrap",
      prose ? "font-sans text-base/relaxed" : "font-mono text-caption/relaxed",
      className,
    )}
  >
    {children}
  </pre>
);
