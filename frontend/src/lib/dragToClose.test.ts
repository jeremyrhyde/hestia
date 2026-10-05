import { describe, expect, it } from 'vitest';
import { shouldDismiss } from './dragToClose';

describe('shouldDismiss', () => {
  it('closes past 80 px or a quarter of the sheet, whichever is smaller', () => {
    expect(shouldDismiss(80, 0, 700)).toBe(true);
    expect(shouldDismiss(79, 0, 700)).toBe(false);
    expect(shouldDismiss(50, 0, 200)).toBe(true); // 25% of 200 = 50
    expect(shouldDismiss(49, 0, 200)).toBe(false);
  });

  it('closes on a quick downward flick even when short', () => {
    expect(shouldDismiss(20, 0.6, 700)).toBe(true);
    expect(shouldDismiss(20, 0.4, 700)).toBe(false);
  });

  it('never closes without a downward drag', () => {
    expect(shouldDismiss(0, 2, 700)).toBe(false);
    expect(shouldDismiss(-30, 2, 700)).toBe(false);
  });
});
