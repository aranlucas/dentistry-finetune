import type { Tally } from './api';

export const pad = (n: number) => String(n).padStart(2, '0');
export const tally = (m?: Tally) => (m?.total ? `${m.count}/${m.total}` : 'Pending');
export const pct = (v: number | null | undefined) => (v == null ? '–' : String(Math.round(v * 100)));
export const mib = (bytes = 0) => `${(bytes / 1048576).toFixed(2)} MiB`;
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
