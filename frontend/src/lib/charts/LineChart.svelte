<script lang="ts">
	import type { Snippet } from 'svelte';
	import Tooltip from './Tooltip.svelte';
	import { hourTicks, linear } from './scale.js';

	interface Point {
		x: string; // date
		y: number; // minutes
	}

	let {
		points,
		label,
		xLabel,
		tooltip,
		height = 220
	}: {
		points: Point[];
		label: string;
		xLabel: (x: string) => string;
		tooltip: Snippet<[Point]>;
		height?: number;
	} = $props();

	let width = $state(600);
	const pad = { top: 12, right: 12, bottom: 26, left: 44 };
	const ys = $derived(points.map((p) => p.y));
	const ticks = $derived(hourTicks(Math.min(0, ...ys), Math.max(0, ...ys), 4));
	const sx = $derived(linear(0, Math.max(points.length - 1, 1), pad.left, width - pad.right));
	const sy = $derived(linear(ticks[0], ticks[ticks.length - 1], height - pad.bottom, pad.top));
	const path = $derived(points.map((p, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(p.y).toFixed(1)}`).join(''));
	const area = $derived(
		points.length
			? `${path}L${sx(points.length - 1).toFixed(1)},${sy(0)}L${sx(0).toFixed(1)},${sy(0)}Z`
			: ''
	);
	const xTicks = $derived.by(() => {
		const n = points.length;
		const want = Math.max(2, Math.min(6, Math.floor(width / 110)));
		const step = Math.max(1, Math.ceil(n / want));
		return points.map((p, i) => ({ i, p })).filter(({ i }) => i % step === 0);
	});

	let hover = $state<number | null>(null);
	function onmove(e: PointerEvent) {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		const x = e.clientX - rect.left;
		const i = Math.round(((x - pad.left) / (width - pad.left - pad.right)) * (points.length - 1));
		hover = points.length ? Math.max(0, Math.min(points.length - 1, i)) : null;
	}
	const last = $derived(points.length ? points.length - 1 : null);
</script>

<div class="relative w-full min-w-0" bind:clientWidth={width}>
	<svg
		{width}
		{height}
		role="img"
		aria-label={label}
		class="block w-full touch-pan-y"
		onpointermove={onmove}
		onpointerdown={onmove}
		onpointerleave={() => (hover = null)}
	>
		{#each ticks as t (t)}
			<line x1={pad.left} x2={width - pad.right} y1={sy(t)} y2={sy(t)} stroke={t === 0 ? 'var(--c-axis)' : 'var(--c-grid)'} stroke-width="1" />
			<text x={pad.left - 8} y={sy(t)} dy="0.32em" text-anchor="end" class="fill-slate-500 text-[11px] tabular-nums dark:fill-slate-400">
				{(t / 60).toLocaleString()} h
			</text>
		{/each}
		{#each xTicks as { i, p } (i)}
			<text x={sx(i)} y={height - 6} text-anchor="middle" class="fill-slate-500 text-[11px] dark:fill-slate-400">{xLabel(p.x)}</text>
		{/each}
		<path d={area} fill="var(--c-line)" opacity="0.1" />
		<path d={path} fill="none" stroke="var(--c-line)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
		{#if last !== null}
			<circle cx={sx(last)} cy={sy(points[last].y)} r="4" fill="var(--c-line)" stroke="var(--color-white, #fff)" stroke-width="2" class="dark:stroke-slate-900" />
		{/if}
		{#if hover !== null}
			<line x1={sx(hover)} x2={sx(hover)} y1={pad.top} y2={height - pad.bottom} stroke="var(--c-axis)" stroke-width="1" />
			<circle cx={sx(hover)} cy={sy(points[hover].y)} r="5" fill="var(--c-line)" stroke="white" stroke-width="2" class="dark:stroke-slate-900" />
		{/if}
	</svg>
	{#if hover !== null}
		<Tooltip x={sx(hover)} y={sy(points[hover].y)} {width}>{@render tooltip(points[hover])}</Tooltip>
	{/if}
</div>
