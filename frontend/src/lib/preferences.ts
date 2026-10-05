// Device-local display preferences. Pure: parsing, persistence and how each
// value maps onto <html> data-* attributes. prefs.svelte.ts holds the state;
// index.html's inline script mirrors loadPrefs + the attribute mapping.

import type { ClockMode } from './format';

export type Theme = 'dark' | 'light' | 'auto';
export type Density = 'comfortable' | 'compact';
export type Motion = 'system' | 'full' | 'reduced';

export interface Prefs {
  theme: Theme;
  clock: ClockMode;
  density: Density;
  motion: Motion;
  confirmAllOff: boolean;
}

export const STORAGE_KEY = 'hestia.prefs.v1';

export const DEFAULT_PREFS: Prefs = {
  theme: 'dark',
  clock: '12h',
  density: 'comfortable',
  motion: 'system',
  confirmAllOff: true,
};

const THEMES: readonly Theme[] = ['dark', 'light', 'auto'];
const CLOCKS: readonly ClockMode[] = ['12h', '24h'];
const DENSITIES: readonly Density[] = ['comfortable', 'compact'];
const MOTIONS: readonly Motion[] = ['system', 'full', 'reduced'];

function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === 'string' && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

export function parsePrefs(raw: string | null): Prefs {
  let obj: Record<string, unknown> = {};
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) obj = parsed as Record<string, unknown>;
  } catch {
    // Corrupt JSON: fall back to defaults.
  }
  return {
    theme: pick(obj.theme, THEMES, DEFAULT_PREFS.theme),
    clock: pick(obj.clock, CLOCKS, DEFAULT_PREFS.clock),
    density: pick(obj.density, DENSITIES, DEFAULT_PREFS.density),
    motion: pick(obj.motion, MOTIONS, DEFAULT_PREFS.motion),
    confirmAllOff: typeof obj.confirmAllOff === 'boolean' ? obj.confirmAllOff : DEFAULT_PREFS.confirmAllOff,
  };
}

export type StorageLike = Pick<Storage, 'getItem' | 'setItem'>;

export function loadPrefs(storage: StorageLike | null): Prefs {
  try {
    return parsePrefs(storage?.getItem(STORAGE_KEY) ?? null);
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(storage: StorageLike | null, prefs: Prefs): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Storage blocked (private mode): prefs last for this session only.
  }
}

export function resolveThemeAttr(theme: Theme): 'dark' | 'light' | null {
  return theme === 'auto' ? null : theme;
}

export function resolveMotionAttr(motion: Motion): 'full' | 'reduced' | null {
  return motion === 'system' ? null : motion;
}

/** True when motion should be reduced. */
export function resolveMotion(motion: Motion, osReduced: boolean): boolean {
  return motion === 'reduced' || (motion === 'system' && osReduced);
}
