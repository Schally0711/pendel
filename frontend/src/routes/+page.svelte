<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { clock, hm, localDate, localTime, minutesBetween, signedHm } from '#lib/time.js';
	import type { Commute, Place, PlaceKind, Segment, Today, WorkSession } from '#lib/types.js';
	import ProgressRing from '#lib/components/ProgressRing.svelte';
	import Timeline from '#lib/components/Timeline.svelte';
	import StatCard from '#lib/components/StatCard.svelte';
	import Alert from '#lib/components/Alert.svelte';
	import {
		Building2,
		Car,
		Coffee,
		House,
		Flag,
		Play,
		Scale,
		CalendarRange,
		TriangleAlert
	} from '@lucide/svelte';

	let today = $state<Today | null>(null);
	let sessions = $state<WorkSession[]>([]);
	let commutes = $state<Commute[]>([]);
	let places = $state<Place[]>([]);
	let fetchedAt = $state(Date.now());
	let now = $state(new Date());
	let busy = $state(false);
	let error = $state<string | null>(null);

	const tz = $derived(auth.tz);

	async function load() {
		const t = await api.get<Today>('/today');
		const day = localDate(t.now, tz);
		const range = { from: day, to: day };
		[sessions, commutes, places] = await Promise.all([
			api.get<WorkSession[]>('/sessions', range),
			api.get<Commute[]>('/commutes', range),
			places.length ? Promise.resolve(places) : api.get<Place[]>('/places')
		]);
		today = t;
		fetchedAt = Date.now();
	}

	onMount(() => {
		load();
		const tick = setInterval(() => (now = new Date()), 1000);
		const refresh = setInterval(load, 60_000);
		const onVisible = () => document.visibilityState === 'visible' && load();
		document.addEventListener('visibilitychange', onVisible);
		return () => {
			clearInterval(tick);
			clearInterval(refresh);
			document.removeEventListener('visibilitychange', onVisible);
		};
	});

	async function act(path: string, body: object = {}) {
		busy = true;
		error = null;
		try {
			await api.post(path, body);
			await load();
		} catch (e) {
			error = errorText(e);
		} finally {
			busy = false;
		}
	}

	const placeOf = (kind: PlaceKind) => places.find((p) => p.kind === kind && !p.archived)?.id ?? null;
	const startWork = (kind: PlaceKind) => act('/clock/start', { kind, place_id: placeOf(kind) });

	// Live values between server refreshes
	const working = $derived(!!today?.running_session && !today.running_break);
	const liveExtra = $derived(working ? (now.getTime() - fetchedAt) / 60000 : 0);
	const actual = $derived((today?.day.actual ?? 0) + liveExtra);
	const target = $derived(today?.day.target ?? 0);
	const balance = $derived((today?.balance_before_today ?? 0) + actual - target);

	type State = 'idle' | 'working' | 'break' | 'commute';
	const status: State = $derived(
		today?.running_commute
			? 'commute'
			: today?.running_break
				? 'break'
				: today?.running_session
					? 'working'
					: 'idle'
	);

	const statusText = $derived.by(() => {
		if (!today) return '';
		if (status === 'commute')
			return today.running_commute?.direction === 'to_work'
				? m.status_commute_to_work()
				: m.status_commute_from_work();
		if (status === 'break') return m.status_break();
		if (status === 'working') {
			const k = today.running_session?.kind;
			return k === 'home'
				? m.status_working_home()
				: k === 'office'
					? m.status_working_office()
					: m.status_working_other();
		}
		return m.status_idle();
	});

	const since = $derived(
		today?.running_commute?.start ?? today?.running_break?.start ?? today?.running_session?.start ?? null
	);

	const greeting = $derived.by(() => {
		const h = Number(localTime(now, tz).slice(0, 2));
		const name = auth.user?.display_name ?? '';
		return h < 11
			? m.greeting_morning({ name })
			: h < 18
				? m.greeting_day({ name })
				: m.greeting_evening({ name });
	});

	const dateLabel = $derived(
		new Intl.DateTimeFormat(getLocale(), {
			weekday: 'long',
			day: 'numeric',
			month: 'long',
			timeZone: tz
		}).format(now)
	);

	const segments: Segment[] = $derived([
		...commutes.map((c) => ({ start: c.start, end: c.end, type: 'travel' as const })),
		...sessions.map((s) => ({ start: s.start, end: s.end, type: s.kind })),
		...sessions.flatMap((s) =>
			s.breaks
				.filter((b) => b.deducted)
				.map((b) => ({ start: b.start, end: b.end, type: 'break' as const }))
		)
	]);

	const KIND_LABEL = $derived({ home: m.kind_home(), office: m.kind_office(), other: m.kind_other() });
	const KIND_DOT = { home: 'bg-home', office: 'bg-office', other: 'bg-brand-500' };

	type Entry = { start: string; end: string | null; label: string; minutes: number; dot: string };
	const entries: Entry[] = $derived(
		[
			...commutes.map((c) => ({
				start: c.start,
				end: c.end,
				label: c.direction === 'to_work' ? m.commute_to_work() : m.commute_from_work(),
				minutes: minutesBetween(c.start, c.end, now),
				dot: 'bg-travel'
			})),
			...sessions.map((s) => ({
				start: s.start,
				end: s.end,
				label: KIND_LABEL[s.kind],
				minutes: minutesBetween(s.start, s.end, now),
				dot: KIND_DOT[s.kind]
			})),
			...sessions.flatMap((s) =>
				s.breaks.map((b) => ({
					start: b.start,
					end: b.end,
					label: b.deducted ? m.start_break() : m.customer_visit(),
					minutes: minutesBetween(b.start, b.end, now),
					dot: 'bg-slate-300 dark:bg-slate-600'
				}))
			)
		].sort((a, b) => a.start.localeCompare(b.start))
	);

	const warnings = $derived(
		(today?.day.warnings ?? []).map((w) =>
			w === 'break_too_short' ? m.warning_break_too_short() : m.warning_max_work_exceeded()
		)
	);

	const pill: Record<State, string> = {
		idle: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
		working: 'bg-brand-100 text-brand-800 dark:bg-brand-900/50 dark:text-brand-200',
		break: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
		commute: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300'
	};
