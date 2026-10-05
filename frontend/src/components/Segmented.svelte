<script lang="ts" generics="T extends string">
  let { label, options, value, onchange }: {
    label: string;
    options: readonly { value: T; label: string }[];
    value: T;
    onchange: (value: T) => void;
  } = $props();
</script>

<div class="segmented" role="radiogroup" aria-label={label}>
  {#each options as option (option.value)}
    <button
      role="radio"
      aria-checked={option.value === value}
      class:on={option.value === value}
      onclick={() => onchange(option.value)}>{option.label}</button>
  {/each}
</div>
