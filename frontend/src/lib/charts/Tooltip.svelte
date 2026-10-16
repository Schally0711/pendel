<script lang="ts">
	import type { Snippet } from 'svelte';

	/** Positioned inside a relative container; x/y in container pixels. Flips to stay inside. */
	let { x, y, width, children }: { x: number; y: number; width: number; children: Snippet } = $props();
	const left = $derived(x > width / 2);
</script>

<div
	class="pointer-events-none absolute z-10 min-w-36 rounded-xl bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-900/10 dark:bg-slate-800 dark:ring-white/10"
	style="top:{Math.max(y - 8, 0)}px;{left ? `right:${width - x + 12}px` : `left:${x + 12}px`}"
>
	{@render children()}
</div>
