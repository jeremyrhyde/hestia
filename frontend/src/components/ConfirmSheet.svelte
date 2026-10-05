<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  import { dur } from '../lib/motion';

  interface Props {
    title: string;
    confirmLabel: string;
    danger?: boolean;
    busy?: boolean;
    onconfirm: () => void;
    oncancel: () => void;
    children?: Snippet;
  }

  let { title, confirmLabel, danger = false, busy = false, onconfirm, oncancel, children }: Props = $props();

  let sheetEl: HTMLDivElement | undefined = $state();

  onMount(() => {
    const previous = document.activeElement as HTMLElement | null;
    sheetEl?.focus();
    return () => {
      if (previous?.isConnected) previous.focus?.();
    };
  });

  function onkeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      oncancel();
      return;
    }
    if (e.key !== 'Tab' || !sheetEl) return;
    const focusable = [...sheetEl.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex="0"]')];
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === sheetEl)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

<svelte:window {onkeydown} />

<button class="backdrop" aria-label="Close" onclick={oncancel} transition:fade={{ duration: dur(150) }}></button>
<div
  class="sheet"
  role="dialog"
  aria-modal="true"
  aria-label={title}
  tabindex="-1"
  bind:this={sheetEl}
  transition:fly={{ y: 320, duration: dur(220) }}
>
  <h2>{title}</h2>
  {@render children?.()}
  <div class="sheet-actions">
    <button class="btn" onclick={oncancel}>Cancel</button>
    <button class="btn {danger ? 'danger' : 'primary'}" disabled={busy} onclick={onconfirm}>{confirmLabel}</button>
  </div>
</div>
