<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { formatDate, hm, localDate, monthRange, shiftMonth, signedHm, weekday } from '#lib/time.js';
	import type { Day, Place, Report } from '#lib/types.js';
	import { DAY_BADGE, dayKindLabel } from '#lib/labels.js';
	import DayEditor from '#lib/components/DayEditor.svelte';
	import { ChevronLeft, ChevronRight, Download, FileText, TriangleAlert } from '@lucide/svelte';

	const todayStr = localDate(new Date(), auth.tz);
	let month = $state(todayStr.slice(0, 7));
	let report = $state<Report | null>(null);
	let places = $state<Place[]>([]);
	let editing = $state<Day | null>(null);

	async function load() {
		const r = await api.get<Report>('/report', monthRange(month));
		report = r;
		if (editing) editing = r.days.find((d) => d.day === editing?.day) ?? null;
	}

	$effect(() => {
		void month;
		load();
	});
	$effect(() => {
		api.get<Place[]>('/places').then((p) => (places = p));
	});

	const monthLabel = $derived(formatDate(`${month}-01`, getLocale(), { month: 'long', year: 'numeric' }));
	const maxMinutes = $derived(Math.max(600, ...(report?.days.map((d) => Math.max(d.actual, d.target)) ?? [])));

	function badge(d: Day): { text: string; cls: string } | null {
		if (d.entry && d.entry !== 'workday') return { text: dayKindLabel(d.entry), cls: DAY_BADGE[d.entry] };
		if (d.holiday) return { text: d.holiday, cls: DAY_BADGE.public_holiday };
		return null;
	}

	const KIND_BAR = { home: 'bg-home', office: 'bg-office', other: 'bg-brand-500' };
	const isFuture = (d: Day) => d.day > todayStr;
	const isWeekend = (d: Day) => weekday(d.day) >= 5;
</script>

<div class="space-y-6">
	<div class="flex items-center justify-between gap-4">
		<h1 class="text-2xl font-semibold tracking-tight">{m.history_title()}</h1>
		<div class="flex items-center gap-1">
			<button class="btn-ghost p-2" onclick={() => (month = shiftMonth(month, -1))} aria-label="←">
				<ChevronLeft class="size-5" />
			</button>
			<span class="w-36 text-center font-medium capitalize">{monthLabel}</span>
			<button class="btn-ghost p-2" onclick={() => (month = shiftMonth(month, 1))} aria-label="→">
				<ChevronRight class="size-5" />
			</button>
		</div>
	</div>

	{#if report}
		<div class="flex flex-wrap justify-end gap-2">
			<a class="btn-secondary py-1.5" href="/report/{month}"><FileText class="size-4" />{m.monthly_report()}</a>
			<a class="btn-ghost py-1.5" href="/api/export.csv?from={monthRange(month).from}&to={monthRange(month).to}" download data-sveltekit-reload>
				<Download class="size-4" />{m.export_csv()}
			</a>
		</div>
		<div class="grid grid-cols-2 gap-4 md:grid-cols-4">
			<div class="card p-4">
				<div class="text-xs font-medium muted">{m.target()}</div>
				<div class="text-xl font-semibold tabular-nums">{hm(report.target)}</div>
			</div>
			<div class="card p-4">
				<div class="text-xs font-medium muted">{m.actual()}</div>
				<div class="text-xl font-semibold tabular-nums">{hm(report.actual)}</div>
			</div>
			<div class="card p-4">
				<div class="text-xs font-medium muted">{m.difference()}</div>
				<div class="text-xl font-semibold tabular-nums {report.diff >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}">
					{signedHm(report.diff)}
				</div>
			</div>
			<div class="card p-4">
				<div class="text-xs font-medium muted">{m.balance_at_end()}</div>
				<div class="text-xl font-semibold tabular-nums {report.balance >= 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400'}">
					{signedHm(report.balance)}
				</div>
			</div>
		</div>

		<!-- Month chart: bar = actual, line = target -->
		<section class="card">
			<div class="flex h-40 items-end gap-[3px]">
				{#each report.days as d (d.day)}
					<button
						class="group relative flex h-full flex-1 items-end rounded-sm hover:bg-slate-100 dark:hover:bg-slate-800"
						onclick={() => (editing = d)}
						title="{formatDate(d.day, getLocale(), { weekday: 'short', day: 'numeric' })}: {hm(d.actual)} / {hm(d.target)}"
					>
						{#if d.target > 0}
							<div
								class="absolute inset-x-0 border-t-2 border-dashed border-slate-300 dark:border-slate-600"
								style="bottom:{(d.target / maxMinutes) * 100}%"
							></div>
						{/if}
						<div
							class="w-full rounded-t {KIND_BAR[d.kinds[0] ?? 'other']} {d.actual < d.target ? 'opacity-60' : ''} transition-all"
							style="height:{(d.actual / maxMinutes) * 100}%"
						></div>
					</button>
				{/each}
			</div>
			<div class="mt-3 flex flex-wrap gap-4 text-xs muted">
				<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-full bg-home"></span>{m.kind_home()}</span>
				<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-full bg-office"></span>{m.kind_office()}</span>
				<span class="flex items-center gap-1.5"><span class="w-4 border-t-2 border-dashed border-slate-400"></span>{m.target()}</span>
			</div>
		</section>

		<section class="card p-0">
			<ul class="divide-y divide-slate-100 dark:divide-slate-800">
				{#each report.days as d (d.day)}
					{@const b = badge(d)}
					<li>
						<button
							class="flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition hover:bg-slate-50 sm:px-5 dark:hover:bg-slate-800/50 {isWeekend(d) && !d.actual ? 'opacity-50' : ''} {d.day === todayStr ? 'bg-brand-50/60 dark:bg-brand-900/20' : ''}"
							onclick={() => (editing = d)}
						>
							<span class="w-14 shrink-0 tabular-nums">
								<span class="font-semibold">{formatDate(d.day, getLocale(), { day: '2-digit' })}.</span>
								<span class="muted">{formatDate(d.day, getLocale(), { weekday: 'short' })}</span>
							</span>
							<span class="flex min-w-0 flex-1 items-center gap-1.5">
								{#each d.kinds as k (k)}
									<span class="size-2 shrink-0 rounded-full {KIND_BAR[k]}"></span>
								{/each}
								{#if b}
									<span class="truncate rounded-md px-1.5 py-0.5 text-xs {b.cls}">{b.text}</span>
								{/if}
								{#if d.warnings.length}
									<TriangleAlert class="size-4 shrink-0 text-amber-500" />
								{/if}
							</span>
							<span class="w-14 text-right tabular-nums">{d.actual || (d.target && !isFuture(d)) ? hm(d.actual) : ''}</span>
							<span class="hidden w-14 text-right tabular-nums muted sm:inline">{d.target ? hm(d.target) : ''}</span>
							<span
								class="w-16 text-right font-medium tabular-nums {isFuture(d) || !d.diff
									? 'muted'
									: d.diff > 0
										? 'text-emerald-600 dark:text-emerald-400'
										: 'text-rose-600 dark:text-rose-400'}"
							>
								{isFuture(d) ? '' : d.diff ? signedHm(d.diff) : ''}
							</span>
						</button>
					</li>
				{/each}
			</ul>
		</section>
	{:else}
		<div class="card muted">{m.loading()}</div>
	{/if}
</div>

{#if editing}
	<DayEditor day={editing} {places} onclose={() => (editing = null)} onchange={load} />
{/if}
