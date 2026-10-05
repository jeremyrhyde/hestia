<script lang="ts">
  import { fly } from 'svelte/transition';
  import { dur } from '../lib/motion';
  import { dismissToast, toasts } from '../lib/toast.svelte';
</script>

<div class="toasts" aria-live="polite">
  {#each toasts as t (t.id)}
    <div
      class="toast {t.kind}"
      class:actionable={t.action}
      role={t.kind === 'error' ? 'alert' : undefined}
      transition:fly={{ y: 16, duration: dur(180) }}>
      <span>{t.text}</span>
      {#if t.action}
        {@const action = t.action}
        <button class="toast-action" onclick={() => { action.run(); dismissToast(t.id); }}>{action.label}</button>
      {/if}
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed; left: 50%; transform: translateX(-50%); z-index: 40;
    /* Stack above the nav pill: pill offset + pill + gap. */
    bottom: calc(var(--space-3) + var(--pill-h) + var(--space-3) + var(--safe-bottom));
    display: grid; gap: var(--space-2); width: min(92vw, 420px); pointer-events: none;
  }
  .toast {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-3);
    padding: var(--space-3) var(--space-4); border-radius: var(--radius-md);
    background: var(--color-surface-3); box-shadow: var(--shadow-2); font-size: var(--text-sm);
  }
  .toast.actionable { pointer-events: auto; }
  .toast.error { background: var(--color-danger); color: var(--color-on-accent); }
  .toast-action {
    min-height: 32px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-sm);
    background: none; color: var(--color-accent); font-weight: 600; cursor: pointer;
  }
</style>
