import {
  loadPrefs, resolveMotionAttr, resolveThemeAttr, savePrefs, type Prefs, type StorageLike,
} from './preferences';

// Browser chrome colour per theme (must be literal colours, not CSS vars).
const THEME_COLOR = { dark: '#0d1117', light: '#f6f8fa' } as const;

function storage(): StorageLike | null {
  try {
    return localStorage;
  } catch {
    return null;
  }
}

export const prefs: Prefs = $state(loadPrefs(storage()));

export function setPref<K extends keyof Prefs>(key: K, value: Prefs[K]): void {
  prefs[key] = value;
  savePrefs(storage(), $state.snapshot(prefs));
  applyPrefs();
}

/** Reflect prefs onto <html> (tokens.css / app.css key off these). */
export function applyPrefs(): void {
  const root = document.documentElement;
  const theme = resolveThemeAttr(prefs.theme);
  if (theme) root.dataset.theme = theme;
  else delete root.dataset.theme;
  const motion = resolveMotionAttr(prefs.motion);
  if (motion) root.dataset.motion = motion;
  else delete root.dataset.motion;
  if (prefs.density === 'compact') root.dataset.density = 'compact';
  else delete root.dataset.density;
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    const scheme = meta.media.includes('light') ? 'light' : 'dark';
    meta.content = THEME_COLOR[theme ?? scheme];
  }
}
