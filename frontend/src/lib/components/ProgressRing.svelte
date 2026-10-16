<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		value,
		max,
		color = 'var(--color-brand-500)',
		children
	}: { value: number; max: number; color?: string; children: Snippet } = $props();

	const R = 88;
	const C = 2 * Math.PI * R;
	const ratio = $derived(max > 0 ? Math.min(value / max, 1) : value > 0 ? 1 : 0);
	const over = $derived(max > 0 && value > max);
</script>

<div class="relative aspect-square w-full max-w-64">
	<svg viewBox="0 0 200 200" class="size-full -rotate-90">
		<circle cx="100" cy="100" r={R} fill="none" stroke-width="14" class="stroke-slate-200 dark:stroke-slate-800" />
		<circle
			cx="100"
			cy="100"
			r={R}
			fill="none"
			stroke-width="14"
			stroke-linecap="round"
			stroke={over ? 'var(--color-emerald-500)' : color}
			stroke-dasharray={C}
			stroke-dashoffset={C * (1 - ratio)}
			class="transition-[stroke-dashoffset] duration-700 ease-out"
		/>
	</svg>
	<div class="absolute inset-0 flex flex-col items-center justify-center text-center">
		{@render children()}
	</div>
</div>
