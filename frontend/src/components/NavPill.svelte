<script lang="ts">
  import Icon from './Icon.svelte';
  import { dur } from '../lib/motion';
  import { tabDirection, type Tab } from '../lib/route';
  import { navigate, router } from '../lib/router.svelte';

  let { active }: { active: Tab } = $props();

  const ITEMS: { key: Tab; label: string; icon: string }[] = [
    { key: 'home', label: 'Home', icon: 'home' },
    { key: 'devices', label: 'Devices', icon: 'plug' },
    { key: 'scenes', label: 'Scenes', icon: 'sparkles' },
    { key: 'schedules', label: 'Schedules', icon: 'clock' },
    { key: 'settings', label: 'Settings', icon: 'sliders' },
  ];

  const activeIndex = $derived(ITEMS.findIndex((i) => i.key === active));

  function select(key: Tab): void {
    const alreadyOnTab = key === active;
    const atRoot = router.route.path.length === 1 && Object.keys(router.route.query).length === 0;
    // Apollo's TabBar logic: at the tab's root, re-tapping scrolls to top;
    // from a subroute (an open sheet), it resets to the root in place.
    if (alreadyOnTab && atRoot) {
      scrollTo({ top: 0, behavior: dur(1) ? 'smooth' : 'auto' });
      return;
    }
    navigate([key], {}, { replace: alreadyOnTab, direction: tabDirection(active, key) });
  }
</script>

<nav class="pill" aria-label="Sections" style="--count: {ITEMS.length}; --active: {activeIndex}">
  <span class="indicator" aria-hidden="true"></span>
  {#each ITEMS as item (item.key)}
    <button
      class:active={item.key === active}
      aria-current={item.key === active ? 'page' : undefined}
      aria-label={item.label}
      onclick={() => select(item.key)}>
      <Icon name={item.icon} size={22} />
      <span class="label">{item.label}</span>
    </button>
  {/each}
</nav>

<style>
  .pill {
    --item: 72px;
    position: fixed; left: 50%; bottom: calc(var(--space-3) + var(--safe-bottom)); z-index: 20;
    transform: translateX(-50%);
    display: grid; grid-template-columns: repeat(var(--count), var(--item));
    height: var(--pill-h); padding: 4px;
    background: var(--color-surface); border: 1px solid var(--color-border);
    border-radius: var(--radius-pill); box-shadow: var(--shadow-2);
    view-transition-name: navpill;
  }
  .indicator {
    position: absolute; top: 4px; bottom: 4px; left: 4px; width: var(--item);
    border-radius: var(--radius-pill); background: var(--color-accent-soft);
    transform: translateX(calc(var(--active) * var(--item)));
    transition: transform var(--nav-duration) var(--spring);
  }
  button {
    position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px;
    min-height: var(--tap-min); border: 0; border-radius: var(--radius-pill);
    background: none; color: var(--color-text-muted); font-size: var(--text-xs); cursor: pointer;
    transition: color var(--transition-fast);
  }
  button.active { color: var(--color-accent); }
  @media (max-width: 420px) {
    .pill { --item: 56px; }
    .label { display: none; }
  }
</style>
