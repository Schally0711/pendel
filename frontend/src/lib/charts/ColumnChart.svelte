<script lang="ts">
	import type { Snippet } from 'svelte';
	import Tooltip from './Tooltip.svelte';
	import { hourTicks, linear } from './scale.js';

	interface Column {
		key: string;
		label: string;
		value: number | null; // minutes
		target?: number | null; // minutes, drawn as a tick
	}

	let {
		columns,
		label,
		color = 'var(--c-line)',
		tooltip,
		valueLabels = false,
		height = 220
	}: {
		columns: Column[];
		label: string;
		color?: string;
		tooltip: Snippet<[Column]>;
		valueLabels?: boolean;
		height?: number;
	} = $props();

	let width = $state(600);
	const pad = { top: 16, right: 8, bottom: 26, left: 44 };
	const max = $derived(Math.max(60, ...columns.flatMap((c) => [c.value ?? 0, c.target ?? 0])));
	const ticks = $derived(hourTicks(0, max, 4));
	const sy = $derived(linear(0, ticks[ticks.length - 1], height - pad.bottom, pad.top));
	const band = $derived((width - pad.left - pad.right) / Math.max(columns.length, 1));
	const bar = $derived(Math.min(24, band * 0.6));
	const cx = (i: number) => pad.left + band * (i + 0.5);
	const labelEvery = $derived(Math.max(1, Math.ceil(columns.length / Math.max(2, Math.floor(width / 48)))));

	/** Column with 4px rounded top, square at the baseline. */
	function colPath(x: number, w: number, y0: number, y1: number): string {
		const r = Math.min(4, w / 2, y0 - y1);
		return `M${x},${y0}V${y1 + r}Q${x},${y1} ${x + r},${y1}H${x + w - r}Q${x + w},${y1} ${x + w},${y1 + r}V${y0}Z`;
	}

	let hover = $state<number | null>(null);
	const fmt = (m: number) => `${Math.floor(m / 60)}:${String(Math.round(m % 60)).padStart(2, '0')}`;
</script>

<div class="relative w-full min-w-0" bind:clientWidth={width}>
	<svg {width} {height} role="img" aria-label={label} class="block w-full" onpointerleave={() => (hover = null)}>
		{#each ticks as t (t)}
			<line x1={pad.left} x2={width - pad.right} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? 'var(--c-axis)' : 'var(--c-grid)'} stroke-width="1" />
			<text x={pad.left - 8} y={sy(t)} dy="0.32em" text-anchor="end" class="fill-slate-500 text-[11px] tabular-nums dark:fill-slate-400">
				{(t / 60).toLocaleString()} h
			</text>
		{/each}
		{#each columns as c, i (c.key)}
			{@const x = cx(i) - bar / 2}
			<!-- hit target: the whole band, taller than the mark -->
			<rect
				x={cx(i) - band / 2}
				y={pad.top}
				width={band}
				height={height - pad.top - pad.bottom}
				fill={hover === i ? 'var(--c-grid)' : 'transparent'}
				opacity="0.5"
				role="presentation"
				onpointerenter={() => (hover = i)}
				onpointerdown={() => (hover = i)}
			/>
			{#if c.value && c.value > 0}
				<path d={colPath(x, bar, sy(0), sy(c.value))} fill={color} class="pointer-events-none" />
				{#if valueLabels}
					<text x={cx(i)} y={sy(c.value) - 5} text-anchor="middle" class="pointer-events-none fill-slate-600 text-[11px] font-medium tabular-nums dark:fill-slate-300">
						{fmt(c.value)}
					</text>
				{/if}
			{/if}
			{#if c.target}
				<line x1={x - 3} x2={x + bar + 3} y1={sy(c.target)} y2={sy(c.target)} class="pointer-events-none stroke-slate-700 dark:stroke-slate-200" stroke-width="2" stroke-linecap="round" />
			{/if}
			{#if i % labelEvery === 0}
				<text x={cx(i)} y={height - 6} text-anchor="middle" class="pointer-events-none fill-slate-500 text-[11px] dark:fill-slate-400">{c.label}</text>
			{/if}
		{/each}
	</svg>
	{#if hover !== null}
		<Tooltip x={cx(hover)} y={sy(Math.max(columns[hover].value ?? 0, columns[hover].target ?? 0))} {width}>
			{@render tooltip(columns[hover])}
		</Tooltip>
	{/if}
</div>
