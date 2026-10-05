<script lang="ts">
  let { checked, label, onchange }: { checked: boolean; label: string; onchange: (value: boolean) => void } = $props();
</script>

<button
  class="switch"
  role="switch"
  aria-checked={checked}
  aria-label={label}
  onclick={(e) => { e.stopPropagation(); onchange(!checked); }}>
  <span class="knob"></span>
</button>

<style>
  .switch {
    position: relative; flex: none; width: 52px; height: 32px; padding: 0;
    border: 0; border-radius: var(--radius-pill); background: var(--color-surface-3); cursor: pointer;
    transition: background var(--transition);
  }
  /* 44px tap target around a 32px track. */
  .switch::before { content: ''; position: absolute; inset: -6px; }
  .knob {
    position: absolute; top: 3px; left: 3px; width: 26px; height: 26px; border-radius: 50%;
    background: var(--color-knob); box-shadow: var(--shadow-1);
    transition: transform 260ms var(--spring);
  }
  .switch[aria-checked='true'] { background: var(--color-accent); }
  .switch[aria-checked='true'] .knob { transform: translateX(20px); }
</style>
