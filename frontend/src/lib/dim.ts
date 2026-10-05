// Light-tile gestures: tap toggles, a mostly-vertical drag dims, a long
// press opens the device sheet. Pure math here; LightTile.svelte wires it.

/** Movement (px) below which a press is still a tap or long-press. */
export const MOVE_SLOP = 8;
/** Held this long without moving → long-press. */
export const LONG_PRESS_MS = 500;
/** Arrow keys change brightness by this much. */
export const KEY_STEP = 10;

export type Gesture = 'pending' | 'drag' | 'scroll';

export function classify(dx: number, dy: number, dimmable: boolean): Gesture {
  if (Math.hypot(dx, dy) < MOVE_SLOP) return 'pending';
  return dimmable && Math.abs(dy) > 1.5 * Math.abs(dx) ? 'drag' : 'scroll';
}

export function clampLevel(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

/** Dragging the full tile height changes brightness by 100 (up = brighter). */
export function levelFromDrag(startLevel: number, dy: number, height: number): number {
  if (height <= 0) return clampLevel(startLevel);
  return clampLevel(startLevel - (dy / height) * 100);
}

export function stepLevel(level: number, direction: 1 | -1): number {
  return clampLevel(level + direction * KEY_STEP);
}

/** Lamp-glow opacity: 0 off; full for on/off lights; 0.35..1 by brightness. */
export function glowOpacity(on: boolean, level: number | null): number {
  if (!on) return 0;
  if (level === null) return 1;
  return 0.35 + 0.65 * (clampLevel(level) / 100);
}
