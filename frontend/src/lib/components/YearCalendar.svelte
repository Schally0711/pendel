<script lang="ts">
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { DAY_DOT, dayKindLabel } from '#lib/labels.js';
	import { formatDate, weekday } from '#lib/time.js';
	import type { Day } from '#lib/types.js';

	let {
		year,
		days,
		today,
		onpick
	}: { year: number; days: Day[]; today: string; onpick: (d: Day) => void } = $props();

	const byDate = $derived(new Map(days.map((d) => [d.day, d])));
	const months = Array.from({ length: 12 }, (_, i) => i);
	const weekdays = $derived(
		Array.from({ length: 7 }, (_, i) =>
			formatDate(`2026-01-${String(5 + i).padStart(2, '0')}`, getLocale(), { weekday: 'narrow' })
		)
	);

	function cells(month: number): (string | null)[] {
		const first = `${year}-${String(month + 1).padStart(2, '0')}-01`;
		const count = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
		const out: (string | null)[] = Array(weekday(first)).fill(null);
		for (let d = 1; d <= count; d++) out.push(`${first.slice(0, 8)}${String(d).padStart(2, '0')}`);
		return out;
	}

	function cls(date: string): string {
		const d = byDate.get(date);
		if (d?.entry && d.entry !== 'workday') return `${DAY_DOT[d.entry]} text-white font-semibold`;
		if (d?.holiday) return 'bg-violet-200 text-violet-800 dark:bg-violet-900 dark:text-violet-200';
		if (weekday(date) >= 5) return 'text-slate-400 dark:text-slate-600';
		return 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800';
	}

	function title(date: string): string {
		const d = byDate.get(date);
		const label = d?.entry ? dayKindLabel(d.entry) : (d?.holiday ?? '');
		return `${formatDate(date, getLocale(), { weekday: 'short', day: 'numeric', month: 'short' })}${label ? ` · ${label}` : ''}`;
	}
</script>

<div class="grid grid-cols-2 gap-x-4 gap-y-5 sm:gap-x-6 lg:grid-cols-3 xl:grid-cols-4">
	{#each months as month (month)}
		<div>
			<div class="mb-1.5 text-sm font-semibold capitalize">
				{formatDate(`${year}-${String(month + 1).padStart(2, '0')}-01`, getLocale(), { month: 'long' })}
			</div>
			<div class="grid grid-cols-7 gap-px text-center text-[10px] sm:gap-0.5 sm:text-[11px]">
				{#each weekdays as w, i (i)}<div class="py-0.5 font-medium muted">{w}</div>{/each}
				{#each cells(month) as date, i (i)}
					{#if date}
						<button
							class="aspect-square rounded-md tabular-nums transition {cls(date)} {date === today
								? 'ring-2 ring-brand-500 ring-offset-1 ring-offset-white dark:ring-offset-slate-900'
								: ''}"
							title={title(date)}
							onclick={() => byDate.get(date) && onpick(byDate.get(date)!)}
						>
							{Number(date.slice(8))}
						</button>
					{:else}
						<div></div>
					{/if}
				{/each}
			</div>
		</div>
	{/each}
</div>
