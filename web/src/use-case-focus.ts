import { useRef, useState } from "react";
import { reducedMotion } from "./format";

/** The selected case, shared by the chart and the inspector. Choosing a mark on the chart opens it below. */
export function useCaseFocus() {
  const [selected, setSelected] = useState<string>();
  const inspectorRef = useRef<HTMLElement>(null);

  const open = (id: string) => {
    setSelected(id);
    // Scroll after React has rendered the newly selected case.
    requestAnimationFrame(() => {
      const box = inspectorRef.current;

      if (!box) {
        return;
      }

      box.focus({ preventScroll: true });
      window.scrollTo({
        top: box.getBoundingClientRect().top + window.scrollY - 16,
        behavior: reducedMotion() ? "auto" : "smooth",
      });
    });
  };

  return { selected, setSelected, inspectorRef, open };
}

interface IdentifiedCase {
  id: string;
}

/** Keep the selection inside the visible list. */
export const within = <T extends IdentifiedCase>(items: T[], id: string | undefined) =>
  items.some((i) => i.id === id) ? id : items[0]?.id;
