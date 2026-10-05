<script lang="ts">
  import ConfirmSheet from './ConfirmSheet.svelte';
  import Icon from './Icon.svelte';
  import { clock } from '../lib/clock.svelte';
  import { formatClock, formatDate, formatTime, nextSchedule } from '../lib/format';
  import { isLight } from '../lib/icons';
  import { prefs } from '../lib/prefs.svelte';
  import { hestia, store } from '../lib/store.svelte';

  /** Ask before All off when at least this many lights are on. */
  const CONFIRM_AT = 4;

  const lightsOn = $derived(hestia.devices.filter((d) => isLight(d) && d.state.power).length);
  const next = $derived(nextSchedule(hestia.schedules, clock.now));
  let confirming = $state(false);

  function allOff(): void {
    if (prefs.confirmAllOff && lightsOn >= CONFIRM_AT) confirming = true;
    else void store.allOff();
  }
</script>

<section class="glance" aria-label="At a glance">
  <div class="when">
    <span class="time">{formatClock(clock.now, prefs.clock)}</span>
    <span class="muted date">{formatDate(clock.now)}</span>
  </div>
  <div class="chips">
    <span class="chip-lg" class:lit={lightsOn > 0}>
      <Icon name="lightbulb" size={16} />{lightsOn} {lightsOn === 1 ? 'light' : 'lights'} on
    </span>
    {#if next}
      <span class="chip-lg next"><Icon name="clock" size={16} /><span class="truncate">Next: {next.schedule.name} · {formatTime(next.schedule.time, prefs.clock)}</span></span>
    {/if}
  </div>
  <button class="btn" disabled={lightsOn === 0} onclick={allOff}><Icon name="power" size={18} />All off</button>
</section>

{#if confirming}
  <ConfirmSheet
    title="Turn off {lightsOn} lights?"
    confirmLabel="All off"
    danger
    onconfirm={() => { confirming = false; void store.allOff(); }}
    oncancel={() => (confirming = false)} />
{/if}

<style>
  .glance {
    display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: var(--space-4);
    max-height: 72px;
  }
  .when { display: grid; line-height: 1.1; }
  .time { font-size: var(--text-2xl); font-weight: 700; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
  .date { font-size: var(--text-sm); }
  /* One row in landscape so the header stays within its 72px cap; Next truncates. */
  .chips { display: flex; flex-wrap: nowrap; overflow: hidden; min-width: 0; gap: var(--space-2); }
  .chip-lg {
    display: inline-flex; align-items: center; gap: var(--space-1);
    padding: var(--space-1) var(--space-3); border-radius: var(--radius-pill);
    background: var(--color-surface-2); color: var(--color-text-muted); font-size: var(--text-sm);
    white-space: nowrap; flex-shrink: 0;
  }
  .chip-lg.next { flex-shrink: 1; min-width: 0; }
  .truncate { overflow: hidden; text-overflow: ellipsis; min-width: 0; }
  .chip-lg.lit { color: var(--color-lamp); background: var(--color-lamp-soft); }
  @media (orientation: portrait) {
    .glance { grid-template-columns: 1fr auto; max-height: none; }
    .chips { grid-column: 1 / -1; grid-row: 2; flex-wrap: wrap; }
  }
</style>
