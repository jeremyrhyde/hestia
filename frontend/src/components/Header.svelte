<script lang="ts">
  import { clock } from '../lib/clock.svelte';
  import { formatClock } from '../lib/format';
  import { connection } from '../lib/live.svelte';
  import { prefs } from '../lib/prefs.svelte';

  let { title }: { title: string } = $props();
  const open = $derived(connection.status === 'open');
</script>

<header class="header">
  <span class="mark" aria-hidden="true">H</span>
  <h1>{title}</h1>
  <span class="clock">{formatClock(clock.now, prefs.clock)}</span>
  <span
    class="live"
    class:open
    role="status"
    title={open ? 'Live updates on' : 'Live updates paused — reconnecting'}
    aria-label={open ? 'Live updates on' : 'Live updates paused'}></span>
</header>

<style>
  .header {
    position: sticky; top: 0; z-index: 20;
    display: flex; align-items: center; gap: var(--space-3);
    height: calc(var(--header-h) + var(--safe-top));
    padding: var(--safe-top) calc(var(--space-4) + var(--safe-right)) 0 calc(var(--space-4) + var(--safe-left));
    background: var(--color-bg); border-bottom: 1px solid var(--color-border-soft);
    view-transition-name: header;
  }
  .mark {
    display: grid; place-items: center; width: 28px; height: 28px; border-radius: var(--radius-sm);
    background: var(--color-accent-soft); color: var(--color-accent); font-weight: 700;
  }
  h1 { flex: 1; font-size: var(--text-lg); font-weight: 600; }
  .clock { font-variant-numeric: tabular-nums; color: var(--color-text-muted); font-weight: 500; }
  .live {
    width: 10px; height: 10px; border-radius: var(--radius-pill);
    background: var(--color-warn); animation: pulse 1.2s ease-in-out infinite;
  }
  .live.open { background: var(--color-accent); animation: none; }
  @keyframes pulse { 50% { opacity: 0.35; } }
</style>
