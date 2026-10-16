<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { ABSENCE_KINDS, DAY_BADGE, DAY_DOT, dayKindLabel } from '#lib/labels.js';
	import { formatDate, localDate } from '#lib/time.js';
	import type { AbsencePeriod, Day, DayKind, Place, Report, VacationAccount } from '#lib/types.js';
	import Alert from '#lib/components/Alert.svelte';
	import YearCalendar from '#lib/components/YearCalendar.svelte';
	import DayEditor from '#lib/components/DayEditor.svelte';
	import CalendarSubscription from '#lib/components/CalendarSubscription.svelte';
	import { ChevronLeft, ChevronRight, Palmtree, Pencil, Plus, Trash2 } from '@lucide/svelte';

	const today = localDate(new Date(), auth.tz);
	let year = $state(Number(today.slice(0, 4)));
	let account = $state<VacationAccount | null>(null);
	let periods = $state<AbsencePeriod[]>([]);
	let days = $state<Day[]>([]);
	let places = $state<Place[]>([]);
	let editing = $state<Day | null>(null);

	async function load() {
		const [abs, rep] = await Promise.all([
			api.get<{ account: VacationAccount; periods: AbsencePeriod[] }>('/absences', { year: String(year) }),
			api.get<Report>('/report', { from: `${year}-01-01`, to: `${year}-12-31` })
		]);
		account = abs.account;
		periods = abs.periods;
		days = rep.days;
		if (editing) editing = days.find((d) => d.day === editing?.day) ?? null;
	}
	$effect(() => {
		void year;
		load();
	});
	$effect(() => {
		api.get<Place[]>('/places').then((p) => (places = p));
	});

	// --- add absence ---
	let form = $state({ kind: 'vacation' as DayKind, start: today, end: today, note: '' });
	let preview = $state<{ days: string[]; vacation_days: number } | null>(null);
	let message = $state<{ text: string; tone: 'error' | 'success' } | null>(null);
	let busy = $state(false);

	$effect(() => {
		const body = { ...form };
		if (!body.start || !body.end || body.end < body.start) {
			preview = null;
			return;
		}
		const t = setTimeout(() => {
			api.post<{ days: string[]; vacation_days: number }>('/absences?dry_run=true', body)
				.then((r) => (preview = r))
				.catch(() => (preview = null));
		}, 200);
		return () => clearTimeout(t);
	});

	$effect(() => {
		// keep "to" not before "from"
		if (form.start && form.end < form.start) form.end = form.start;
	});

	async function addAbsence(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		message = null;
		try {
			const r = await api.post<{ days: string[] }>('/absences', form);
			message = { text: m.absence_saved({ n: r.days.length }), tone: 'success' };
			form.note = '';
			if (Number(form.start.slice(0, 4)) !== year) year = Number(form.start.slice(0, 4));
			else await load();
		} catch (err) {
			message = { text: errorText(err), tone: 'error' };
		} finally {
			busy = false;
		}
	}

	async function removePeriod(p: AbsencePeriod) {
		if (!confirm(m.confirm_delete())) return;
		await api.del(`/absences?from=${p.start}&to=${p.end}`);
		await load();
	}

	// --- allowance ---
	let editAllowance = $state(false);
	let allowance = $state({ days: 30, carried_over: 0 });
	function startEditAllowance() {
		if (!account) return;
		allowance = { days: account.days, carried_over: account.carried_over };
		editAllowance = true;
	}
	async function saveAllowance(e: SubmitEvent) {
		e.preventDefault();
		account = await api.put<VacationAccount>(`/vacation/${year}`, allowance);
		editAllowance = false;
	}

	const fmtDays = (n: number) => n.toLocaleString(getLocale(), { maximumFractionDigits: 1 });
	const daysText = (n: number) => (n === 1 ? m.vacation_days_one() : m.vacation_days_n({ n: fmtDays(n) }));
	const workdaysText = (n: number) => (n === 1 ? m.absence_workday_one() : m.absence_preview({ workdays: n }));
	// Workdays per non-vacation kind in this year
	const otherTotals = $derived(
		Object.entries(
			periods
				.filter((p) => p.kind !== 'vacation' && p.kind !== 'vacation_half')
				.reduce<Record<string, number>>((acc, p) => ((acc[p.kind] = (acc[p.kind] ?? 0) + p.workdays), acc), {})
		) as [DayKind, number][]
	);
	const range = (p: AbsencePeriod) => {
		const a = formatDate(p.start, getLocale(), { day: 'numeric', month: 'short' });
		return p.start === p.end
			? formatDate(p.start, getLocale(), { weekday: 'short', day: 'numeric', month: 'short' })
			: `${a} – ${formatDate(p.end, getLocale(), { day: 'numeric', month: 'short' })}`;
	};
	const upcoming = $derived(periods.filter((p) => p.end >= today));
	const past = $derived(periods.filter((p) => p.end < today).reverse());
	const isVacation = $derived(form.kind === 'vacation' || form.kind === 'vacation_half');
	const afterBooking = $derived(account && preview && isVacation ? account.remaining - preview.vacation_days : null);
	const pct = (n: number) => (account && account.total > 0 ? Math.max(0, Math.min(100, (n / account.total) * 100)) : 0);
