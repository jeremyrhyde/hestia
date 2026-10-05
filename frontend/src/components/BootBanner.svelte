<script lang="ts">
  import Icon from './Icon.svelte';
  import { isShown } from '../lib/prefs.svelte';
  import { hestia } from '../lib/store.svelte';

  // Failures hidden in Settings → Devices are known-down; don't nag about them.
  const failures = $derived((hestia.health?.devices_failed ?? []).filter((f) => isShown(f.id)));
</script>

{#if failures.length}
  <div class="banner warn boot" role="alert">
    <Icon name="alert" size={20} />
    <div>
      <strong>{failures.length} {failures.length === 1 ? 'device' : 'devices'} failed to register at startup</strong>
      <ul>
        {#each failures as f (f.id)}
          <li><code>{f.id}</code> — {f.error}</li>
        {/each}
      </ul>
    </div>
  </div>
{/if}

<style>
  .boot { display: flex; gap: var(--space-3); align-items: flex-start; }
  ul { margin: var(--space-1) 0 0; padding-left: var(--space-4); font-size: var(--text-sm); color: var(--color-text-muted); }
  code { font-family: var(--font-mono); color: var(--color-text); }
</style>
