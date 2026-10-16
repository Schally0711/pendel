<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { dayKindLabel } from '#lib/labels.js';
	import { addDays, formatDate, hm, localDate, signedHm } from '#lib/time.js';
	import type { DayKind, Stats, TaxOverview, WorkModel } from '#lib/types.js';
	import LineChart from '#lib/charts/LineChart.svelte';
	import ColumnChart from '#lib/charts/ColumnChart.svelte';
	import ShareBar from '#lib/charts/ShareBar.svelte';
	import WindowChart from '#lib/charts/WindowChart.svelte';
	import { Printer, Table2 } from '@lucide/svelte';

	const today = localDate(new Date(), auth.tz);
	const year = Number(today.slice(0, 4));
	const month = today.slice(0, 7);

	type Preset = { key: string; label: () => string; from: string; to: string };
	const firstOfMonth = (d: string) => `${d.slice(0, 7)}-01`;
	const lastMonthEnd = addDays(firstOfMonth(today), -1);
	const presets: Preset[] = [
		{ key: 'month', label: m.range_this_month, from: `${month}-01`, to: today },
		{ key: 'last', label: m.range_last_month, from: firstOfMonth(lastMonthEnd), to: lastMonthEnd },
		{ key: '3m', label: m.range_3_months, from: addDays(today, -91), to: today },
		{ key: 'year', label: m.range_this_year, from: `${year}-01-01`, to: today },
		{ key: '12m', label: m.range_12_months, from: addDays(today, -364), to: today }
	];
	let preset = $state('month');
	let stats = $state<Stats | null>(null);
	let showTable = $state(false);

	// Selectable years: from the first work model (at least the last three years) up to now
	let firstYear = $state(year - 2);
	api.get<WorkModel[]>('/work-models').then((models) => {
		const first = Math.min(...models.map((w) => Number(w.valid_from.slice(0, 4))));
		if (first < firstYear) firstYear = first;
	});
	const years = $derived(Array.from({ length: year - firstYear + 1 }, (_, i) => year - i));
	const yearRange = (y: number) => ({ from: `${y}-01-01`, to: y === year ? today : `${y}-12-31` });

	$effect(() => {
		const range = preset.startsWith('y:') ? yearRange(Number(preset.slice(2))) : presets.find((x) => x.key === preset)!;
		api.get<Stats>('/stats', { from: range.from, to: range.to }).then((s) => (stats = s));
	});

	let taxYear = $state(year);
	let tax = $state<TaxOverview | null>(null);
	$effect(() => {
		api.get<TaxOverview>(`/tax/${taxYear}`).then((t) => (tax = t));
	});

	const s = $derived(stats?.summary);
	const locale = getLocale();
	const short = (d: string) => formatDate(d, locale, { day: 'numeric', month: 'numeric' });
	const clock = (m: number | null | undefined) =>
		m === null || m === undefined ? '–' : `${Math.floor(m / 60)}:${String(Math.round(m % 60)).padStart(2, '0')}`;
	const daysText = (n: number) => (n === 1 ? m.day_one() : m.days_n({ n }));
	const euro = (n: number) => n.toLocaleString(locale, { style: 'currency', currency: 'EUR' });

	const workedDays = $derived(stats?.days.filter((d) => d.actual > 0 || d.target > 0) ?? []);
	const balancePoints = $derived((stats?.days ?? []).map((d) => ({ x: d.day, y: d.balance })));

	function periodLabel(key: string): string {
		if (key.includes('-W')) return m.week_short({ n: Number(key.split('-W')[1]) });
		return formatDate(`${key}-01`, locale, { month: 'short' });
	}
	const columns = $derived(
		(stats?.periods ?? []).map((p) => ({ key: p.key, label: periodLabel(p.key), value: p.actual, target: p.target, p }))
	);

	const absenceTotal = $derived(Object.values(s?.absence_days ?? {}).reduce((a, b) => a + b, 0));
	const places = $derived([
		{ key: 'office', label: m.kind_office(), value: s?.office_days ?? 0, color: 'var(--c-office)' },
		{ key: 'home', label: m.kind_home(), value: s?.home_days ?? 0, color: 'var(--c-home)' },
		{ key: 'absence', label: m.absence(), value: absenceTotal, color: 'var(--c-absence)' },
		...(s?.other_days ? [{ key: 'other', label: m.kind_other(), value: s.other_days, color: 'var(--c-travel)' }] : [])
	]);
	const homeShare = $derived(
		s && s.office_days + s.home_days > 0 ? Math.round((s.home_days / (s.office_days + s.home_days)) * 100) : null
	);

	let innerWidth = $state(1024);
	// fewer days on narrow screens so the bars stay readable
	const WINDOW_DAYS = $derived(innerWidth < 640 ? 21 : 62);
	const windowDays = $derived(
		(stats?.days ?? []).slice(-WINDOW_DAYS).filter((d) => d.target > 0 || d.start !== null).map((d) => ({
			key: d.day,
			label: short(d.day),
			start: d.start,
			end: d.end,
			color: d.place === 'home' ? 'var(--c-home)' : d.place === 'office' ? 'var(--c-office)' : 'var(--c-travel)',
			d
		}))
	);

	const weekdayNames = Array.from({ length: 5 }, (_, i) =>
		formatDate(`2026-01-${String(5 + i).padStart(2, '0')}`, locale, { weekday: 'short' })
	);
	const commuteCols = $derived(
		weekdayNames.map((name, i) => ({ key: String(i), label: name, value: s?.commute_by_weekday[i] ?? null }))
	);
	const hasCommute = $derived(commuteCols.some((c) => c.value));
