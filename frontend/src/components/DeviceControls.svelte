<script lang="ts">
  import Icon from './Icon.svelte';
  import Switch from './Switch.svelte';
  import { hasCap } from '../lib/icons';
  import { store } from '../lib/store.svelte';
  import type { Device } from '../lib/types';

  let { device }: { device: Device } = $props();
  const playing = $derived(device.state.power);
</script>

{#if hasCap(device, 'media_control')}
  <button
    class="icon-btn media"
    aria-label={playing ? `Pause ${device.name}` : `Play ${device.name}`}
    onclick={(e) => { e.stopPropagation(); void (playing ? store.pause(device.id) : store.play(device.id)); }}>
    <Icon name={playing ? 'pause' : 'play'} size={24} />
  </button>
{:else if hasCap(device, 'toggle')}
  <Switch checked={device.state.power} label="{device.name} power" onchange={() => void store.toggle(device.id)} />
{/if}

<style>
  .media { color: var(--color-accent); background: var(--color-surface-2); border-radius: var(--radius-pill); }
</style>
