<script lang="ts">
  import { untrack } from 'svelte';
  import Icon from './Icon.svelte';
  import { actionsSummary } from '../lib/format';
  import { sceneIcon } from '../lib/icons';
  import { dur } from '../lib/motion';
  import { hestia, store } from '../lib/store.svelte';
  import type { Scene } from '../lib/types';

  let { scene, compact = false }: { scene: Scene; compact?: boolean } = $props();

  let ripples: { key: number; x: number; y: number }[] = $state([]);
  let done = $state(false);
  let nextKey = 0;

  function ripple(x: number, y: number): void {
    if (!dur(1)) return;
    const key = ++nextKey;
    ripples.push({ key, x, y });
    setTimeout(() => {
      ripples = ripples.filter((r) => r.key !== key);
    }, 650);
  }

  // Runs started elsewhere (another client, a schedule) ripple from the centre.
  // Start from the current counter so mounting doesn't replay an old ripple.
  let seen = untrack(() => hestia.ripple?.n ?? 0);
  $effect(() => {
    const r = hestia.ripple;
    if (!r || r.n === seen) return;
    seen = r.n;
    if (r.id === scene.id) ripple(50, 50);
  });

  async function run(e: MouseEvent): Promise<void> {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const fromPointer = e.detail > 0 && rect.width > 0;
    ripple(
      fromPointer ? ((e.clientX - rect.left) / rect.width) * 100 : 50,
      fromPointer ? ((e.clientY - rect.top) / rect.height) * 100 : 50,
    );
    if (await store.runScene(scene.id)) {
      done = true;
      setTimeout(() => (done = false), 900);
    }
  }
</script>

<button class="scene" class:tile={compact} class:card={!compact} onclick={run} aria-label="Run {scene.name}">
  {#each ripples as r (r.key)}
    <span class="ripple" style="left: {r.x}%; top: {r.y}%" aria-hidden="true"></span>
  {/each}
  <span class="scene-icon" class:done>
    <Icon name={done ? 'check' : sceneIcon(scene)} size={compact ? 32 : 24} />
  </span>
  <span class="name">{scene.name}</span>
  {#if !compact}<span class="muted sub">{actionsSummary(scene)}</span>{/if}
</button>

<style>
  .scene { position: relative; overflow: hidden; }
  .card.scene {
    grid-template-columns: auto 1fr; align-items: center; column-gap: var(--space-3); row-gap: 2px;
    min-height: 64px; transition: transform var(--transition-fast);
  }
  .card.scene:active { transform: scale(0.98); }
  .card .scene-icon { grid-row: 1 / span 2; }
  .card .name { font-weight: 600; }
  .scene-icon { position: relative; color: var(--color-accent); transition: transform 260ms var(--spring); }
  .scene-icon.done { transform: scale(1.15); }
  .sub { font-size: var(--text-xs); }
  .ripple {
    position: absolute; width: 24px; height: 24px; margin: -12px 0 0 -12px; border-radius: 50%;
    background: var(--color-accent); opacity: 0.35; transform: scale(0); pointer-events: none;
    animation: ripple 600ms ease-out forwards;
  }
  @keyframes ripple { to { transform: scale(14); opacity: 0; } }
</style>
