<script lang="ts">
	import type { Component } from 'svelte';

	let {
		label,
		value,
		sub = '',
		icon: Icon,
		tone = 'neutral'
	}: {
		label: string;
		value: string;
		sub?: string;
		icon: Component<{ class?: string }>;
		tone?: 'neutral' | 'positive' | 'negative';
	} = $props();
</script>

<div class="card flex items-start gap-3 p-4">
	<div class="rounded-xl bg-brand-50 p-2 text-brand-600 dark:bg-brand-900/40 dark:text-brand-400">
		<Icon class="size-5" />
	</div>
	<div class="min-w-0">
		<div class="text-xs font-medium muted">{label}</div>
		<div
			class="text-xl font-semibold tracking-tight {tone === 'positive'
				? 'text-emerald-600 dark:text-emerald-400'
				: tone === 'negative'
					? 'text-rose-600 dark:text-rose-400'
					: ''}"
		>
			{value}
		</div>
		{#if sub}<div class="truncate text-xs muted">{sub}</div>{/if}
	</div>
</div>
