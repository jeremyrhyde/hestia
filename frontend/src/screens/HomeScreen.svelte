<script lang="ts">
  import GlanceHeader from '../components/GlanceHeader.svelte';
  import LightTile from '../components/LightTile.svelte';
  import SceneCard from '../components/SceneCard.svelte';
  import ScheduleRow from '../components/ScheduleRow.svelte';
  import { isLight } from '../lib/icons';
  import { isShown } from '../lib/prefs.svelte';
  import { navigate } from '../lib/router.svelte';
  import { hestia, store } from '../lib/store.svelte';

  const lights = $derived(hestia.devices.filter((d) => isShown(d.id) && isLight(d)));
</script>

<GlanceHeader />

{#if lights.length}
  <section class="stack" aria-label="Lights">
    <h2 class="section-title">Lights</h2>
    <div class="tile-grid">
      {#each lights as device (device.id)}
        <LightTile
          {device}
          ontoggle={() => void store.toggle(device.id)}
          onlevel={(level, final) => store.setBrightness(device.id, level, { final })}
          onlongpress={() => navigate(['devices'], { open: device.id })} />
      {/each}
    </div>
  </section>
{/if}

{#if hestia.scenes.length}
  <section class="stack" aria-label="Scenes">
    <h2 class="section-title">Scenes</h2>
    <div class="tile-grid">
      {#each hestia.scenes as scene (scene.id)}
        <SceneCard {scene} compact />
      {/each}
    </div>
  </section>
{/if}

{#if hestia.schedules.length}
  <section class="stack" aria-label="Schedules">
    <h2 class="section-title">Schedules</h2>
    {#each hestia.schedules as schedule (schedule.id)}
      <ScheduleRow {schedule} />
    {/each}
  </section>
{/if}
