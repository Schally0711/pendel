<script lang="ts">
	import type { Snippet } from 'svelte';
	import Tooltip from './Tooltip.svelte';
	import { linear } from './scale.js';

	/** Working window per day: a floating bar from first start to last end (minutes after midnight). */
	interface Window {
		key: string;
		label: string;
		start: number | null;
		end: number | null;
		color: string;
	}

	let {
		days,
		label,
		avgStart,
		avgEnd,
		avgLabels,
		tooltip,
		height = 240
	}: {
		days: Window[];
		label: string;
		avgStart: number | null;
		avgEnd: number | null;
		avgLabels: [string, string];
		tooltip: Snippet<[Window]>;
		height?: number;
	} = $props();

	let width = $state(600);
	const pad = { top: 12, right: 64, bottom: 26, left: 44 };
	const withData = $derived(days.filter((d) => d.start !== null && d.end !== null));
	const lo = $derived(Math.floor(Math.min(7 * 60, ...withData.map((d) => d.start!)) / 60) * 60);
	const hi = $derived(Math.ceil(Math.max(18 * 60, ...withData.map((d) => d.end!)) / 60) * 60);
	// earlier times at the top, like a calendar
	const sy = $derived(linear(lo, hi, pad.top, height - pad.bottom));
	const band = $derived((width - pad.left - pad.right) / Math.max(days.length, 1));
	const bar = $derived(Math.max(3, Math.min(14, band * 0.6)));
	const cx = (i: number) => pad.left + band * (i + 0.5);
	const hours = $derived.by(() => {
		const step = hi - lo > 10 * 60 ? 120 : 60;
		const out = [];
		for (let t = lo; t <= hi; t += step) out.push(t);
		return out;
	});
	const labelEvery = $derived(Math.max(1, Math.ceil(days.length / Math.max(2, Math.floor(width / 48)))));
	const hm = (m: number) => `${Math.floor(m / 60)}:${String(Math.round(m % 60)).padStart(2, '0')}`;
	let hover = $state<number | null>(null);
</script>

<div class="relative w-full min-w-0" bind:clientWidth={width}>
	<svg {width} {height} role="img" aria-label={label} class="block w-full" onpointerleave={() => (hover = null)}>
		{#each hours as t (t)}
			<line x1={pad.left} x2={width - pad.right} y1={sy(t)} y2={sy(t)} stroke="var(--c-grid)" stroke-width="1" />
			<text x={pad.left - 8} y={sy(t)} dy="0.32em" text-anchor="end" class="fill-slate-500 text-[11px] tabular-nums dark:fill-slate-400">{hm(t)}</text>
		{/each}
		{#each [[avgStart, avgLabels[0]], [avgEnd, avgLabels[1]]] as [v, text], k (k)}
			{#if v !== null}
				<line x1={pad.left} x2={width - pad.right} y1={sy(v as number)} y2={sy(v as number)} class="stroke-slate-500 dark:stroke-slate-400" stroke-width="1" />
				<text x={width - pad.right + 6} y={sy(v as number)} dy="0.32em" class="fill-slate-600 text-[11px] dark:fill-slate-300">{text} {hm(v as number)}</text>
			{/if}
		{/each}
		{#each days as d, i (d.key)}
			<rect x={cx(i) - band / 2} y={pad.top} width={band} height={height - pad.top - pad.bottom} fill={hover === i ? 'var(--c-grid)' : 'transparent'} opacity="0.5" role="presentation" onpointerenter={() => (hover = i)} onpointerdown={() => (hover = i)} />
			{#if d.start !== null && d.end !== null}
				<rect x={cx(i) - bar / 2} y={sy(d.start)} width={bar} height={Math.max(2, sy(d.end) - sy(d.start))} rx={Math.min(4, bar / 2)} fill={d.color} class="pointer-events-none" />
			{/if}
			{#if i % labelEvery === 0}
				<text x={cx(i)} y={height - 6} text-anchor="middle" class="pointer-events-none fill-slate-500 text-[11px] dark:fill-slate-400">{d.label}</text>
			{/if}
		{/each}
	</svg>
	{#if hover !== null}
		<Tooltip x={cx(hover)} y={days[hover].start !== null ? sy(days[hover].start!) : pad.top} {width}>{@render tooltip(days[hover])}</Tooltip>
	{/if}
</div>