</script>

{#snippet periodRow(p: AbsencePeriod)}
	<li class="flex items-center gap-3 py-2.5 text-sm">
		<span class="size-2.5 shrink-0 rounded-full {DAY_DOT[p.kind]}"></span>
		<span class="w-36 shrink-0 tabular-nums sm:w-44">{range(p)}</span>
		<span class="flex min-w-0 flex-1 items-center gap-2">
			<span class="shrink-0 rounded-md px-1.5 py-0.5 text-xs {DAY_BADGE[p.kind]}">{dayKindLabel(p.kind)}</span>
			<span class="truncate muted">{p.note}</span>
		</span>
		<span class="hidden text-right tabular-nums muted sm:inline">
			{p.vacation_days ? daysText(p.vacation_days) : workdaysText(p.workdays)}
		</span>
		<button class="btn-danger p-1.5" aria-label={m.delete()} onclick={() => removePeriod(p)}>
			<Trash2 class="size-4" />
		</button>
	</li>
{/snippet}

<div class="space-y-6">
	<div class="flex items-center justify-between gap-4">
		<h1 class="text-2xl font-semibold tracking-tight">{m.absences_title()}</h1>
		<div class="flex items-center gap-1">
			<button class="btn-ghost p-2" onclick={() => year--} aria-label="←"><ChevronLeft class="size-5" /></button>
			<span class="w-16 text-center font-medium tabular-nums">{year}</span>
			<button class="btn-ghost p-2" onclick={() => year++} aria-label="→"><ChevronRight class="size-5" /></button>
		</div>
	</div>

	<div class="grid gap-6 lg:grid-cols-5">
		<!-- Vacation account -->
		<section class="card lg:col-span-2">
			{#if account}
				<div class="flex items-start justify-between gap-3">
					<div>
						<h2 class="text-sm font-medium muted">{m.vacation_account({ year })}</h2>
						<div class="mt-1 flex items-baseline gap-2">
							<span class="text-4xl font-semibold tracking-tight tabular-nums {account.remaining < 0 ? 'text-rose-600' : ''}">
								{fmtDays(account.remaining)}
							</span>
							<span class="muted">{m.vacation_remaining()}</span>
						</div>
					</div>
					<div class="rounded-xl bg-sky-50 p-2.5 text-sky-600 dark:bg-sky-950 dark:text-sky-300">
						<Palmtree class="size-6" />
					</div>
				</div>

				<div class="mt-4 flex h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
					<div class="bg-sky-500" style="width:{pct(account.taken)}%"></div>
					<div class="bg-sky-300" style="width:{pct(account.planned)}%"></div>
				</div>
				<div class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs muted">
					<span class="flex items-center gap-1.5"><span class="size-2 rounded-full bg-sky-500"></span>{fmtDays(account.taken)} {m.vacation_taken()}</span>
					<span class="flex items-center gap-1.5"><span class="size-2 rounded-full bg-sky-300"></span>{fmtDays(account.planned)} {m.vacation_planned()}</span>
					<span class="flex items-center gap-1.5"><span class="size-2 rounded-full bg-slate-200 dark:bg-slate-700"></span>{fmtDays(Math.max(account.remaining, 0))} {m.vacation_left()}</span>
				</div>

				{#if editAllowance}
					<form class="mt-5 space-y-3 border-t border-slate-100 pt-4 dark:border-slate-800" onsubmit={saveAllowance}>
						<div class="grid grid-cols-2 gap-3">
							<div>
								<label class="label" for="vd">{m.vacation_entitlement()}</label>
								<input id="vd" type="number" min="0" max="366" step="0.5" class="input" bind:value={allowance.days} />
							</div>
							<div>
								<label class="label" for="vc">{m.vacation_carried_over()}</label>
								<input id="vc" type="number" min="0" max="366" step="0.5" class="input" bind:value={allowance.carried_over} />
							</div>
						</div>
						{#if account.suggested_carry_over > 0 && allowance.carried_over !== account.suggested_carry_over}
							<button type="button" class="text-xs font-medium text-brand-600 hover:underline" onclick={() => (allowance.carried_over = account!.suggested_carry_over)}>
								{m.vacation_suggest_carry({ n: fmtDays(account.suggested_carry_over) })}
							</button>
						{/if}
						<div class="flex gap-2">
							<button class="btn-primary">{m.save()}</button>
							<button type="button" class="btn-ghost" onclick={() => (editAllowance = false)}>{m.cancel()}</button>
						</div>
					</form>
				{:else}
					<div class="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-sm dark:border-slate-800">
						<span class="muted">
							{m.vacation_entitlement()} {fmtDays(account.days)}{#if account.carried_over}&nbsp;+ {fmtDays(account.carried_over)} {m.vacation_carried_over()}{/if}
						</span>
						<button class="btn-ghost px-2 py-1 text-xs" onclick={startEditAllowance}><Pencil class="size-3.5" />{m.edit()}</button>
					</div>
					{#if !account.configured}
						<p class="mt-2 text-xs text-amber-700 dark:text-amber-400">{m.vacation_not_configured({ n: fmtDays(account.days) })}</p>
					{/if}
				{/if}
				{#if otherTotals.length}
					<div class="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800">
						<h3 class="mb-2 text-xs font-medium tracking-wide uppercase muted">{m.other_absences({ year })}</h3>
						<div class="grid grid-cols-2 gap-2">
							{#each otherTotals as [kind, n] (kind)}
								<div class="flex items-center justify-between rounded-xl px-3 py-2 text-sm {DAY_BADGE[kind]}">
									<span class="truncate">{dayKindLabel(kind)}</span>
									<span class="font-semibold tabular-nums">{n}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			{/if}
		</section>

		<!-- Add absence -->
		<form class="card space-y-4 lg:col-span-3" onsubmit={addAbsence}>
			<h2 class="section-title mb-1">{m.add_absence()}</h2>
			<div class="flex flex-wrap gap-1.5">
				{#each ABSENCE_KINDS as k (k)}
					<button
						type="button"
						class="rounded-full px-3 py-1.5 text-xs font-medium ring-1 transition {form.kind === k
							? `${DAY_BADGE[k]} ring-current`
							: 'ring-slate-200 text-slate-600 hover:bg-slate-50 dark:ring-slate-700 dark:text-slate-300 dark:hover:bg-slate-800'}"
						onclick={() => (form.kind = k)}
					>
						{dayKindLabel(k)}
					</button>
				{/each}
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<div>
					<label class="label" for="af">{m.date_from()}</label>
					<input id="af" type="date" class="input" bind:value={form.start} required />
				</div>
				<div>
					<label class="label" for="at">{m.date_to()}</label>
					<input id="at" type="date" class="input" bind:value={form.end} min={form.start} required />
				</div>
			</div>
			<div>
				<label class="label" for="an">{m.note()}</label>
				<input id="an" class="input" bind:value={form.note} maxlength="1000" />
			</div>

			<div class="min-h-10 rounded-xl bg-slate-50 px-3 py-2.5 text-sm dark:bg-slate-800/60">
				{#if preview}
					{#if preview.days.length === 0}
						<span class="text-amber-700 dark:text-amber-400">{m.absence_none()}</span>
					{:else}
						<span class="font-medium">
							{isVacation
								? preview.days.length === 1
									? preview.vacation_days === 1
										? m.absence_preview_one_one()
										: m.absence_preview_vacation_one({ days: fmtDays(preview.vacation_days) })
									: m.absence_preview_vacation({ workdays: preview.days.length, days: fmtDays(preview.vacation_days) })
								: workdaysText(preview.days.length)}
						</span>
						{#if afterBooking !== null && afterBooking < 0}
							<span class="block text-rose-600 dark:text-rose-400">{m.absence_over_budget({ n: fmtDays(afterBooking) })}</span>
						{/if}
					{/if}
				{/if}
				<span class="block text-xs muted">{m.absence_hint()}</span>
			</div>

			<div class="flex flex-wrap items-center gap-3">
				<button class="btn-primary" disabled={busy || !preview?.days.length}><Plus class="size-4" />{m.add_absence()}</button>
				{#if message}<Alert message={message.text} tone={message.tone} />{/if}
			</div>
		</form>
	</div>

	<section class="card">
		<h2 class="section-title">{m.year_overview()}</h2>
		<YearCalendar {year} {days} {today} onpick={(d) => (editing = d)} />
	</section>

	<CalendarSubscription />

	<section class="card">
		{#if periods.length === 0}
			<p class="text-sm muted">{m.no_absences()}</p>
		{/if}
		{#if upcoming.length}
			<h2 class="section-title mb-1">{m.upcoming()}</h2>
			<ul class="mb-4 divide-y divide-slate-100 dark:divide-slate-800">
				{#each upcoming as p (p.start + p.kind)}{@render periodRow(p)}{/each}
			</ul>
		{/if}
		{#if past.length}
			<h2 class="section-title mb-1">{m.past()}</h2>
			<ul class="divide-y divide-slate-100 dark:divide-slate-800">
				{#each past as p (p.start + p.kind)}{@render periodRow(p)}{/each}
			</ul>
		{/if}
	</section>
</div>

{#if editing}
	<DayEditor day={editing} {places} onclose={() => (editing = null)} onchange={load} />
{/if}
