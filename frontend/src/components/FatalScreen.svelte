<script lang="ts">
  import Icon from './Icon.svelte';

  let { message, onretry }: { message: string; onretry: () => void } = $props();
</script>

<div class="center-state" role="alert">
  <Icon name="wifi-off" size={40} />
  <h2>Can't reach Hestia</h2>
  {#if message !== "Can't reach Hestia"}<p class="muted">{message}</p>{/if}
  <p class="muted">Retrying automatically…</p>
  <button class="btn primary" onclick={onretry}>Retry now</button>
</div>
