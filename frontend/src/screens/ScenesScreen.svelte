<script lang="ts">
  import SceneCard from '../components/SceneCard.svelte';
  import { hestia } from '../lib/store.svelte';
</script>

{#if hestia.scenes.length}
  <div class="scene-grid">
    {#each hestia.scenes as scene (scene.id)}
      <SceneCard {scene} />
    {/each}
  </div>
{:else}
  <p class="center-state muted">No scenes yet. Create them with <code>make seed</code> or the API.</p>
{/if}

<style>
  .scene-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
</style>
