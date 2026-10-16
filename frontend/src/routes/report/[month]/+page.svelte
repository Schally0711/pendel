<script lang="ts">
	import { page } from '$app/state';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { dayKindLabel, placeKindLabel } from '#lib/labels.js';
	import { formatDate, hm, monthRange, signedHm, weekday } from '#lib/time.js';
	import type { Stats } from '#lib/types.js';
	import { ArrowLeft, Download, Printer } from '@lucide/svelte';

	const month = $derived(page.params.month ?? '');
	const range = $derived(monthRange(month));
	let stats = $state<Stats | null>(null);

	$effect(() => {
		api.get<Stats>('/stats', { ...range, group: 'month' }).then((s) => (stats = s));
	});

	const locale = getLocale();
	const title = $derived(formatDate(`${month}-01`, locale, { month: 'long', year: 'numeric' }));
	const clock = (v: number | null) =>
		v === null ? '' : `${Math.floor(v / 60)}:${String(Math.round(v % 60)).padStart(2, '0')}`;
	const csvUrl = $derived(`/api/export.csv?from=${range.from}&to=${range.to}`);
</script>

<svelte:head><title>{m.report_title({ month: title })} – {auth.user?.display_name}</title></svelte:head>

<div class="mx-auto max-w-4xl space-y-4">
	<div class="flex flex-wrap items-center justify-between gap-2 print:hidden">
		<a href="/history" class="btn-ghost"><ArrowLeft class="size-4" />{m.back()}</a>
		<div class="flex gap-2">
			<a class="btn-secondary" href={csvUrl} download data-sveltekit-reload><Download class="size-4" />{m.export_csv()}</a>
			<button class="btn-primary" onclick={() => window.print()}><Printer class="size-4" />{m.print()}</button>
		</div>
	</div>

	<article class="card p-6 text-[13px] print:p-0 print:shadow-none print:ring-0 sm:p-8">
		<header class="flex items-start justify-between gap-4 border-b border-slate-200 pb-4 dark:border-slate-700">
			<div>
				<h1 class="text-xl font-semibold">{m.report_title({ month: title })}</h1>
				<p class="mt-1 muted">{m.report_person()}: <span class="font-medium text-slate-900 dark:text-slate-100">{auth.user?.display_name}</span></p>
			</div>
			<div class="text-right text-xs muted">Pendel</div>
		</header>

		{#if !stats}
			<p class="py-6 muted">{m.loading()}</p>
		{:else}
			<table class="mt-4 w-full tabular-nums">
				<thead>
					<tr class="border-b border-slate-200 text-left text-[11px] tracking-wide text-slate-500 uppercase dark:border-slate-700">
						<th class="py-1.5 pr-2 font-medium">{m.day()}</th>
						<th class="py-1.5 pr-2 font-medium">{m.day_type()}</th>
						<th class="py-1.5 pr-2 font-medium">{m.start()}</th>
						<th class="py-1.5 pr-2 font-medium">{m.end()}</th>
						<th class="py-1.5 pr-2 text-right font-medium">{m.breaks()}</th>
						<th class="py-1.5 pr-2 text-right font-medium">{m.legend_target()}</th>
						<th class="py-1.5 pr-2 text-right font-medium">{m.legend_actual()}</th>
						<th class="py-1.5 text-right font-medium">{m.difference()}</th>
					</tr>
				</thead>
				<tbody>
					{#each stats.days as d (d.day)}
						<tr class="border-b border-slate-100 dark:border-slate-800 {weekday(d.day) >= 5 ? 'text-slate-400' : ''}">
							<td class="py-1 pr-2 whitespace-nowrap">{formatDate(d.day, locale, { weekday: 'short', day: '2-digit', month: '2-digit' })}</td>
							<td class="py-1 pr-2">
								{d.entry && d.entry !== 'workday' ? dayKindLabel(d.entry) : d.holiday ? d.holiday : d.place ? placeKindLabel(d.place) : ''}
							</td>
							<td class="py-1 pr-2">{clock(d.start)}</td>
							<td class="py-1 pr-2">{clock(d.end)}</td>
							<td class="py-1 pr-2 text-right">{d.breaks ? hm(d.breaks) : ''}</td>
							<td class="py-1 pr-2 text-right">{d.target ? hm(d.target) : ''}</td>
							<td class="py-1 pr-2 text-right">{d.actual ? hm(d.actual) : ''}</td>
							<td class="py-1 text-right">{d.target || d.actual ? signedHm(d.diff) : ''}</td>
						</tr>
					{/each}
				</tbody>
				<tfoot>
					<tr class="border-t-2 border-slate-300 font-semibold dark:border-slate-600">
						<td class="py-2 pr-2" colspan="5">{m.report_sum()}</td>
						<td class="py-2 pr-2 text-right">{hm(stats.summary.target)}</td>
						<td class="py-2 pr-2 text-right">{hm(stats.summary.actual)}</td>
						<td class="py-2 text-right">{signedHm(stats.summary.diff)}</td>
					</tr>
				</tfoot>
			</table>

			<dl class="mt-4 grid max-w-sm grid-cols-[1fr_auto] gap-x-6 gap-y-1">
				<dt class="muted">{m.report_balance_start()}</dt>
				<dd class="text-right tabular-nums">{signedHm(stats.summary.balance_start)} h</dd>
				<dt class="font-semibold">{m.report_balance_end()}</dt>
				<dd class="text-right font-semibold tabular-nums">{signedHm(stats.summary.balance_end)} h</dd>
			</dl>

			<div class="mt-16 grid grid-cols-2 gap-10 text-xs muted">
				<div class="border-t border-slate-400 pt-1">{m.report_signature_employee()}</div>
				<div class="border-t border-slate-400 pt-1">{m.report_signature_manager()}</div>
			</div>
			<p class="mt-6 text-[10px] muted">{m.report_generated({ date: new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(new Date()) })}</p>
		{/if}
	</article>
</div>

<style>
	@media print {
		@page {
			size: A4;
			margin: 14mm;
		}
		:global(html),
		:global(body) {
			background: white !important;
			color: black !important;
		}
	}
</style>
