import { resolveMotion, type Motion } from './preferences';

/** Reduced motion: the Settings override (html[data-motion]) or the OS. */
export function motionReduced(): boolean {
  const attr = typeof document !== 'undefined' ? document.documentElement.dataset.motion : undefined;
  const pref: Motion = attr === 'full' || attr === 'reduced' ? attr : 'system';
  const os = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  return resolveMotion(pref, os);
}

/** Transition duration that collapses to 0 when motion is reduced. */
export function dur(ms: number): number {
  return motionReduced() ? 0 : ms;
}
