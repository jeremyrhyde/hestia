import { describe, expect, it } from 'vitest';
import { buildHash, matchRoute, parseHash, tabDirection } from './route';

describe('parseHash / buildHash', () => {
  it('defaults to home', () => {
    expect(parseHash('')).toEqual({ path: ['home'], query: {} });
    expect(parseHash('#/')).toEqual({ path: ['home'], query: {} });
  });

  it('round-trips a path and query', () => {
    const hash = buildHash(['devices'], { open: 'kasa one' });
    expect(hash).toBe('#/devices?open=kasa+one');
    expect(parseHash(hash)).toEqual({ path: ['devices'], query: { open: 'kasa one' } });
  });

  it('drops empty query values', () => {
    expect(buildHash(['scenes'], { open: undefined, x: '' })).toBe('#/scenes');
  });
});

describe('matchRoute', () => {
  it('matches each tab', () => {
    for (const tab of ['home', 'devices', 'scenes', 'schedules', 'settings'] as const) {
      expect(matchRoute({ path: [tab], query: {} })).toEqual({ kind: tab });
    }
  });

  it('carries the open device id on devices', () => {
    expect(matchRoute({ path: ['devices'], query: { open: 'lamp' } })).toEqual({ kind: 'devices', open: 'lamp' });
  });

  it('returns null for unknown tabs and extra segments (caller redirects home)', () => {
    expect(matchRoute({ path: ['nope'], query: {} })).toBeNull();
    expect(matchRoute({ path: ['devices', 'lamp'], query: {} })).toBeNull();
  });
});

describe('tabDirection', () => {
  it('follows tab order', () => {
    expect(tabDirection('home', 'scenes')).toBe('forward');
    expect(tabDirection('settings', 'devices')).toBe('back');
  });
});
