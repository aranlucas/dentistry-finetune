import { useRef, useState } from 'react';
import { reducedMotion } from './format';

/** The selected case, shared by the chart and the inspector. Choosing a mark on the chart opens it below. */
export function useCaseFocus() {
  const [selected, setSelected] = useState<string>();
  const inspector = useRef<HTMLElement>(null);
  const open = (id: string) => {
    setSelected(id);
    // Scroll after React has rendered the newly selected case.
    requestAnimationFrame(() => {
      const box = inspector.current;
      if (!box) return;
      box.focus({ preventScroll: true });
      window.scrollTo({ top: box.getBoundingClientRect().top + window.scrollY - 16, behavior: reducedMotion() ? 'auto' : 'smooth' });
    });
  };
  return { selected, setSelected, inspector, open };
}

/** Keep the selection inside the visible list. */
export const within = <T extends { id: string }>(items: T[], id: string | undefined) =>
  items.some(i => i.id === id) ? id : items[0]?.id;
