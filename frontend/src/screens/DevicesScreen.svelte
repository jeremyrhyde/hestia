<script lang="ts">
  import DeviceControls from '../components/DeviceControls.svelte';
  import DeviceSheet from '../components/DeviceSheet.svelte';
  import Icon from '../components/Icon.svelte';
  import Slider from '../components/Slider.svelte';
  import { mediaText } from '../lib/format';
  import { brightnessOf, deviceIcon, deviceSubtitle, isDimmable } from '../lib/icons';
  import { isShown } from '../lib/prefs.svelte';
  import { navigate } from '../lib/router.svelte';
  import { hestia, store } from '../lib/store.svelte';

  let { open }: { open?: string } = $props();
  const devices = $derived(hestia.devices.filter((d) => isShown(d.id)));
  const openDevice = $derived(open ? devices.find((d) => d.id === open) : undefined);
</script>

<section class="stack" aria-label="Devices">
  {#each devices as device (device.id)}
    <div class="device-row" data-device-id={device.id} class:on={device.state.power}>
      <button class="row-main" onclick={() => navigate(['devices'], { open: device.id }, { replace: true })}>
        <span class="row-icon"><Icon name={deviceIcon(device)} size={24} /></span>
        <span class="row-text">
          <span class="name">{device.name}</span>
          <span class="muted sub">{mediaText(device.state) || deviceSubtitle(device)}</span>
        </span>
      </button>
      <DeviceControls {device} />
      {#if isDimmable(device)}
        <div class="row-slider">
          <Slider
            value={brightnessOf(device) ?? 0}
            label="{device.name} brightness"
            oninput={(v) => store.setBrightness(device.id, v, { final: false })}
            onchange={(v) => store.setBrightness(device.id, v, { final: true })} />
        </div>
      {/if}
    </div>
  {:else}
    <p class="center-state muted">
      {hestia.devices.length ? 'Every device is hidden on this display. Show them in Settings.' : 'No devices registered. Add some to devices.yaml.'}
    </p>
  {/each}
</section>

{#if openDevice}
  {@const id = openDevice.id}
  <DeviceSheet
    device={openDevice}
    fallbackFocus={() => document.querySelector<HTMLElement>(`[data-device-id="${CSS.escape(id)}"] .row-main`)}
    onclose={() => navigate(['devices'], {}, { replace: true })} />
{/if}

<style>
  .device-row {
    display: grid; grid-template-columns: 1fr auto; align-items: center; gap: var(--space-2) var(--space-3);
    min-height: 72px; padding: var(--space-2) var(--space-4);
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg);
    transition: border-color var(--transition);
  }
  .device-row.on { border-color: var(--color-accent-dim); }
  .row-main {
    display: flex; align-items: center; gap: var(--space-3); min-height: var(--tap-min);
    padding: 0; border: 0; background: none; text-align: left; cursor: pointer;
  }
  .row-icon { color: var(--color-text-muted); transition: color var(--transition); }
  .device-row.on .row-icon { color: var(--color-accent); }
  .row-text { display: grid; gap: 2px; }
  .name { font-weight: 500; }
  .sub { font-size: var(--text-xs); }
  .row-slider { grid-column: 1 / -1; }
</style>
