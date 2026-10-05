<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import Icon from './Icon.svelte';
  import { dragToClose } from '../lib/dragToClose';
  import { dur } from '../lib/motion';

  let { title, onclose, fallbackFocus, children }: {
    title: string; onclose: () => void; fallbackFocus?: () => HTMLElement | null; children: Snippet;
  } = $props();

  let el: HTMLDivElement | undefined = $state();

  onMount(() => {
    const previous = document.activeElement as HTMLElement | null;
    el?.focus();
    return () => (previous?.isConnected ? previous : fallbackFocus?.())?.focus?.();
  });

  function onkeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
      onclose();
      return;
    }
    if (e.key !== 'Tab' || !el) return;
    const focusable = [...el.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex="0"]')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === el)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

<svelte:window {onkeydown} />

<button class="backdrop" aria-label="Close" onclick={onclose} transition:fade={{ duration: dur(150) }}></button>
<div
  class="sheet"
  role="dialog"
  aria-modal="true"
  aria-label={title}
  tabindex="-1"
  bind:this={el}
  use:dragToClose={{ handle: '.grabber, .sheet-head', onclose }}
  transition:fly={{ y: 320, duration: dur(220) }}>
  <div class="grabber" aria-hidden="true"></div>
  <div class="sheet-head">
    <h2>{title}</h2>
    <button class="icon-btn" aria-label="Close" onclick={onclose}><Icon name="x" /></button>
  </div>
  {@render children()}
</div>

<style>
  /* Dragging here moves the sheet (dragToClose), not the page. */
  .grabber, .sheet-head { touch-action: none; }
  /* Padding enlarges the hit area; background-clip keeps the visible bar 5px. */
  .grabber {
    justify-self: center; box-sizing: content-box; width: 40px; height: 5px; padding: var(--space-2) 0;
    border-radius: var(--radius-pill); background: var(--color-surface-3); background-clip: content-box;
  }
  .sheet-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
</style>
