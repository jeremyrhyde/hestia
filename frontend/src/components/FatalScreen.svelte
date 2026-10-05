<script lang="ts">
  import Icon from './Icon.svelte';

  let { message, onretry }: { message: string; onretry: () => void } = $props();
</script>

<div class="center-state">
  <Icon name="wifi-off" size={40} />
  <!-- The alert wraps only the text, so the Retry button isn't read as part of it. -->
  <div role="alert" class="stack">
    <h2>Can't reach Hestia</h2>
    {#if message !== "Can't reach Hestia"}<p class="muted">{message}</p>{/if}
    <p class="muted">Retrying automatically…</p>
  </div>
  <button class="btn primary" onclick={onretry}>Retry now</button>
</div>

<style>
  /* Match .center-state's spacing so the layout is unchanged. */
  .stack { gap: var(--space-4); justify-items: center; }
</style>
