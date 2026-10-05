<script lang="ts">
  import { onMount } from 'svelte';
  import BootBanner from './components/BootBanner.svelte';
  import ConnectionBanner from './components/ConnectionBanner.svelte';
  import FatalScreen from './components/FatalScreen.svelte';
  import Header from './components/Header.svelte';
  import NavPill from './components/NavPill.svelte';
  import Toasts from './components/Toast.svelte';
  import { startClock } from './lib/clock.svelte';
  import { live } from './lib/live.svelte';
  import { applyPrefs, isShown } from './lib/prefs.svelte';
  import { matchRoute, TITLES } from './lib/route';
  import { initRouter, navigate, router } from './lib/router.svelte';
  import { hestia, registerLiveHandlers, store } from './lib/store.svelte';
  import DevicesScreen from './screens/DevicesScreen.svelte';
  import HomeScreen from './screens/HomeScreen.svelte';
  import ScenesScreen from './screens/ScenesScreen.svelte';
  import SchedulesScreen from './screens/SchedulesScreen.svelte';
  import SettingsScreen from './screens/SettingsScreen.svelte';

  onMount(() => {
    applyPrefs();
    const stopRouter = initRouter();
    const stopClock = startClock();
    const stopLive = registerLiveHandlers();
    void store.loadAll();
    live.connect();
    const healthTimer = setInterval(() => void store.refreshHealth(), 60_000);
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      void store.refreshHealth();
      live.retryNow();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      document.removeEventListener('visibilitychange', onVisible);
      clearInterval(healthTimer);
      live.disconnect();
      stopLive();
      stopClock();
      stopRouter();
    };
  });

  // First load failed: keep retrying — a kiosk has nobody to tap Retry.
  $effect(() => {
    if (hestia.ready || !hestia.error) return;
    const timer = setInterval(() => void store.loadAll(), 5000);
    return () => clearInterval(timer);
  });

  const screen = $derived(matchRoute(router.route));
  const tab = $derived(screen?.kind ?? 'home');
  const screenKey = $derived(router.route.path.join('/'));

  $effect(() => {
    if (!screen) navigate(['home'], {}, { replace: true });
  });

  // A deep link to a device that doesn't exist drops the ?open=.
  $effect(() => {
    if (screen?.kind !== 'devices' || !screen.open || !hestia.ready) return;
    const id = screen.open;
    if (!hestia.devices.some((d) => d.id === id && isShown(id))) navigate(['devices'], {}, { replace: true });
  });
</script>

<Header title={TITLES[tab]} />
<ConnectionBanner />

<main class="screen">
  {#if !hestia.ready}
    {#if hestia.error}
      <FatalScreen message={hestia.error} onretry={() => void store.loadAll()} />
    {:else}
      <div class="center-state"><p class="muted">Loading…</p></div>
    {/if}
  {:else}
    <BootBanner />
    {#key screenKey}
      {#if screen?.kind === 'home'}
        <HomeScreen />
      {:else if screen?.kind === 'devices'}
        <DevicesScreen open={screen.open} />
      {:else if screen?.kind === 'scenes'}
        <ScenesScreen />
      {:else if screen?.kind === 'schedules'}
        <SchedulesScreen />
      {:else if screen?.kind === 'settings'}
        <SettingsScreen />
      {/if}
    {/key}
  {/if}
</main>

<NavPill active={tab} />
<Toasts />