</script>

<div class="space-y-6">
	<div>
		<h1 class="text-2xl font-semibold tracking-tight">{greeting}</h1>
		<p class="muted">{dateLabel}</p>
	</div>

	{#if !today}
		<div class="card muted">{m.loading()}</div>
	{:else}
		<div class="grid gap-6 lg:grid-cols-5">
			<section class="card flex flex-col items-center gap-6 p-6 lg:col-span-3">
				<div class="flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium {pill[status]}">
					<span class="relative flex size-2">
						{#if status !== 'idle'}
							<span class="absolute inline-flex size-full animate-ping rounded-full bg-current opacity-60"
							></span>
						{/if}
						<span class="relative inline-flex size-2 rounded-full bg-current"></span>
					</span>
					{statusText}
					{#if since}<span class="opacity-70">· {m.since({ time: localTime(since, tz) })}</span>{/if}
				</div>

				<ProgressRing value={actual} max={target}>
					<div class="text-xs font-medium tracking-wide uppercase muted">{m.today_worked()}</div>
					<div class="mt-1 text-5xl font-semibold tracking-tight tabular-nums">
						{working ? clock(actual) : hm(actual)}
					</div>
					<div class="mt-1 text-sm muted">
						{#if target === 0}
							{today.day.holiday ?? m.no_target_today()}
						{:else if actual >= target}
							{m.target_reached()}
						{:else}
							{m.of_target({ target: hm(target) })}
						{/if}
					</div>
				</ProgressRing>

				{#if status === 'working' && target > actual}
					<p class="-mt-2 text-sm muted">{m.remaining({ time: hm(target - actual) })}</p>
				{/if}

				<div class="grid w-full max-w-md gap-3">
					{#if status === 'idle'}
						<div class="grid grid-cols-2 gap-3">
							<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => startWork('home')}>
								<House class="size-5" />{m.start_home()}
							</button>
							<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => startWork('office')}>
								<Building2 class="size-5" />{m.start_office()}
							</button>
						</div>
						<button
							class="btn-secondary"
							disabled={busy}
							onclick={() => act('/clock/commute/start', { direction: 'to_work' })}
						>
							<Car class="size-4" />{m.start_commute()}
						</button>
					{:else if status === 'working'}
						<div class="grid grid-cols-2 gap-3">
							<button class="btn-secondary py-4 text-base" disabled={busy} onclick={() => act('/clock/break/start')}>
								<Coffee class="size-5" />{m.start_break()}
							</button>
							<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => act('/clock/stop')}>
								<Flag class="size-5" />{m.stop_work()}
							</button>
						</div>
						{#if today.running_session?.kind === 'office'}
							<button
								class="btn-secondary"
								disabled={busy}
								onclick={() => act('/clock/commute/start', { direction: 'from_work' })}
							>
								<Car class="size-4" />{m.go_home()}
							</button>
						{/if}
					{:else if status === 'break'}
						<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => act('/clock/break/stop')}>
							<Play class="size-5" />{m.end_break()}
						</button>
					{:else if today.running_commute?.direction === 'to_work'}
						<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => startWork('office')}>
							<Building2 class="size-5" />{m.arrived_office()}
						</button>
					{:else}
						<button class="btn-primary py-4 text-base" disabled={busy} onclick={() => act('/clock/commute/stop')}>
							<House class="size-5" />{m.arrived_home()}
						</button>
					{/if}
					<Alert message={error} />
				</div>
			</section>

			<section class="grid content-start gap-4 sm:grid-cols-2 lg:col-span-2 lg:grid-cols-1">
				<StatCard
					label={m.balance()}
					value={signedHm(balance)}
					icon={Scale}
					tone={Math.round(balance) > 0 ? 'positive' : Math.round(balance) < 0 ? 'negative' : 'neutral'}
				/>
				<StatCard
					label={m.this_week()}
					value={hm(today.week_actual + liveExtra)}
					sub={m.of_target({ target: hm(today.week_target) })}
					icon={CalendarRange}
				/>
				<StatCard
					label={m.breaks()}
					value={hm(today.day.breaks_effective)}
					sub={today.day.breaks_effective > today.day.breaks_recorded ? m.auto_break_applied() : ''}
					icon={Coffee}
				/>
				<StatCard label={m.commute()} value={hm(today.day.commute)} icon={Car} />
			</section>
		</div>

		{#each warnings as w (w)}
			<div
				class="flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
			>
				<TriangleAlert class="size-4 shrink-0" />{w}
			</div>
		{/each}

		<section class="card">
			<h2 class="section-title">{m.today_entries()}</h2>
			{#if entries.length === 0}
				<p class="text-sm muted">{m.no_entries()}</p>
			{:else}
				<Timeline {segments} {tz} {now} />
				<ul class="mt-4 divide-y divide-slate-100 dark:divide-slate-800">
					{#each entries as e, i (i)}
						<li class="flex items-center gap-3 py-2.5 text-sm">
							<span class="size-2.5 shrink-0 rounded-full {e.dot}"></span>
							<span class="font-medium">{e.label}</span>
							<span class="muted tabular-nums">
								{localTime(e.start, tz)} – {e.end ? localTime(e.end, tz) : m.running()}
							</span>
							<span class="ml-auto font-medium tabular-nums">{hm(e.minutes)}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/if}
</div>
