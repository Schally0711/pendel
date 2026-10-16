<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { formatDate, localDate, signedHm } from '#lib/time.js';
	import type { Adjustment, Place, PlaceKind, Subdivision, User, WorkModel } from '#lib/types.js';
	import Alert from '#lib/components/Alert.svelte';
	import Integrations from '#lib/components/Integrations.svelte';
	import { Plus, Trash2, Users } from '@lucide/svelte';

	type Status = { message: string | null; tone: 'error' | 'success' };
	const status = $state<Record<string, Status>>({});
	function ok(key: string) {
		status[key] = { message: m.saved(), tone: 'success' };
		setTimeout(() => (status[key] = { message: null, tone: 'success' }), 2500);
	}
	function fail(key: string, e: unknown) {
		status[key] = { message: errorText(e), tone: 'error' };
	}

	// --- profile ---
	let profile = $state({ display_name: '', locale: 'de', subdivision: '', timezone: '' });
	let subdivisions = $state<Subdivision[]>([]);

	async function saveProfile(e: SubmitEvent) {
		e.preventDefault();
		try {
			const u = await api.patch<User>('/me', profile);
			auth.set(u);
			if (u.locale !== getLocale()) setLocale(u.locale);
			ok('profile');
		} catch (err) {
			fail('profile', err);
		}
	}

	// --- work models ---
	let models = $state<WorkModel[]>([]);
	let selected = $state(0);
	const model = $derived(models[selected]);
	const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;
	const dayName = (i: number) => formatDate(`2026-01-${String(5 + i).padStart(2, '0')}`, getLocale(), { weekday: 'short' });
	const weekly = $derived(model ? DAYS.reduce((s, d) => s + model[`target_${d}`], 0) / 60 : 0);

	async function loadModels(selectId?: number) {
		models = await api.get<WorkModel[]>('/work-models');
		const idx = selectId ? models.findIndex((x) => x.id === selectId) : models.length - 1;
		selected = Math.max(idx, 0);
	}

	async function saveModel(e: SubmitEvent) {
		e.preventDefault();
		try {
			const saved = model.id
				? await api.put<WorkModel>(`/work-models/${model.id}`, model)
				: await api.post<WorkModel>('/work-models', model);
			await loadModels(saved.id);
			ok('model');
		} catch (err) {
			fail('model', err);
		}
	}

	function newModel() {
		const { id: _id, ...rest } = model;
		models.push({ ...rest, valid_from: localDate(new Date(), auth.tz), name: '' });
		selected = models.length - 1;
	}

	async function deleteModel() {
		if (!model.id) {
			models.splice(selected, 1);
			selected = models.length - 1;
			return;
		}
		if (!confirm(m.confirm_delete())) return;
		try {
			await api.del(`/work-models/${model.id}`);
			await loadModels();
		} catch (err) {
			fail('model', err);
		}
	}

	// --- places ---
	let places = $state<Place[]>([]);
	const placeKinds: PlaceKind[] = ['home', 'office', 'other'];
	const kindLabel = (k: PlaceKind) => (k === 'home' ? m.kind_home() : k === 'office' ? m.kind_office() : m.kind_other());

	async function savePlace(p: Place) {
		try {
			const { id, ...body } = p;
			await api.put(`/places/${id}`, body);
			ok('places');
		} catch (err) {
			fail('places', err);
		}
	}
	async function addPlace() {
		places.push(await api.post<Place>('/places', { name: m.kind_office(), kind: 'office' }));
	}
	async function deletePlace(p: Place) {
		if (!confirm(m.confirm_delete())) return;
		await api.del(`/places/${p.id}`);
		places = places.filter((x) => x.id !== p.id);
	}

	// --- adjustments ---
	let adjustments = $state<Adjustment[]>([]);
	let newAdj = $state({ day: '', hours: 0, note: '' });
	async function addAdjustment(e: SubmitEvent) {
		e.preventDefault();
		try {
			const a = await api.post<Adjustment>('/adjustments', {
				day: newAdj.day,
				minutes: Math.round(newAdj.hours * 60),
				note: newAdj.note
			});
			adjustments.push(a);
			newAdj = { day: newAdj.day, hours: 0, note: '' };
		} catch (err) {
			fail('adjustments', err);
		}
	}
	async function deleteAdjustment(a: Adjustment) {
		await api.del(`/adjustments/${a.id}`);
		adjustments = adjustments.filter((x) => x.id !== a.id);
	}

	// --- password ---
	let pw = $state({ current_password: '', new_password: '' });
	async function changePassword(e: SubmitEvent) {
		e.preventDefault();
		try {
			await api.post('/me/password', pw);
			pw = { current_password: '', new_password: '' };
			ok('password');
		} catch (err) {
			fail('password', err);
		}
	}

	onMount(async () => {
		const u = auth.user!;
		profile = { display_name: u.display_name, locale: u.locale, subdivision: u.subdivision ?? '', timezone: u.timezone };
		newAdj.day = localDate(new Date(), auth.tz);
		[subdivisions, places, adjustments] = await Promise.all([
			api.get<Subdivision[]>('/meta/subdivisions'),
			api.get<Place[]>('/places'),
			api.get<Adjustment[]>('/adjustments')
		]);
		await loadModels();
	});

	const timezones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
