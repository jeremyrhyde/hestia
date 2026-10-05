<script lang="ts">
  let { value, label, oninput, onchange }: {
    value: number;
    label: string;
    oninput: (value: number) => void;
    onchange: (value: number) => void;
  } = $props();
</script>

<div class="slider" style="--pct: {value}%">
  <input
    type="range" min="0" max="100" step="1" {value} aria-label={label}
    oninput={(e) => oninput(Number(e.currentTarget.value))}
    onchange={(e) => onchange(Number(e.currentTarget.value))}
    onclick={(e) => e.stopPropagation()} />
  <span class="readout" aria-hidden="true">{value}%</span>
</div>

<style>
  .slider { display: flex; align-items: center; gap: var(--space-3); width: 100%; }
  input {
    flex: 1; height: var(--tap-min); margin: 0; background: none; cursor: pointer;
    -webkit-appearance: none; appearance: none;
  }
  input::-webkit-slider-runnable-track {
    height: 12px; border-radius: var(--radius-pill);
    background: linear-gradient(to right, var(--color-accent) 0 var(--pct), var(--color-surface-3) var(--pct) 100%);
  }
  input::-moz-range-track { height: 12px; border-radius: var(--radius-pill); background: var(--color-surface-3); }
  input::-moz-range-progress { height: 12px; border-radius: var(--radius-pill); background: var(--color-accent); }
  input::-webkit-slider-thumb {
    -webkit-appearance: none; width: 28px; height: 28px; margin-top: -8px; border-radius: 50%;
    background: var(--color-knob); box-shadow: var(--shadow-2); border: 0;
  }
  input::-moz-range-thumb { width: 28px; height: 28px; border-radius: 50%; background: var(--color-knob); border: 0; box-shadow: var(--shadow-2); }
  .readout { min-width: 3.5ch; text-align: right; font-variant-numeric: tabular-nums; color: var(--color-text-muted); font-size: var(--text-sm); }
</style>
