<script lang="ts">
  import Icon from './Icon.svelte';
  import { classify, glowOpacity, levelFromDrag, LONG_PRESS_MS, stepLevel, type Gesture } from '../lib/dim';
  import { brightnessOf, isDimmable } from '../lib/icons';
  import type { Device } from '../lib/types';

  let { device, ontoggle, onlevel, onlongpress }: {
    device: Device;
    ontoggle: () => void;
    onlevel: (level: number, final: boolean) => void;
    onlongpress: () => void;
  } = $props();

  const on = $derived(device.state.power);
  const dimmable = $derived(isDimmable(device));
  const level = $derived(brightnessOf(device));
  let dragLevel: number | null = $state(null);
  const shown = $derived(dragLevel ?? level);
  const showLevel = $derived(dimmable && (on || dragLevel !== null));
  const glow = $derived(glowOpacity(on || dragLevel !== null, shown));

  let el: HTMLButtonElement | undefined = $state();
  let pointerId: number | null = null;
  let startX = 0;
  let startY = 0;
  let startLevel = 0;
  let gesture: Gesture = 'pending';
  let pressTimer: ReturnType<typeof setTimeout> | null = null;
  let suppressClick = false;

  function clearPress(): void {
    if (pressTimer) clearTimeout(pressTimer);
    pressTimer = null;
  }
  // Teardown runs on destroy: a stale long-press must not navigate later.
  $effect(() => clearPress);

  function onpointerdown(e: PointerEvent): void {
    if (pointerId !== null || (e.pointerType === 'mouse' && e.button !== 0)) return;
    pointerId = e.pointerId;
    startX = e.clientX;
    startY = e.clientY;
    startLevel = on ? (level ?? 100) : 0;
    gesture = 'pending';
    suppressClick = false;
    // Capture now (touch already has implicit capture) so a mouse released
    // outside the tile still ends the gesture instead of leaving it stuck.
    el?.setPointerCapture(e.pointerId);
    clearPress();
    pressTimer = setTimeout(() => {
      pressTimer = null;
      if (gesture !== 'pending') return;
      suppressClick = true;
      navigator.vibrate?.(10);
      onlongpress();
    }, LONG_PRESS_MS);
  }

  function onpointermove(e: PointerEvent): void {
    if (e.pointerId !== pointerId || !el) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    if (gesture === 'pending') {
      gesture = classify(dx, dy, dimmable);
      if (gesture === 'pending') return;
      clearPress();
      suppressClick = true;
    }
    if (gesture === 'drag') {
      e.preventDefault();
      dragLevel = levelFromDrag(startLevel, dy, el.offsetHeight);
      onlevel(dragLevel, false);
    }
  }

  function onpointerend(e: PointerEvent): void {
    if (e.pointerId !== pointerId) return;
    pointerId = null;
    clearPress();
    if (gesture === 'drag' && dragLevel !== null) onlevel(dragLevel, true);
    dragLevel = null;
    gesture = 'pending';
  }

  function onclick(e: MouseEvent): void {
    // Taps arrive as click after pointerup and are skipped after a drag or
    // long-press. Keyboard Enter/Space (detail 0) always toggles.
    const suppressed = suppressClick && e.detail !== 0;
    suppressClick = false;
    if (!suppressed) ontoggle();
  }

  function onkeydown(e: KeyboardEvent): void {
    if (!dimmable || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    e.preventDefault();
    onlevel(stepLevel(level ?? 0, e.key === 'ArrowUp' ? 1 : -1), true);
  }
</script>

<button
  bind:this={el}
  class="tile light"
  class:on
  style="--glow: {glow}; --level: {(shown ?? 0) / 100}; touch-action: {dimmable ? 'pan-x' : 'manipulation'}"
  aria-pressed={on}
  aria-label="{device.name}{showLevel && shown !== null ? `, ${shown}%` : ''}"
  {onpointerdown}
  {onpointermove}
  onpointerup={onpointerend}
  onpointercancel={onpointerend}
  onlostpointercapture={onpointerend}
  {onclick}
  {onkeydown}
  oncontextmenu={(e) => e.preventDefault()}>
  {#if showLevel}<span class="fill" aria-hidden="true"></span>{/if}
  <span class="halo" aria-hidden="true"></span>
  <span class="icon"><Icon name="lightbulb" size={32} /></span>
  <span class="name">{device.name}</span>
  {#if showLevel && shown !== null}<span class="pct">{shown}%</span>{/if}
</button>

<style>
  .light.on { color: var(--color-text); border-color: var(--color-lamp); }
  .fill {
    position: absolute; inset: 0; background: var(--color-lamp-soft);
    transform-origin: bottom; transform: scaleY(var(--level));
    transition: transform var(--transition-fast);
  }
  .halo {
    position: absolute; inset: 0;
    background: radial-gradient(circle at 50% 38%, var(--color-lamp) 0, transparent 62%);
    opacity: calc(var(--glow) * 0.45);
    transition: opacity var(--transition);
  }
  .icon { position: relative; transition: transform 260ms var(--spring), color var(--transition); }
  .light.on .icon { color: var(--color-lamp); transform: scale(1.06); }
  .pct { position: relative; font-size: var(--text-xs); color: var(--color-text-muted); font-variant-numeric: tabular-nums; }
</style>
