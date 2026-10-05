import { afterEach, describe, expect, it, vi } from 'vitest';
import { dur, motionReduced } from './motion';

function env(attr: string | undefined, osReduced: boolean) {
  vi.stubGlobal('document', { documentElement: { dataset: attr ? { motion: attr } : {} } });
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce') && osReduced }));
}

afterEach(() => vi.unstubAllGlobals());

describe('dur', () => {
  it('follows the OS when there is no override', () => {
    env(undefined, false);
    expect(dur(200)).toBe(200);
    env(undefined, true);
    expect(dur(200)).toBe(0);
  });
  it('an explicit Reduced wins over an OS that allows motion', () => {
    env('reduced', false);
    expect(dur(200)).toBe(0);
    expect(motionReduced()).toBe(true);
  });
  it('an explicit Full wins over an OS that asks to reduce', () => {
    env('full', true);
    expect(dur(200)).toBe(200);
  });
  it('without a DOM (SSR/tests) it uses the duration', () => {
    expect(dur(150)).toBe(150);
  });
});
