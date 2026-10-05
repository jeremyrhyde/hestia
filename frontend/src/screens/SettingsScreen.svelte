<script lang="ts">
  import Segmented from '../components/Segmented.svelte';
  import Switch from '../components/Switch.svelte';
  import type { ClockMode } from '../lib/format';
  import { connection } from '../lib/live.svelte';
  import type { Density, Motion, Theme } from '../lib/preferences';
  import { prefs, setPref } from '../lib/prefs.svelte';
  import { hestia, store } from '../lib/store.svelte';

  const THEMES: { value: Theme; label: string }[] = [
    { value: 'dark', label: 'Dark' },
    { value: 'light', label: 'Light' },
    { value: 'auto', label: 'Auto' },
  ];
  const CLOCKS: { value: ClockMode; label: string }[] = [
    { value: '12h', label: '12-hour' },
    { value: '24h', label: '24-hour' },
  ];
  const DENSITIES: { value: Density; label: string }[] = [
    { value: 'comfortable', label: 'Comfortable' },
    { value: 'compact', label: 'Compact' },
  ];
  const MOTIONS: { value: Motion; label: string }[] = [
    { value: 'system', label: 'Follow system' },
    { value: 'full', label: 'Full' },
    { value: 'reduced', label: 'Reduced' },
  ];

  const failed = $derived(hestia.health?.devices_failed ?? []);
  let reloading = $state(false);

  async function reload(): Promise<void> {
    reloading = true;
    await Promise.all([store.loadAll(), store.refreshHealth()]);
    reloading = false;
  }
</script>

<section class="stack" aria-label="Display">
  <h2 class="section-title">Display</h2>
  <div class="card settings">
    <div class="setting"><span>Theme</span>
      <Segmented label="Theme" options={THEMES} value={prefs.theme} onchange={(v) => setPref('theme', v)} /></div>
    <div class="setting"><span>Clock</span>
      <Segmented label="Clock" options={CLOCKS} value={prefs.clock} onchange={(v) => setPref('clock', v)} /></div>
    <div class="setting"><span>Tile density</span>
      <Segmented label="Tile density" options={DENSITIES} value={prefs.density} onchange={(v) => setPref('density', v)} /></div>
    <div class="setting"><span>Motion</span>
      <Segmented label="Motion" options={MOTIONS} value={prefs.motion} onchange={(v) => setPref('motion', v)} /></div>
    <div class="setting"><span>Confirm “All off”</span>
      <Switch checked={prefs.confirmAllOff} label="Confirm All off" onchange={(v) => setPref('confirmAllOff', v)} /></div>
  </div>
  <p class="muted note">These settings are saved on this device only.</p>
</section>

<section class="stack" aria-label="About">
  <h2 class="section-title">About</h2>
  <div class="card">
    <dl class="about">
      <dt>Version</dt><dd>{__APP_VERSION__}</dd>
      <dt>Live updates</dt><dd>{connection.status === 'open' ? 'Connected' : 'Reconnecting…'}</dd>
      <dt>Devices</dt><dd>{hestia.devices.length}</dd>
      <dt>Scenes</dt><dd>{hestia.scenes.length}</dd>
      <dt>Schedules</dt><dd>{hestia.schedules.length}</dd>
      <dt>Failed at boot</dt><dd>{failed.length ? failed.map((f) => f.id).join(', ') : 'None'}</dd>
    </dl>
    <button class="btn" disabled={reloading} onclick={reload}>{reloading ? 'Reloading…' : 'Reload data'}</button>
  </div>
</section>

<style>
  .settings { gap: 0; padding: 0 var(--space-4); }
  .setting {
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-2) var(--space-4);
    min-height: 64px; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-soft);
  }
  .setting:last-child { border-bottom: 0; }
  .note { font-size: var(--text-xs); }
  .about { display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-4); margin: 0; font-size: var(--text-sm); }
  .about dt { color: var(--color-text-muted); }
  .about dd { margin: 0; }
</style>
