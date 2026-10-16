<script lang="ts">
	interface Part {
		key: string;
		label: string;
		value: number;
		color: string;
	}
	let { parts, unit }: { parts: Part[]; unit: (n: number) => string } = $props();
	const total = $derived(parts.reduce((s, p) => s + p.value, 0));
	const shown = $derived(parts.filter((p) => p.value > 0));
</script>

<div>
	<!-- 2px gaps between segments come from the flex gap on the card surface -->
	<div class="flex h-6 gap-0.5 overflow-hidden rounded-md" role="img" aria-label={shown.map((p) => `${p.label} ${unit(p.value)}`).join(', ')}>
		{#each shown as p (p.key)}
			<div class="h-full" style="flex:{p.value} 1 0;background:{p.color}" title="{p.label}: {unit(p.value)}"></div>
		{/each}
		{#if total === 0}<div class="h-full flex-1 bg-slate-100 dark:bg-slate-800"></div>{/if}
	</div>
	<ul class="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
		{#each parts as p (p.key)}
			<li class="flex items-center gap-2">
				<span class="size-2.5 rounded-sm" style="background:{p.color}"></span>
				<span>{p.label}</span>
				<span class="font-semibold tabular-nums">{unit(p.value)}</span>
				{#if total > 0}<span class="text-xs muted tabular-nums">{Math.round((p.value / total) * 100)} %</span>{/if}
			</li>
		{/each}
	</ul>
</div>
