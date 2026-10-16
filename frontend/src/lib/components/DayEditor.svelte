<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { addDays, formatDate, hm, localDate, localTime, zonedToIso } from '#lib/time.js';
	import type { Break, Commute, Day, DayKind, PendelEvent, Place, PlaceKind, WorkSession } from '#lib/types.js';
	import { DAY_KINDS, actionLabel, dayKindLabel } from '#lib/labels.js';
	import Modal from './Modal.svelte';
	import Alert from './Alert.svelte';
	import { Plus, Trash2, Car, Coffee, Radio, TriangleAlert, Zap } from '@lucide/svelte';

	let {
		day,
		places,
		onclose,
		onchange
	}: { day: Day; places: Place[]; onclose: () => void; onchange: () => void } = $props();

	const tz = $derived(auth.tz);
	let sessions = $state<WorkSession[]>([]);
	let commutes = $state<Commute[]>([]);
	let events = $state<PendelEvent[]>([]);
	let entry = $state<DayKind | ''>('');
	let error = $state<string | null>(null);

	async function load() {
		const range = { from: day.day, to: day.day };
		[sessions, commutes, events] = await Promise.all([
			api.get<WorkSession[]>('/sessions', range),
			api.get<Commute[]>('/commutes', range),
			api.get<PendelEvent[]>('/events', range)
		]);
	}

	$effect(() => {
		entry = day.entry ?? '';
		load();
	});

	async function run(fn: () => Promise<unknown>) {
		error = null;
		try {
			await fn();
			await load();
			onchange();
		} catch (e) {
			error = errorText(e);
		}
	}

	/** ISO for a HH:MM on this day; times before the start roll over to the next day. */
	function iso(time: string, after?: string): string {
		let date = day.day;
		if (after && time <= localTime(after, tz) && localDate(after, tz) === day.day) date = addDays(date, 1);
		return zonedToIso(date, time, tz);
	}

	const kinds: PlaceKind[] = ['home', 'office', 'other'];
	const kindLabel = (k: PlaceKind) =>
		k === 'home' ? m.kind_home() : k === 'office' ? m.kind_office() : m.kind_other();
	function setEntry() {
		run(() =>
			entry ? api.put(`/days/${day.day}`, { kind: entry, note: '' }) : api.del(`/days/${day.day}`)
		);
	}

	function addSession() {
		const kind: PlaceKind = 'office';
		const place = places.find((p) => p.kind === kind)?.id ?? null;
		run(() =>
			api.post('/sessions', {
				kind,
				place_id: place,
				start: zonedToIso(day.day, '08:00', tz),
				end: zonedToIso(day.day, '16:30', tz)
			})
		);
	}

	function patchSession(s: WorkSession, changes: Partial<WorkSession>) {
		run(() => api.patch(`/sessions/${s.id}`, changes));
	}

	function setKind(s: WorkSession, kind: PlaceKind) {
		patchSession(s, { kind, place_id: places.find((p) => p.kind === kind)?.id ?? null });
	}

	function addBreak(s: WorkSession) {
		const start = zonedToIso(day.day, '12:00', tz);
		const end = zonedToIso(day.day, '12:30', tz);
		run(() => api.post(`/sessions/${s.id}/breaks`, { start, end }));
	}

	function saveBreak(b: Break, changes: Partial<Break>) {
		const next = { ...b, ...changes };
		run(() =>
			api.put(`/breaks/${b.id}`, { start: next.start, end: next.end, deducted: next.deducted, note: next.note })
		);
	}

	function addCommute(direction: Commute['direction']) {
		const [a, b] = direction === 'to_work' ? ['07:30', '08:00'] : ['16:30', '17:00'];
		run(() =>
			api.post('/commutes', {
				direction,
				start: zonedToIso(day.day, a, tz),
				end: zonedToIso(day.day, b, tz)
			})
		);
	}

	function saveCommute(c: Commute, changes: Partial<Commute>) {
		const next = { ...c, ...changes };
		run(() =>
			api.put(`/commutes/${c.id}`, {
				direction: next.direction,
				start: next.start,
				end: next.end,
				from_place_id: next.from_place_id,
				to_place_id: next.to_place_id,
				note: next.note
			})
		);
	}

	const title = $derived(
		formatDate(day.day, getLocale(), { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
	);
</script>

{#snippet auto()}
	<span class="inline-flex items-center gap-1 rounded-md bg-brand-50 px-1.5 py-0.5 text-[10px] font-medium text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
		<Zap class="size-3" />{m.automatic()}
	</span>
{/snippet}

{#snippet times(start: string, end: string | null, save: (start: string, end: string | null) => void)}
	<div class="flex items-center gap-2">
		<input
			type="time"
			class="input w-auto px-2 py-1.5 tabular-nums"
			value={localTime(start, tz)}
			onchange={(e) => save(iso(e.currentTarget.value), end)}
		/>
		<span class="muted">–</span>
		{#if end}
			<input
				type="time"
				class="input w-auto px-2 py-1.5 tabular-nums"
				value={localTime(end, tz)}
				onchange={(e) => save(start, iso(e.currentTarget.value, start))}
			/>
		{:else}
			<span class="text-sm font-medium text-brand-600">{m.running()}</span>
		{/if}
	</div>
{/snippet}

<Modal {title} {onclose}>
	<div class="space-y-6">
		<div class="grid grid-cols-3 gap-2 text-center">
			<div class="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
				<div class="text-xs muted">{m.target()}</div>
				<div class="font-semibold tabular-nums">{hm(day.target)}</div>
			</div>
			<div class="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
				<div class="text-xs muted">{m.actual()}</div>
				<div class="font-semibold tabular-nums">{hm(day.actual)}</div>
			</div>
			<div class="rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
				<div class="text-xs muted">{m.difference()}</div>
				<div
					class="font-semibold tabular-nums {day.diff > 0
						? 'text-emerald-600'
						: day.diff < 0
							? 'text-rose-600'
							: ''}"
				>
					{day.diff > 0 ? '+' : ''}{hm(day.diff)}
				</div>
			</div>
		</div>

		<div>
			<label class="label" for="daykind">{m.day_type()}</label>
			<select id="daykind" class="input" bind:value={entry} onchange={setEntry}>
				<option value="">{day.holiday ? `${m.day_public_holiday()}: ${day.holiday}` : m.day_normal()}</option>
				{#each DAY_KINDS as k (k)}
					<option value={k}>{dayKindLabel(k)}</option>
				{/each}
			</select>
		</div>

		<section>
			<div class="mb-2 flex items-center justify-between">
				<h3 class="text-sm font-semibold">{m.work_sessions()}</h3>
				<button class="btn-ghost px-2 py-1 text-xs" onclick={addSession}>
					<Plus class="size-4" />{m.add_session()}
				</button>
			</div>
			<div class="space-y-3">
				{#each sessions as s (s.id)}
					<div class="rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
						<div class="flex flex-wrap items-center gap-2 p-3">
							<select
								class="input w-auto py-1.5"
								value={s.kind}
								onchange={(e) => setKind(s, e.currentTarget.value as PlaceKind)}
							>
								{#each kinds as k (k)}<option value={k}>{kindLabel(k)}</option>{/each}
							</select>
							{@render times(s.start, s.end, (start, end) => patchSession(s, { start, ...(end ? { end } : {}) }))}
							{#if s.source === 'automatic'}{@render auto()}{/if}
							<button
								class="btn-danger ml-auto p-1.5"
								aria-label={m.delete()}
								onclick={() => confirm(m.confirm_delete()) && run(() => api.del(`/sessions/${s.id}`))}
							>
								<Trash2 class="size-4" />
							</button>
						</div>
						{#if s.note.includes('[end_estimated]')}
							<p class="flex items-center gap-1.5 px-3 pb-2 text-xs text-amber-700 dark:text-amber-400">
								<TriangleAlert class="size-3.5" />{m.end_estimated()}
							</p>
						{/if}
						<div class="space-y-2 border-t border-slate-100 p-3 dark:border-slate-800">
							{#each s.breaks as b (b.id)}
								<div class="flex flex-wrap items-center gap-2 text-sm">
									<Coffee class="size-4 muted" />
									{@render times(b.start, b.end, (start, end) => saveBreak(b, { start, end }))}
									<label class="flex items-center gap-1.5 text-xs">
										<input
											type="checkbox"
											class="size-4 accent-brand-600"
											checked={b.deducted}
											onchange={(e) => saveBreak(b, { deducted: e.currentTarget.checked })}
										/>
										{m.counts_as_break()}
									</label>
									{#if b.kind === 'office_gap'}
										<span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] muted dark:bg-slate-800">{m.office_gap()}</span>
									{/if}
									<button
										class="btn-danger ml-auto p-1.5"
										aria-label={m.delete()}
										onclick={() => run(() => api.del(`/breaks/${b.id}`))}
									>
										<Trash2 class="size-4" />
									</button>
								</div>
							{/each}
							<button class="btn-ghost px-2 py-1 text-xs" onclick={() => addBreak(s)}>
								<Plus class="size-4" />{m.add_break()}
							</button>
						</div>
					</div>
				{/each}
			</div>
		</section>

		<section>
			<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
				<h3 class="text-sm font-semibold">{m.commute()}</h3>
				<div class="flex gap-1">
					<button class="btn-ghost px-2 py-1 text-xs" onclick={() => addCommute('to_work')}>
						<Plus class="size-4" />{m.commute_to_work()}
					</button>
					<button class="btn-ghost px-2 py-1 text-xs" onclick={() => addCommute('from_work')}>
						<Plus class="size-4" />{m.commute_from_work()}
					</button>
				</div>
			</div>
			<div class="space-y-2">
				{#each commutes as c (c.id)}
					<div class="flex flex-wrap items-center gap-2 rounded-2xl p-3 text-sm ring-1 ring-slate-200 dark:ring-slate-700">
						<Car class="size-4 text-travel" />
						<span class="w-20 font-medium">
							{c.direction === 'to_work' ? m.commute_to_work() : m.commute_from_work()}
						</span>
						{@render times(c.start, c.end, (start, end) => saveCommute(c, { start, end }))}
						{#if c.source === 'automatic'}{@render auto()}{/if}
						<button
							class="btn-danger ml-auto p-1.5"
							aria-label={m.delete()}
							onclick={() => run(() => api.del(`/commutes/${c.id}`))}
						>
							<Trash2 class="size-4" />
						</button>
					</div>
				{/each}
			</div>
		</section>

		{#if events.length}
			<section>
				<h3 class="mb-2 flex items-center gap-1.5 text-sm font-semibold"><Radio class="size-4" />{m.event_log()}</h3>
				<ul class="space-y-1 text-xs">
					{#each events as ev (ev.id)}
						<li class="flex gap-2">
							<span class="w-10 shrink-0 tabular-nums muted">{localTime(ev.occurred_at, tz)}</span>
							<span class="shrink-0 font-medium">
								{#if ev.type === 'device_active'}
									{m.event_device_active()}{ev.zone ? ` (${ev.zone})` : ''}
								{:else}
									{ev.zone} {ev.type === 'zone_enter' ? m.event_zone_enter() : m.event_zone_leave()}
								{/if}
							</span>
							<span class="muted">→ {(ev.payload.actions ?? []).map(actionLabel).join(', ')}</span>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<Alert message={error} />
	</div>
</Modal>
