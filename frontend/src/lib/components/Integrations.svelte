<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { ApiTokenInfo, Place } from '#lib/types.js';
	import { renderSVG } from 'uqr';
	import { instance } from '#lib/instance.svelte.js';
	import Alert from './Alert.svelte';
	import { Check, Copy, House, KeyRound, MapPin, Plus, Smartphone, Trash2 } from '@lucide/svelte';

	let tokens = $state<ApiTokenInfo[]>([]);
	let name = $state('');
	let created = $state<string | null>(null);
	let copied = $state<string | null>(null);
	let error = $state<string | null>(null);

	let places = $state<Place[]>([]);
	const load = async () => (tokens = await api.get<ApiTokenInfo[]>('/tokens'));
	onMount(() => {
		load();
		instance.load();
		api.get<Place[]>('/places').then((p) => (places = p.filter((x) => !x.archived && x.kind !== 'other')));
	});

	// --- OwnTracks: a token of its own, handed over as remote configuration (QR code / link) ---
	let otToken = $state<string | null>(null);
	let otError = $state<string | null>(null);
	async function createOwnTracks() {
		otError = null;
		try {
			otToken = (await api.post<ApiTokenInfo>('/tokens', { name: 'OwnTracks' })).token ?? null;
			await load();
		} catch (err) {
			otError = errorText(err);
		}
	}
	const otUrl = $derived(`${instance.baseUrl}/api/owntracks`);
	// OwnTracks remote configuration: mode 3 = HTTP, user name is ignored by Pendel
	const otConfigLink = $derived.by(() => {
		if (!otToken) return '';
		const config = {
			_type: 'configuration',
			mode: 3,
			url: otUrl,
			auth: true,
			username: 'pendel',
			password: otToken,
			deviceId: 'pendel',
			tid: 'PD',
			monitoring: 1
		};
		const inline = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(config))));
		return `owntracks:///config?inline=${encodeURIComponent(inline)}`;
	});
	const otQr = $derived(otConfigLink ? renderSVG(otConfigLink, { border: 2 }) : '');
	const regionNames = $derived(places.map((p) => p.name));

	// --- generic HTTP examples (iOS Shortcuts, Tasker, MacroDroid, ...) ---
	const exampleZone = $derived(places.find((p) => p.kind === 'office')?.name ?? 'Büro');
	const example = $derived(
		`POST ${instance.baseUrl}/api/events\nAuthorization: Bearer <Token>\nContent-Type: application/json\n\n{"type": "zone_enter", "zone": "${exampleZone}"}`
	);
	const actions = [
		['/api/events', '{"type": "zone_enter", "zone": "…"}', 'action_zone_enter'],
		['/api/events', '{"type": "zone_leave", "zone": "…"}', 'action_zone_leave'],
		['/api/clock/start', '{"kind": "home"}', 'action_start_home'],
		['/api/clock/start', '{"kind": "office"}', 'action_start_office'],
		['/api/clock/break/start', '{}', 'action_break_start'],
		['/api/clock/break/stop', '{}', 'action_break_stop'],
		['/api/clock/stop', '{}', 'action_stop']
	] as const;

	async function create(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		try {
			created = (await api.post<ApiTokenInfo>('/tokens', { name })).token ?? null;
			name = '';
			await load();
		} catch (err) {
			error = errorText(err);
		}
	}

	async function revoke(t: ApiTokenInfo) {
		if (!confirm(`${m.revoke()}: ${t.name}?`)) return;
		await api.del(`/tokens/${t.id}`);
		await load();
	}

	async function copy(key: string, text: string) {
		await navigator.clipboard.writeText(text);
		copied = key;
		setTimeout(() => (copied = null), 2000);
	}

	const fmt = (iso: string) =>
		new Intl.DateTimeFormat(getLocale(), { dateStyle: 'medium', timeStyle: 'short', timeZone: auth.tz }).format(
			new Date(iso)
		);

	const origin = $derived(instance.baseUrl);
	// Revoked tokens are history only; keep the list short
	const active = $derived(tokens.filter((t) => !t.revoked_at));
	const steps = $derived([m.ha_step_install(), m.ha_step_add(), m.ha_step_login(), m.ha_step_zones()]);
	const actionLabel = (key: (typeof actions)[number][2]) => m[key]();
</script>