</script>

<svelte:window bind:innerWidth />

{#snippet kpi(label: string, value: string, sub = '')}
	<div class="card p-4">
		<div class="text-xs font-medium muted">{label}</div>
		<div class="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
		{#if sub}<div class="mt-0.5 truncate text-xs muted">{sub}</div>{/if}
	</div>
{/snippet}

<div class="space-y-6">
	<div class="flex flex-wrap items-center justify-between gap-3">
		<h1 class="text-2xl font-semibold tracking-tight">{m.stats_title()}</h1>
		<div class="flex flex-wrap gap-1 rounded-xl bg-white p-1 shadow-sm ring-1 ring-slate-900/5 dark:bg-slate-900 dark:ring-white/10">
			{#each presets as p (p.key)}
				<button
					class="rounded-lg px-3 py-1.5 text-sm font-medium transition {preset === p.key
						? 'bg-brand-600 text-white'
						: 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}"
					onclick={() => (preset = p.key)}>{p.label()}</button
				>
			{/each}
			<select
				class="rounded-lg border-0 py-1.5 pr-7 pl-3 text-sm font-medium transition {preset.startsWith('y:')
					? 'bg-brand-600 text-white'
					: 'bg-transparent text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'}"
				aria-label={m.range_year()}
				value={preset.startsWith('y:') ? preset : ''}
				onchange={(e) => {
					const v = e.currentTarget.value;
					if (v) [preset, taxYear] = [v, Number(v.slice(2))];
				}}
			>
				<option value="" disabled>{m.range_year()}</option>
				{#each years as y (y)}<option value="y:{y}">{y}</option>{/each}
			</select>
		</div>
	</div>

	{#if !stats || !s}
		<div class="card muted">{m.loading()}</div>
	{:else if s.worked_days === 0 && absenceTotal === 0}
		<div class="card muted">{m.no_data()}</div>
	{:else}
		<div class="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
			{@render kpi(m.kpi_avg_day(), `${hm(s.avg_actual)} h`, m.kpi_worked_days({ n: s.worked_days }))}
			{@render kpi(m.kpi_overtime(), `${signedHm(s.diff)} h`, `${m.legend_target()} ${hm(s.target)} h`)}
			{@render kpi(m.kpi_home_share(), homeShare === null ? '–' : `${homeShare} %`, m.kpi_home_of({ home: s.home_days, total: s.home_days + s.office_days }))}
			{@render kpi(m.kpi_avg_start(), clock(s.avg_start), m.kpi_earliest({ t: clock(s.earliest_start) }))}
			{@render kpi(m.kpi_avg_end(), clock(s.avg_end), m.kpi_latest({ t: clock(s.latest_end) }))}
			{@render kpi(
				m.kpi_avg_commute(),
				s.avg_commute_to === null && s.avg_commute_from === null ? '–' : `${Math.round((s.avg_commute_to ?? 0) + (s.avg_commute_from ?? 0))} min`,
				s.avg_commute_to !== null ? m.kpi_commute_split({ to: `${Math.round(s.avg_commute_to ?? 0)}`, back: `${Math.round(s.avg_commute_from ?? 0)}` }) : ''
			)}
		</div>

		<div class="grid gap-6 lg:grid-cols-2">
			<section class="card min-w-0">
				<h2 class="section-title mb-0">{m.chart_balance()}</h2>
				<p class="mb-3 text-xs muted">{m.chart_balance_sub()}</p>
				<LineChart points={balancePoints} label={m.chart_balance()} xLabel={short}>
					{#snippet tooltip(p)}
						<div class="font-medium">{formatDate(p.x, locale, { weekday: 'short', day: 'numeric', month: 'short' })}</div>
						<div class="tabular-nums">{signedHm(p.y)} h</div>
					{/snippet}
				</LineChart>
			</section>

			<section class="card min-w-0">
				<div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
					<h2 class="section-title mb-0">{stats.group === 'week' ? m.chart_periods_week() : m.chart_periods_month()}</h2>
					<div class="flex gap-4 text-xs muted">
						<span class="flex items-center gap-1.5"><span class="h-2.5 w-3 rounded-sm" style="background:var(--c-line)"></span>{m.legend_actual()}</span>
						<span class="flex items-center gap-1.5"><span class="h-0.5 w-3 rounded bg-slate-700 dark:bg-slate-200"></span>{m.legend_target()}</span>
					</div>
				</div>
				<ColumnChart {columns} label={m.chart_periods_week()}>
					{#snippet tooltip(c)}
						<div class="font-medium">{c.label}</div>
						<div class="tabular-nums">{m.legend_actual()} {hm(c.value ?? 0)} h · {m.legend_target()} {hm(c.target ?? 0)} h</div>
						<div class="tabular-nums">{signedHm((c.value ?? 0) - (c.target ?? 0))} h</div>
					{/snippet}
				</ColumnChart>
			</section>

			<section class="card min-w-0">
				<h2 class="section-title mb-0">{m.chart_places()}</h2>
				<p class="mb-3 text-xs muted">{m.chart_places_sub()}</p>
				<ShareBar parts={places} unit={daysText} />
				{#if absenceTotal}
					<div class="mt-4 flex flex-wrap gap-2 text-xs">
						{#each Object.entries(s.absence_days) as [kind, n] (kind)}
							<span class="rounded-md bg-slate-100 px-2 py-1 dark:bg-slate-800">{dayKindLabel(kind as DayKind)} · {n}</span>
						{/each}
					</div>
				{/if}
			</section>

			{#if hasCommute}
				<section class="card min-w-0">
					<h2 class="section-title mb-0">{m.chart_commute()}</h2>
					<p class="mb-3 text-xs muted">{m.chart_commute_sub()}</p>
					<ColumnChart columns={commuteCols} label={m.chart_commute()} color="var(--c-travel)" valueLabels height={180}>
						{#snippet tooltip(c)}
							<div class="font-medium">{c.label}</div>
							<div class="tabular-nums">Ø {Math.round(c.value ?? 0)} min</div>
						{/snippet}
					</ColumnChart>
				</section>
			{/if}

			{#if windowDays.some((d) => d.start !== null)}
				<section class="card min-w-0 lg:col-span-2">
					<div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
						<div>
							<h2 class="section-title mb-0">{m.chart_window()}</h2>
							<p class="text-xs muted">
								{m.chart_window_sub()}{(stats.days.length > WINDOW_DAYS) ? ` · ${m.window_last_days({ n: WINDOW_DAYS })}` : ''}
							</p>
						</div>
						<div class="flex gap-4 text-xs muted">
							<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-sm bg-office"></span>{m.kind_office()}</span>
							<span class="flex items-center gap-1.5"><span class="size-2.5 rounded-sm bg-home"></span>{m.kind_home()}</span>
						</div>
					</div>
					<WindowChart days={windowDays} label={m.chart_window()} avgStart={s.avg_start} avgEnd={s.avg_end} avgLabels={['Ø', 'Ø']}>
						{#snippet tooltip(w)}
							<div class="font-medium">{formatDate(w.key, locale, { weekday: 'short', day: 'numeric', month: 'short' })}</div>
							{#if w.start !== null}
								<div class="tabular-nums">{clock(w.start)} – {clock(w.end)}</div>
							{:else}
								<div class="muted">–</div>
							{/if}
						{/snippet}
					</WindowChart>
				</section>
			{/if}
		</div>

		<section class="card min-w-0">
			<div class="flex items-center justify-between">
				<h2 class="section-title mb-0">{m.period()}</h2>
				<button class="btn-ghost px-2 py-1 text-xs" onclick={() => (showTable = !showTable)}>
					<Table2 class="size-4" />{m.table_view()}
				</button>
			</div>
			{#if showTable}
				<div class="mt-3 overflow-x-auto">
					<table class="w-full text-sm tabular-nums">
						<thead class="text-left text-xs muted">
							<tr>
								<th class="py-2 pr-3 font-medium">{m.period()}</th>
								<th class="py-2 pr-3 text-right font-medium">{m.legend_target()}</th>
								<th class="py-2 pr-3 text-right font-medium">{m.legend_actual()}</th>
								<th class="py-2 pr-3 text-right font-medium">{m.difference()}</th>
								<th class="py-2 pr-3 text-right font-medium">{m.kind_office()}</th>
								<th class="py-2 pr-3 text-right font-medium">{m.kind_home()}</th>
								<th class="py-2 text-right font-medium">{m.absence()}</th>
							</tr>
						</thead>
						<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
							{#each stats.periods as p (p.key)}
								<tr>
									<td class="py-2 pr-3">{periodLabel(p.key)} <span class="text-xs muted">{short(p.start)}–{short(p.end)}</span></td>
									<td class="py-2 pr-3 text-right">{hm(p.target)}</td>
									<td class="py-2 pr-3 text-right">{hm(p.actual)}</td>
									<td class="py-2 pr-3 text-right font-medium">{signedHm(p.diff)}</td>
									<td class="py-2 pr-3 text-right">{p.office_days}</td>
									<td class="py-2 pr-3 text-right">{p.home_days}</td>
									<td class="py-2 text-right">{p.absence_days}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}

	<!-- Tax -->
	{#if tax}
		<section class="card print:shadow-none">
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div>
					<h2 class="section-title mb-1">{m.tax_title({ year: tax.year })}</h2>
					<p class="text-sm muted">{m.tax_sub({ date: formatDate(tax.until, locale, { dateStyle: 'medium' }) })}</p>
				</div>
				<div class="flex items-center gap-2 print:hidden">
					<select class="input w-auto py-1.5" bind:value={taxYear}>
						{#each years as y (y)}<option value={y}>{y}</option>{/each}
					</select>
					<button class="btn-secondary py-1.5" onclick={() => window.print()}><Printer class="size-4" />{m.print()}</button>
				</div>
			</div>
			<div class="mt-5 grid gap-4 md:grid-cols-2">
				<div class="rounded-2xl bg-slate-50 p-4 dark:bg-slate-800/60">
					<div class="flex items-center gap-2 text-sm font-medium">
						<span class="size-2.5 rounded-sm bg-office"></span>{m.tax_commuter()}
					</div>
					<div class="mt-2 text-3xl font-semibold tracking-tight">{euro(tax.commuter_total)}</div>
					<ul class="mt-2 space-y-0.5 text-sm muted">
						{#each tax.offices as o (o.place)}
							<li>{o.place}: {m.tax_commuter_line({ days: o.days, km: o.distance_km === null ? '?' : o.distance_km.toLocaleString(locale) })}</li>
						{/each}
						<li class="text-xs">
							{tax.commuter_rate[0] === tax.commuter_rate[1]
								? m.tax_rate_flat({ a: tax.commuter_rate[0].toLocaleString(locale) })
								: m.tax_rate_line({ a: tax.commuter_rate[0].toLocaleString(locale), b: tax.commuter_rate[1].toLocaleString(locale) })}
						</li>
					</ul>
					{#if tax.missing_distance}<p class="mt-2 text-xs text-amber-700 dark:text-amber-400">{m.tax_missing_km()}</p>{/if}
				</div>
				<div class="rounded-2xl bg-slate-50 p-4 dark:bg-slate-800/60">
					<div class="flex items-center gap-2 text-sm font-medium">
						<span class="size-2.5 rounded-sm bg-home"></span>{m.tax_home()}
					</div>
					<div class="mt-2 text-3xl font-semibold tracking-tight">{euro(tax.home_office_total)}</div>
					<ul class="mt-2 space-y-0.5 text-sm muted">
						<li>{m.tax_home_line({ days: tax.home_office_days_counted, rate: tax.home_office_rate.toLocaleString(locale) })}</li>
						<li class="text-xs">{m.tax_home_cap({ max: tax.home_office_max_days })}</li>
					</ul>
				</div>
			</div>
			<p class="mt-4 text-xs muted">{m.tax_disclaimer()}</p>
		</section>
	{/if}
</div>
