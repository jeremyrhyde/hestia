import { describe, expect, it } from 'vitest';
import { classify, glowOpacity, levelFromDrag, stepLevel } from './dim';

describe('classify', () => {
  it('stays pending inside the 8px slop (a tap or a long-press)', () => {
    expect(classify(3, 4, true)).toBe('pending');
    expect(classify(0, 7.9, true)).toBe('pending');
  });
  it('mostly-vertical movement on a dimmable tile is a drag', () => {
    expect(classify(2, -20, true)).toBe('drag');
    expect(classify(10, 16, true)).toBe('drag'); // 16 > 1.5 * 10
  });
  it('anything else is a scroll', () => {
    expect(classify(20, 5, true)).toBe('scroll');
    expect(classify(10, 14, true)).toBe('scroll'); // 14 < 15
    expect(classify(0, -30, false)).toBe('scroll'); // not dimmable
  });
});

describe('levelFromDrag', () => {
  it('dragging up brightens, down dims, by share of tile height', () => {
    expect(levelFromDrag(50, -46, 92)).toBe(100);
    expect(levelFromDrag(50, 23, 92)).toBe(25);
  });
  it('clamps to 0..100', () => {
    expect(levelFromDrag(90, -500, 92)).toBe(100);
    expect(levelFromDrag(10, 500, 92)).toBe(0);
  });
  it('ignores a zero-height tile', () => expect(levelFromDrag(40, 50, 0)).toBe(40));
});

describe('stepLevel', () => {
  it('moves 10% and clamps', () => {
    expect(stepLevel(40, 1)).toBe(50);
    expect(stepLevel(95, 1)).toBe(100);
    expect(stepLevel(5, -1)).toBe(0);
  });
});

describe('glowOpacity', () => {
  it('is 0 when off, 1 for non-dimmers, scaled for dimmers', () => {
    expect(glowOpacity(false, 80)).toBe(0);
    expect(glowOpacity(true, null)).toBe(1);
    expect(glowOpacity(true, 0)).toBeCloseTo(0.35);
    expect(glowOpacity(true, 100)).toBeCloseTo(1);
    expect(glowOpacity(true, 50)).toBeCloseTo(0.675);
  });
});