</script>

{#snippet toggle(label: string, checked: boolean, set: (v: boolean) => void)}
	<label class="flex cursor-pointer items-center justify-between gap-4 py-1 text-sm">
		<span>{label}</span>
		<input type="checkbox" class="peer sr-only" {checked} onchange={(e) => set(e.currentTarget.checked)} />
		<span
			class="relative h-6 w-11 shrink-0 rounded-full bg-slate-300 transition peer-checked:bg-brand-600 peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500 after:absolute after:top-0.5 after:left-0.5 after:size-5 after:rounded-full after:bg-white after:shadow after:transition peer-checked:after:translate-x-5 dark:bg-slate-700"
		></span>
	</label>
{/snippet}

<div class="space-y-6">
	<div class="flex items-center justify-between gap-3">
		<h1 class="text-2xl font-semibold tracking-tight">{m.settings_title()}</h1>
		{#if auth.user?.is_admin}
			<a href="/admin" class="btn-secondary md:hidden"><Users class="size-4" />{m.nav_admin()}</a>
		{/if}
	</div>

	<!-- Profile -->
	<form class="card space-y-4" onsubmit={saveProfile}>
		<h2 class="section-title">{m.profile()}</h2>
		<div class="grid gap-4 sm:grid-cols-2">
			<div>
				<label class="label" for="name">{m.display_name()}</label>
				<input id="name" class="input" bind:value={profile.display_name} required />
			</div>
			<div>
				<label class="label" for="locale">{m.language()}</label>
				<select id="locale" class="input" bind:value={profile.locale}>
					<option value="de">Deutsch</option>
					<option value="en">English</option>
				</select>
			</div>
			<div>
				<label class="label" for="state">{m.state()}</label>
				<select id="state" class="input" bind:value={profile.subdivision}>
					{#each subdivisions as s (s.code)}<option value={s.code}>{s.name}</option>{/each}
				</select>
			</div>
			<div>
				<label class="label" for="tz">{m.timezone()}</label>
				<select id="tz" class="input" bind:value={profile.timezone}>
					{#each timezones as t (t)}<option value={t}>{t}</option>{/each}
				</select>
			</div>
		</div>
		<div class="flex items-center gap-3">
			<button class="btn-primary">{m.save()}</button>
			<Alert message={status.profile?.message ?? null} tone={status.profile?.tone} />
		</div>
	</form>

	<!-- Work model -->
	{#if model}
		<form class="card space-y-5" onsubmit={saveModel}>
			<div class="flex flex-wrap items-start justify-between gap-3">
				<div>
					<h2 class="section-title mb-1">{m.work_model()}</h2>
					<p class="max-w-prose text-sm muted">{m.work_model_text()}</p>
				</div>
				{#if models.length > 1}
					<select class="input w-auto" bind:value={selected}>
						{#each models as wm, i (i)}
							<option value={i}>{m.valid_from()} {formatDate(wm.valid_from, getLocale(), { dateStyle: 'medium' })}{wm.name ? ` · ${wm.name}` : ''}</option>
						{/each}
					</select>
				{/if}
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<div>
					<label class="label" for="valid_from">{m.valid_from()}</label>
					<input id="valid_from" type="date" class="input" bind:value={model.valid_from} required />
				</div>
				<div>
					<label class="label" for="mname">{m.model_name()}</label>
					<input id="mname" class="input" bind:value={model.name} />
				</div>
			</div>

			<div>
				<div class="mb-1.5 flex items-baseline justify-between">
					<span class="label mb-0">{m.hours_per_day()}</span>
					<span class="text-sm font-medium text-brand-700 dark:text-brand-400">
						{m.weekly_hours({ hours: weekly.toLocaleString(getLocale(), { maximumFractionDigits: 2 }) })}
					</span>
				</div>
				<div class="grid grid-cols-7 gap-1.5">
					{#each DAYS as d, i (d)}
						<label class="text-center">
							<span class="mb-1 block text-xs muted">{dayName(i)}</span>
							<input
								type="number"
								min="0"
								max="24"
								step="0.25"
								class="input px-1 text-center tabular-nums"
								value={model[`target_${d}`] / 60}
								oninput={(e) => (model[`target_${d}`] = Math.round(Number(e.currentTarget.value) * 60))}
							/>
						</label>
					{/each}
				</div>
			</div>

			{@render toggle(m.flexitime(), model.flexitime, (v) => (model.flexitime = v))}

			<div class="space-y-3 rounded-2xl bg-slate-50 p-4 dark:bg-slate-800/50">
				<div class="label">{m.break_rule()}</div>
				<div class="grid gap-2 sm:grid-cols-2">
					{#each [['manual', m.break_mode_manual()], ['auto', m.break_mode_auto()]] as [value, label] (value)}
						<label
							class="flex cursor-pointer items-center gap-2 rounded-xl bg-white p-3 text-sm ring-1 ring-slate-200 has-checked:ring-2 has-checked:ring-brand-500 dark:bg-slate-900 dark:ring-slate-700"
						>
							<input type="radio" class="accent-brand-600" bind:group={model.break_mode} {value} />
							{label}
						</label>
					{/each}
				</div>
				{#if model.break_mode === 'auto'}
					<div class="grid gap-4 sm:grid-cols-2">
						<div>
							<label class="label" for="abm">{m.auto_break_minutes()}</label>
							<input id="abm" type="number" min="0" max="480" class="input" bind:value={model.auto_break_minutes} />
						</div>
						<div>
							<label class="label" for="abw">{m.auto_break_min_work()}</label>
							<input id="abw" type="number" min="0" max="1440" class="input" bind:value={model.auto_break_min_work_minutes} />
						</div>
					</div>
				{/if}
				<div>
					<label class="label" for="gap">{m.office_gap_max()}</label>
					<input id="gap" type="number" min="0" max="1440" class="input sm:w-40" bind:value={model.office_gap_break_max_minutes} />
					<p class="mt-1 text-xs muted">{m.office_gap_help()}</p>
				</div>
				{@render toggle(m.legal_break_check(), model.legal_break_check, (v) => (model.legal_break_check = v))}
			</div>

			<div>
				<label class="label" for="cc">{m.commute_credit()}</label>
				<div class="flex items-center gap-3">
					<input id="cc" type="range" min="0" max="100" step="5" class="flex-1 accent-brand-600" bind:value={model.commute_credit_percent} />
					<span class="w-12 text-right text-sm font-medium tabular-nums">{model.commute_credit_percent} %</span>
				</div>
			</div>

			<div class="flex flex-wrap items-center gap-3">
				<button class="btn-primary">{m.save()}</button>
				<button type="button" class="btn-secondary" onclick={newModel}><Plus class="size-4" />{m.new_model()}</button>
				{#if models.length > 1 || !model.id}
					<button type="button" class="btn-danger" onclick={deleteModel}><Trash2 class="size-4" />{m.delete()}</button>
				{/if}
				<Alert message={status.model?.message ?? null} tone={status.model?.tone} />
			</div>
		</form>
	{/if}

	<!-- Places -->
	<section class="card">
		<h2 class="section-title">{m.places()}</h2>
		<div class="space-y-3">
			{#each places as p (p.id)}
				<div class="grid gap-2 rounded-2xl p-3 ring-1 ring-slate-200 sm:grid-cols-[1fr_9rem_8rem_1fr_auto] sm:items-end dark:ring-slate-700">
					<div>
						<label class="label" for="pn{p.id}">{m.place_name()}</label>
						<input id="pn{p.id}" class="input" bind:value={p.name} onchange={() => savePlace(p)} />
					</div>
					<div>
						<label class="label" for="pk{p.id}">{m.place_kind()}</label>
						<select id="pk{p.id}" class="input" bind:value={p.kind} onchange={() => savePlace(p)}>
							{#each placeKinds as k (k)}<option value={k}>{kindLabel(k)}</option>{/each}
						</select>
					</div>
					<div>
						<label class="label" for="pd{p.id}">km</label>
						<input
							id="pd{p.id}"
							type="number"
							min="0"
							step="0.1"
							class="input"
							value={p.distance_km ?? ''}
							onchange={(e) => {
								p.distance_km = e.currentTarget.value === '' ? null : Number(e.currentTarget.value);
								savePlace(p);
							}}
						/>
					</div>
					<div>
						<label class="label" for="pz{p.id}">{m.zone()}</label>
						<input
							id="pz{p.id}"
							class="input"
							placeholder={p.kind === 'home' ? 'home' : 'Arbeit'}
							title={m.zone_hint()}
							value={p.zone ?? ''}
							onchange={(e) => {
								p.zone = e.currentTarget.value || null;
								savePlace(p);
							}}
						/>
					</div>
					<button class="btn-danger p-2.5" aria-label={m.delete()} onclick={() => deletePlace(p)}>
						<Trash2 class="size-4" />
					</button>
				</div>
			{/each}
		</div>
		<div class="mt-3 flex items-center gap-3">
			<button class="btn-secondary" onclick={addPlace}><Plus class="size-4" />{m.add_place()}</button>
			<Alert message={status.places?.message ?? null} tone={status.places?.tone} />
		</div>
	</section>

	<Integrations />

	<!-- Adjustments -->
	<section class="card">
		<h2 class="section-title mb-1">{m.adjustments()}</h2>
		<p class="mb-4 text-sm muted">{m.adjustments_text()}</p>
		{#if adjustments.length}
			<ul class="mb-4 divide-y divide-slate-100 dark:divide-slate-800">
				{#each adjustments as a (a.id)}
					<li class="flex items-center gap-3 py-2 text-sm">
						<span class="w-28 tabular-nums">{formatDate(a.day, getLocale(), { dateStyle: 'medium' })}</span>
						<span class="w-20 font-medium tabular-nums">{signedHm(a.minutes)}</span>
						<span class="flex-1 truncate muted">{a.note}</span>
						<button class="btn-danger p-1.5" aria-label={m.delete()} onclick={() => deleteAdjustment(a)}>
							<Trash2 class="size-4" />
						</button>
					</li>
				{/each}
			</ul>
		{/if}
		<form class="grid gap-2 sm:grid-cols-[10rem_8rem_1fr_auto] sm:items-end" onsubmit={addAdjustment}>
			<div>
				<label class="label" for="ad">{m.day()}</label>
				<input id="ad" type="date" class="input" bind:value={newAdj.day} required />
			</div>
			<div>
				<label class="label" for="ah">{m.hours()}</label>
				<input id="ah" type="number" step="0.25" class="input" bind:value={newAdj.hours} required />
			</div>
			<div>
				<label class="label" for="an">{m.note()}</label>
				<input id="an" class="input" bind:value={newAdj.note} />
			</div>
			<button class="btn-secondary"><Plus class="size-4" />{m.add_adjustment()}</button>
		</form>
		<div class="mt-2"><Alert message={status.adjustments?.message ?? null} tone={status.adjustments?.tone} /></div>
	</section>

	<!-- Password -->
	<form class="card space-y-4" onsubmit={changePassword}>
		<h2 class="section-title">{m.change_password()}</h2>
		<div class="grid gap-4 sm:grid-cols-2">
			<div>
				<label class="label" for="cpw">{m.current_password()}</label>
				<input id="cpw" type="password" class="input" bind:value={pw.current_password} required autocomplete="current-password" />
			</div>
			<div>
				<label class="label" for="npw">{m.new_password()}</label>
				<input id="npw" type="password" class="input" bind:value={pw.new_password} required minlength="10" autocomplete="new-password" />
			</div>
		</div>
		<div class="flex items-center gap-3">
			<button class="btn-primary">{m.save()}</button>
			<Alert message={status.password?.message ?? null} tone={status.password?.tone} />
		</div>
	</form>
</div>
