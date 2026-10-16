<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { addDays, formatDate, localDate, signedHm } from '#lib/time.js';
	import type { Employment } from '#lib/types.js';
	import Alert from './Alert.svelte';
	import Modal from './Modal.svelte';
	import { ArrowRightLeft, Briefcase, Pencil, Trash2 } from '@lucide/svelte';

	let { onchange }: { onchange?: () => void } = $props();

	let list = $state<Employment[]>([]);
	let error = $state<string | null>(null);
	let editing = $state<Employment | null>(null);
	let switching = $state(false);
	let busy = $state(false);

	const today = localDate(new Date(), auth.tz);
	let sw = $state({ employer: '', start: today, previous_end: addDays(today, -1), vacation_days: '' as string | number });
	let endTouched = $state(false);

	const load = async () => (list = await api.get<Employment[]>('/employments'));
	onMount(load);

	const fmt = (d: string) => formatDate(d, getLocale(), { dateStyle: 'medium' });
	const name = (e: Employment) => e.employer || m.employer_unnamed();

	async function run(action: () => Promise<unknown>, close: () => void) {
		busy = true;
		error = null;
		try {
			await action();
			close();
			await load();
			onchange?.();
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	function openSwitch() {
		sw = { employer: '', start: today, previous_end: addDays(today, -1), vacation_days: '' };
		endTouched = false;
		error = null;
		switching = true;
	}

	function saveSwitch(e: SubmitEvent) {
		e.preventDefault();
		const days = sw.vacation_days === '' ? null : Number(sw.vacation_days);
		run(
			() => api.post('/employments/switch', { ...sw, vacation_days: days }),
			() => (switching = false)
		);
	}

	function saveEdit(e: SubmitEvent) {
		e.preventDefault();
		const x = editing!;
		run(
			() => api.put(`/employments/${x.id}`, { employer: x.employer, start: x.start, end: x.end || null, note: x.note }),
			() => (editing = null)
		);
	}

	function remove(e: Employment) {
		const text = m.delete_employment_confirm({ name: name(e), start: fmt(e.start), end: fmt(e.end!) });
		if (confirm(text)) run(() => api.del(`/employments/${e.id}`), () => {});
	}
</script>

<section class="card">
	<div class="mb-4 flex flex-wrap items-start justify-between gap-3">
		<div>
			<h2 class="section-title mb-1">{m.employments()}</h2>
			<p class="text-sm muted">{m.employments_text()}</p>
		</div>
		<button class="btn-secondary" onclick={openSwitch}><ArrowRightLeft class="size-4" />{m.change_job()}</button>
	</div>

	<ul class="divide-y divide-slate-100 dark:divide-slate-800">
		{#each [...list].reverse() as e (e.id)}
			<li class="flex items-center gap-3 py-2.5 text-sm">
				<span
					class="grid size-8 shrink-0 place-items-center rounded-full {e.current
						? 'bg-brand-100 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300'
						: 'bg-slate-100 text-slate-500 dark:bg-slate-800'}"
				>
					<Briefcase class="size-4" />
				</span>
				<span class="min-w-0 flex-1">
					<span class="flex items-center gap-2">
						<span class="truncate font-medium">{name(e)}</span>
						{#if e.current}
							<span class="rounded-md bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">{m.employment_current()}</span>
						{/if}
					</span>
					<span class="block truncate text-xs muted">
						{e.end ? `${fmt(e.start)} – ${fmt(e.end)}` : m.employment_since({ date: fmt(e.start) })}
					</span>
				</span>
				<span class="text-right">
					<span class="block text-xs muted">{m.employment_balance()}</span>
					<span class="font-medium tabular-nums">{signedHm(e.balance)}</span>
				</span>
				<button class="btn-ghost p-1.5" aria-label={m.edit()} onclick={() => ((editing = { ...e }), (error = null))}>
					<Pencil class="size-4" />
				</button>
				{#if e.end && !e.current && list.some((x) => x.start > e.end!)}
					<button class="btn-danger p-1.5" aria-label={m.delete()} onclick={() => remove(e)}>
						<Trash2 class="size-4" />
					</button>
				{/if}
			</li>
		{/each}
	</ul>
	{#if !editing && !switching}<div class="mt-2"><Alert message={error} /></div>{/if}
</section>

{#if switching}
	<Modal title={m.change_job()} onclose={() => (switching = false)}>
		<form class="space-y-4" onsubmit={saveSwitch}>
			<p class="text-sm muted">{m.change_job_text()}</p>
			<div>
				<label class="label" for="sw-employer">{m.new_employer()}</label>
				<input id="sw-employer" class="input" bind:value={sw.employer} maxlength="100" />
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<div>
					<label class="label" for="sw-start">{m.new_start()}</label>
					<input
						id="sw-start"
						type="date"
						class="input"
						bind:value={sw.start}
						required
						oninput={() => !endTouched && sw.start && (sw.previous_end = addDays(sw.start, -1))}
					/>
				</div>
				<div>
					<label class="label" for="sw-end">{m.previous_end()}</label>
					<input
						id="sw-end"
						type="date"
						class="input"
						bind:value={sw.previous_end}
						max={sw.start ? addDays(sw.start, -1) : undefined}
						required
						oninput={() => (endTouched = true)}
					/>
				</div>
			</div>
			<div>
				<label class="label" for="sw-vac">{m.vacation_days_year({ year: (sw.start || today).slice(0, 4) })}</label>
				<input id="sw-vac" type="number" min="0" max="366" step="0.5" class="input sm:w-40" bind:value={sw.vacation_days} />
				<p class="mt-1.5 text-xs muted">{m.vacation_days_hint()}</p>
			</div>
			<Alert message={error} />
			<div class="flex justify-end gap-2">
				<button type="button" class="btn-ghost" onclick={() => (switching = false)}>{m.cancel()}</button>
				<button class="btn-primary" disabled={busy}>{m.change_job_button()}</button>
			</div>
		</form>
	</Modal>
{/if}

{#if editing}
	<Modal title={name(editing)} onclose={() => (editing = null)}>
		<form class="space-y-4" onsubmit={saveEdit}>
			<div>
				<label class="label" for="em-employer">{m.employer()}</label>
				<input id="em-employer" class="input" bind:value={editing.employer} maxlength="100" />
			</div>
			<div class="grid gap-4 sm:grid-cols-2">
				<div>
					<label class="label" for="em-start">{m.start()}</label>
					<input id="em-start" type="date" class="input" bind:value={editing.start} required />
				</div>
				<div>
					<label class="label" for="em-end">{m.end()}</label>
					<input id="em-end" type="date" class="input" bind:value={editing.end} min={editing.start} />
				</div>
			</div>
			<p class="text-xs muted">{m.employment_start_hint()}</p>
			<div>
				<label class="label" for="em-note">{m.note()}</label>
				<input id="em-note" class="input" bind:value={editing.note} maxlength="1000" />
			</div>
			<Alert message={error} />
			<div class="flex justify-end gap-2">
				<button type="button" class="btn-ghost" onclick={() => (editing = null)}>{m.cancel()}</button>
				<button class="btn-primary" disabled={busy}>{m.save()}</button>
			</div>
		</form>
	</Modal>
{/if}
