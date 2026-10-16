<script lang="ts">
	import { localTime } from '#lib/time.js';
	import type { Segment } from '#lib/types.js';

	let { segments, tz, now }: { segments: Segment[]; tz: string; now: Date } = $props();

	function hours(iso: string | Date): number {
		const [h, m] = localTime(iso, tz).split(':').map(Number);
		return h + m / 60;
	}

	const range = $derived.by(() => {
		let lo = 7;
		let hi = 18;
		for (const s of segments) {
			lo = Math.min(lo, Math.floor(hours(s.start)));
			hi = Math.max(hi, Math.ceil(hours(s.end ?? now)));
		}
		return { lo, hi: Math.min(Math.max(hi, lo + 4), 24) };
	});

	const ticks = $derived.by(() => {
		const out = [];
		const step = range.hi - range.lo > 12 ? 3 : 2;
		for (let h = Math.ceil(range.lo / step) * step; h <= range.hi; h += step) out.push(h);
		return out;
	});

	const pos = (h: number) => ((h - range.lo) / (range.hi - range.lo)) * 100;

	const COLORS: Record<Segment['type'], string> = {
		home: 'bg-home',
		office: 'bg-office',
		other: 'bg-brand-500',
		travel: 'bg-travel',
		break: 'bg-stripes'
	};
</script>

<div>
	<div class="relative h-9 overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-800">
		{#each segments as s, i (i)}
			{@const a = pos(hours(s.start))}
			{@const b = pos(Math.max(hours(s.end ?? now), hours(s.start)))}
			<div
				class="absolute inset-y-0 {COLORS[s.type]} {s.type === 'break' ? 'z-10' : ''} {s.end === null
					? 'animate-pulse'
					: ''}"
				style="left:{a}%;width:max({b - a}%, 3px)"
			></div>
		{/each}
		{#if hours(now) >= range.lo && hours(now) <= range.hi}
			<div class="absolute inset-y-0 z-20 w-0.5 bg-slate-900 dark:bg-white" style="left:{pos(hours(now))}%"></div>
		{/if}
	</div>
	<div class="relative mt-1 h-4 text-[10px] muted">
		{#each ticks as h (h)}
			<span class="absolute -translate-x-1/2" style="left:{pos(h)}%">{h}:00</span>
		{/each}
	</div>
</div>

<style>
	.bg-stripes {
		background: repeating-linear-gradient(
			-45deg,
			rgb(255 255 255 / 0.85) 0 4px,
			rgb(255 255 255 / 0.35) 4px 8px
		);
	}
</style>
