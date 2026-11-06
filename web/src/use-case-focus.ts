import { useRef, useState } from "react";
import { reducedMotion } from "./format";

export function useCaseFocus() {
  const [selected, setSelected] = useState<string>();
  const inspectorRef = useRef<HTMLElement>(null);

  const open = (id: string) => {
    setSelected(id);
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

export const within = <T extends IdentifiedCase>(items: T[], id: string | undefined) =>
  items.some((i) => i.id === id) ? id : items[0]?.id;