<section class="card space-y-5">
	<div>
		<h2 class="section-title mb-1">{m.integrations()}</h2>
		<p class="text-sm muted">{m.integrations_text()}</p>
	</div>

	{#if active.length}
		<ul class="divide-y divide-slate-100 dark:divide-slate-800">
			{#each active as t (t.id)}
				<li class="flex items-center gap-3 py-2.5 text-sm">
					<KeyRound class="size-4 shrink-0 muted" />
					<span class="font-medium">{t.name}</span>
					<span class="flex-1 truncate text-xs muted">
						{t.last_used_at ? m.token_last_used({ date: fmt(t.last_used_at) }) : m.token_never_used()}
					</span>
					<button class="btn-danger px-2 py-1 text-xs" onclick={() => revoke(t)}>
						<Trash2 class="size-4" />{m.revoke()}
					</button>
				</li>
			{/each}
		</ul>
	{/if}

	<details class="rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
		<summary class="flex cursor-pointer items-center gap-2 px-4 py-3 text-sm font-medium">
			<House class="size-4 text-brand-600" />{m.ha_setup()}
		</summary>
		<div class="space-y-3 px-4 pb-4 text-sm">
			<p class="muted">{m.ha_integration_text()}</p>
			<ol class="list-decimal space-y-1.5 pl-5">
				{#each steps as step, i (i)}<li>{step}</li>{/each}
			</ol>
			<div class="flex gap-2">
				<input class="input font-mono text-xs" readonly value={origin} onfocus={(e) => e.currentTarget.select()} />
				<button class="btn-secondary shrink-0" onclick={() => copy('url', origin)}>
					{#if copied === 'url'}<Check class="size-4" />{m.copied()}{:else}<Copy class="size-4" />{m.copy()}{/if}
				</button>
			</div>
		</div>
	</details>

	<details class="rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
		<summary class="flex cursor-pointer items-center gap-2 px-4 py-3 text-sm font-medium">
			<MapPin class="size-4 text-brand-600" />{m.ot_setup()}
		</summary>
		<div class="space-y-3 px-4 pb-4 text-sm">
			<p class="muted">{m.ot_text()}</p>
			<ol class="list-decimal space-y-1.5 pl-5">
				<li>{m.ot_step_install()}</li>
				<li>{m.ot_step_token()}</li>
				<li>{m.ot_step_regions({ names: regionNames.map((n) => `„${n}“`).join(', ') })}</li>
				<li>{m.ot_step_permission()}</li>
			</ol>
			{#if !otToken}
				<button class="btn-primary" onclick={createOwnTracks}><Smartphone class="size-4" />{m.ot_create()}</button>
				<Alert message={otError} />
			{:else}
				<div class="space-y-3 rounded-2xl bg-brand-50 p-4 dark:bg-brand-900/30">
					<p class="font-medium">{m.ot_scan()}</p>
					<div class="flex flex-wrap items-center gap-4">
						<div class="w-44 shrink-0 rounded-2xl bg-white p-2 [&_svg]:h-auto [&_svg]:w-full">{@html otQr}</div>
						<div class="min-w-0 flex-1 basis-56 space-y-2">
							<a class="btn-secondary" href={otConfigLink}><Smartphone class="size-4" />{m.ot_open_link()}</a>
							<p class="text-xs muted">{m.ot_once()}</p>
						</div>
					</div>
					<details>
						<summary class="cursor-pointer text-xs font-medium">{m.ot_manual()}</summary>
						<dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
							<dt class="muted">{m.ot_mode()}</dt><dd>HTTP</dd>
							<dt class="muted">URL</dt><dd class="font-mono break-all">{otUrl}</dd>
							<dt class="muted">{m.ot_user()}</dt><dd class="font-mono">pendel</dd>
							<dt class="muted">{m.password()}</dt><dd class="font-mono break-all select-all">{otToken}</dd>
						</dl>
					</details>
				</div>
			{/if}
		</div>
	</details>

	<details class="rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
		<summary class="flex cursor-pointer items-center gap-2 px-4 py-3 text-sm font-medium">
			<KeyRound class="size-4 text-brand-600" />{m.other_tools()}
		</summary>
		<div class="space-y-3 px-4 pb-4 text-sm">
			<p class="muted">{m.other_tools_text()}</p>
			<form class="flex flex-wrap items-end gap-2" onsubmit={create}>
				<div class="min-w-48 flex-1">
					<label class="label" for="tname">{m.token_name()}</label>
					<input id="tname" class="input" bind:value={name} required maxlength="100" placeholder="Tasker" />
				</div>
				<button class="btn-secondary"><Plus class="size-4" />{m.create_token()}</button>
			</form>
			<Alert message={error} />
			{#if created}
				<div class="rounded-2xl bg-brand-50 p-4 dark:bg-brand-900/30">
					<p class="mb-2 text-sm font-medium">{m.token_created()}</p>
					<div class="flex gap-2">
						<input class="input font-mono text-xs" readonly value={created} onfocus={(e) => e.currentTarget.select()} />
						<button class="btn-secondary shrink-0" onclick={() => copy('token', created!)}>
							{#if copied === 'token'}<Check class="size-4" />{m.copied()}{:else}<Copy class="size-4" />{m.copy()}{/if}
						</button>
					</div>
				</div>
			{/if}
			<p class="font-medium">{m.http_example()}</p>
			<pre class="overflow-x-auto rounded-xl bg-slate-100 p-3 font-mono text-xs dark:bg-slate-800">{example}</pre>
			<p class="text-xs muted">{m.http_example_hint()}</p>
			<div class="overflow-x-auto">
				<table class="w-full text-xs">
					<tbody class="divide-y divide-slate-100 dark:divide-slate-800">
						{#each actions as [path, body, key] (key)}
							<tr>
								<td class="py-1.5 pr-3">{actionLabel(key)}</td>
								<td class="py-1.5 pr-3 font-mono whitespace-nowrap">POST {path}</td>
								<td class="py-1.5 font-mono whitespace-nowrap">{body}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	</details>
</section>
