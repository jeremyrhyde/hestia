<script lang="ts">
  import Switch from './Switch.svelte';
  import { formatDays, formatTime } from '../lib/format';
  import { prefs } from '../lib/prefs.svelte';
  import { hestia, store } from '../lib/store.svelte';
  import type { Schedule } from '../lib/types';

  let { schedule }: { schedule: Schedule } = $props();
  const sceneName = $derived(hestia.scenes.find((s) => s.id === schedule.scene_id)?.name ?? schedule.scene_id);
</script>

<div class="schedule-row" class:off={!schedule.enabled}>
  <span class="time">{formatTime(schedule.time, prefs.clock)}</span>
  <span class="what">
    <span class="name">{schedule.name}</span>
    <span class="muted sub">{formatDays(schedule.days)} · {sceneName}</span>
  </span>
  <Switch
    checked={schedule.enabled}
    label="{schedule.name} enabled"
    onchange={(enabled) => void store.setScheduleEnabled(schedule.id, enabled)} />
</div>

<style>
  .schedule-row {
    display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--space-4);
    min-height: 64px; padding: var(--space-2) var(--space-4);
    background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-lg);
    transition: opacity var(--transition);
  }
  .schedule-row.off { opacity: 0.6; }
  .time { min-width: 5.5ch; font-size: var(--text-lg); font-weight: 600; font-variant-numeric: tabular-nums; }
  .what { display: grid; gap: 2px; }
  .name { font-weight: 500; }
  .sub { font-size: var(--text-xs); }
</style>
