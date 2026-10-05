import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PREFS, STORAGE_KEY, loadPrefs, parsePrefs, resolveMotion, resolveMotionAttr,
  resolveThemeAttr, savePrefs, type StorageLike,
} from './preferences';

function memory(initial: Record<string, string> = {}): StorageLike & { data: Record<string, string> } {
  const data = { ...initial };
  return { data, getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
}

const throwing: StorageLike = {
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('blocked'); },
};

describe('parsePrefs', () => {
  it('defaults: dark, 12h, comfortable, follow OS motion, confirm All off', () => {
    expect(parsePrefs(null)).toEqual({ theme: 'dark', clock: '12h', density: 'comfortable', motion: 'system', confirmAllOff: true });
    expect(DEFAULT_PREFS.theme).toBe('dark');
  });
  it('keeps valid values and drops unknown ones', () => {
    expect(parsePrefs(JSON.stringify({ theme: 'light', clock: '24h', density: 'nope', motion: 'reduced', confirmAllOff: false, extra: 1 })))
      .toEqual({ theme: 'light', clock: '24h', density: 'comfortable', motion: 'reduced', confirmAllOff: false });
  });
  it('corrupt JSON or non-objects give defaults', () => {
    expect(parsePrefs('{not json')).toEqual(DEFAULT_PREFS);
    expect(parsePrefs('[1,2]')).toEqual(DEFAULT_PREFS);
    expect(parsePrefs('"light"')).toEqual(DEFAULT_PREFS);
  });
});

describe('load / save', () => {
  it('round-trips through storage', () => {
    const store = memory();
    savePrefs(store, { ...DEFAULT_PREFS, theme: 'auto' });
    expect(JSON.parse(store.data[STORAGE_KEY]).theme).toBe('auto');
    expect(loadPrefs(store).theme).toBe('auto');
  });
  it('a throwing or missing storage never throws', () => {
    expect(loadPrefs(throwing)).toEqual(DEFAULT_PREFS);
    expect(loadPrefs(null)).toEqual(DEFAULT_PREFS);
    expect(() => savePrefs(throwing, DEFAULT_PREFS)).not.toThrow();
  });
});

describe('resolution', () => {
  it('theme attribute: auto removes it', () => {
    expect(resolveThemeAttr('dark')).toBe('dark');
    expect(resolveThemeAttr('light')).toBe('light');
    expect(resolveThemeAttr('auto')).toBeNull();
  });
  it('motion attribute: follow OS removes it', () => {
    expect(resolveMotionAttr('system')).toBeNull();
    expect(resolveMotionAttr('full')).toBe('full');
    expect(resolveMotionAttr('reduced')).toBe('reduced');
  });
  it('resolveMotion truth table (true = reduced)', () => {
    expect(resolveMotion('system', false)).toBe(false);
    expect(resolveMotion('system', true)).toBe(true);
    expect(resolveMotion('full', true)).toBe(false);
    expect(resolveMotion('reduced', false)).toBe(true);
  });
});
