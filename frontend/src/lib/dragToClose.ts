import { dur } from './motion';

/** Close once dragged past this share of the sheet's height… */
const DISTANCE_SHARE = 0.25;
/** …or at least this far (px), whichever is smaller… */
const DISTANCE_MIN = 80;
/** …or when released while flicking down faster than this (px per ms). */
const FLICK_SPEED = 0.5;

/** Whether a drag of `dy` px, released at `speed` px/ms, should dismiss a sheet `height` px tall. */
export function shouldDismiss(dy: number, speed: number, height: number): boolean {
  if (dy <= 0) return false;
  return dy >= Math.min(DISTANCE_MIN, height * DISTANCE_SHARE) || speed >= FLICK_SPEED;
}

interface Options {
  /** Where a drag may start (e.g. the grabber and header); defaults to the whole node. */
  handle?: string;
  onclose: () => void;
}

/**
 * Svelte action: drag the sheet down to close it. The sheet follows the
 * finger; on release it either closes (`onclose`, whose outro continues from
 * the dragged position) or springs back. Drags don't start on form controls
 * or buttons, so typing and tapping inside the handle area still work.
 */
export function dragToClose(node: HTMLElement, options: Options) {
  let opts = options;
  let pointerId: number | null = null;
  let startY = 0;
  let dy = 0;
  let lastY = 0;
  let lastT = 0;
  let speed = 0;

  function onDown(e: PointerEvent) {
    if (pointerId !== null || (e.pointerType === 'mouse' && e.button !== 0)) return;
    const target = e.target as Element;
    if (target.closest('input, textarea, select, button, a')) return;
    if (opts.handle && !target.closest(opts.handle)) return;
    pointerId = e.pointerId;
    startY = lastY = e.clientY;
    lastT = e.timeStamp;
    dy = speed = 0;
    node.setPointerCapture(e.pointerId);
    node.style.transition = 'none';
  }

  function onMove(e: PointerEvent) {
    if (e.pointerId !== pointerId) return;
    dy = Math.max(0, e.clientY - startY);
    const dt = e.timeStamp - lastT;
    if (dt > 0) speed = (e.clientY - lastY) / dt;
    lastY = e.clientY;
    lastT = e.timeStamp;
    node.style.transform = dy ? `translateY(${dy}px)` : '';
  }

  function onUp(e: PointerEvent) {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
    const close = e.type === 'pointerup' && shouldDismiss(dy, speed, node.offsetHeight);
    if (close) {
      opts.onclose();
      return;
    }
    const ms = dur(180);
    node.style.transition = ms ? `transform ${ms}ms ease-out` : '';
    node.style.transform = '';
  }

  node.addEventListener('pointerdown', onDown);
  node.addEventListener('pointermove', onMove);
  node.addEventListener('pointerup', onUp);
  node.addEventListener('pointercancel', onUp);

  return {
    update(next: Options) {
      opts = next;
    },
    destroy() {
      node.removeEventListener('pointerdown', onDown);
      node.removeEventListener('pointermove', onMove);
      node.removeEventListener('pointerup', onUp);
      node.removeEventListener('pointercancel', onUp);
    },
  };
}
