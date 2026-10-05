<script lang="ts">
  import ScheduleRow from '../components/ScheduleRow.svelte';
  import { hestia } from '../lib/store.svelte';
</script>

{#if hestia.schedules.length}
  <section class="stack" aria-label="Schedules">
    {#each hestia.schedules as schedule (schedule.id)}
      <ScheduleRow {schedule} />
    {/each}
  </section>
{:else}
  <p class="center-state muted">No schedules yet. Create them with <code>make seed</code> or the API.</p>
{/if}
