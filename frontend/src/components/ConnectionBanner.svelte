<script lang="ts">
  import { slide } from 'svelte/transition';
  import Icon from './Icon.svelte';
  import { connection } from '../lib/live.svelte';
  import { dur } from '../lib/motion';
</script>

<!-- Controls stay enabled: device actions are plain REST calls and return the
     new state, so they work without the socket. Only live updates pause. -->
{#if connection.status === 'reconnecting'}
  <div class="conn" role="status" transition:slide={{ duration: dur(180) }}>
    <Icon name="wifi-off" size={18} />
    <span>Live updates paused — reconnecting…</span>
  </div>
{/if}

<style>
  .conn {
    display: flex; align-items: center; justify-content: center; gap: var(--space-2);
    padding: var(--space-2) var(--space-4); background: var(--color-warn-soft);
    border-bottom: 1px solid var(--color-warn); color: var(--color-text); font-size: var(--text-sm);
  }
</style>
