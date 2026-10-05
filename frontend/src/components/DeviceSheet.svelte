<script lang="ts">
  import DeviceControls from './DeviceControls.svelte';
  import Sheet from './Sheet.svelte';
  import Slider from './Slider.svelte';
  import { mediaText } from '../lib/format';
  import { brightnessOf, deviceSubtitle, isDimmable } from '../lib/icons';
  import { store } from '../lib/store.svelte';
  import type { Device } from '../lib/types';

  let { device, onclose }: { device: Device; onclose: () => void } = $props();
  const now = $derived(mediaText(device.state));
</script>

<Sheet title={device.name} {onclose}>
  <div class="primary">
    <span class="muted">{device.state.power ? 'On' : 'Off'}{now ? ` · ${now}` : ''}</span>
    <DeviceControls {device} />
  </div>
  {#if isDimmable(device)}
    <Slider
      value={brightnessOf(device) ?? 0}
      label="{device.name} brightness"
      oninput={(v) => store.setBrightness(device.id, v, { final: false })}
      onchange={(v) => store.setBrightness(device.id, v, { final: true })} />
  {/if}
  <dl class="details">
    <dt>Type</dt><dd>{deviceSubtitle(device)}</dd>
    <dt>ID</dt><dd><code>{device.id}</code></dd>
    <dt>Capabilities</dt><dd>{device.capabilities.join(', ') || '—'}</dd>
    {#each Object.entries(device.state.attributes) as [key, value] (key)}
      <dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd>
    {/each}
  </dl>
</Sheet>

<style>
  .primary { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  .details {
    display: grid; grid-template-columns: auto 1fr; gap: var(--space-1) var(--space-4); margin: 0;
    font-size: var(--text-sm);
  }
  dt { color: var(--color-text-muted); }
  dd { margin: 0; overflow-wrap: anywhere; }
  code { font-family: var(--font-mono); }
</style>
