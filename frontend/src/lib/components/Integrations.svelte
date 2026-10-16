<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { ApiTokenInfo } from '#lib/types.js';
	import Alert from './Alert.svelte';
	import { Check, Copy, KeyRound, Plus, Trash2 } from '@lucide/svelte';

	let tokens = $state<ApiTokenInfo[]>([]);
	let name = $state('Home Assistant');
	let created = $state<string | null>(null);
	let copied = $state<string | null>(null);
	let error = $state<string | null>(null);

	const load = async () => (tokens = await api.get<ApiTokenInfo[]>('/tokens'));
	onMount(load);

	async function create(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		try {
			created = (await api.post<ApiTokenInfo>('/tokens', { name })).token ?? null;
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

	const origin = typeof location !== 'undefined' ? location.origin : '';
	const snippets = $derived([
		{ key: 'secret', title: m.ha_step_secret(), code: `pendel_token: "Bearer ${created ?? '<TOKEN>'}"` },
		{
			key: 'config',
			title: m.ha_step_config(),
			code: `rest_command:
  pendel_event:
    url: "${origin}/api/events"
    method: POST
    headers:
      Authorization: !secret pendel_token
    content_type: "application/json"
    payload: >-
      {{ {"type": "zone_change", "from": from_zone, "to": to_zone,
          "at": at, "source": "home_assistant"} | to_json }}`
		},
		{
			key: 'automation',
			title: m.ha_step_automation(),
			code: `alias: Pendel – Zonenwechsel melden
mode: queued
triggers:
  - trigger: state
    entity_id: person.ich
    not_from: [unknown, unavailable]
    not_to: [unknown, unavailable]
actions:
  - action: rest_command.pendel_event
    data:
      from_zone: "{{ trigger.from_state.state }}"
      to_zone: "{{ trigger.to_state.state }}"
      at: "{{ trigger.to_state.last_changed.isoformat() }}"`
		}
	]);
</script>

<section class="card space-y-5">
	<div>
		<h2 class="section-title mb-1">{m.integrations()}</h2>
		<p class="text-sm muted">{m.integrations_text()}</p>
	</div>

	{#if tokens.length}
		<ul class="divide-y divide-slate-100 dark:divide-slate-800">
			{#each tokens as t (t.id)}
				<li class="flex items-center gap-3 py-2.5 text-sm {t.revoked_at ? 'opacity-50' : ''}">
					<KeyRound class="size-4 shrink-0 muted" />
					<span class="font-medium">{t.name}</span>
					<span class="flex-1 truncate text-xs muted">
						{t.revoked_at
							? m.token_revoked()
							: t.last_used_at
								? m.token_last_used({ date: fmt(t.last_used_at) })
								: m.token_never_used()}
					</span>
					{#if !t.revoked_at}
						<button class="btn-danger px-2 py-1 text-xs" onclick={() => revoke(t)}>
							<Trash2 class="size-4" />{m.revoke()}
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<form class="flex flex-wrap items-end gap-2" onsubmit={create}>
		<div class="min-w-48 flex-1">
			<label class="label" for="tname">{m.token_name()}</label>
			<input id="tname" class="input" bind:value={name} required maxlength="100" />
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

	<details class="group rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
		<summary class="cursor-pointer px-4 py-3 text-sm font-medium">{m.ha_setup()}</summary>
		<ol class="space-y-4 px-4 pb-4 text-sm">
			<li>1. {m.ha_step_places()}</li>
			{#each snippets as s, i (s.key)}
				<li>
					<div class="mb-1.5 flex items-center justify-between gap-2">
						<span>{i + 2}. {s.title}</span>
						<button class="btn-ghost px-2 py-1 text-xs" onclick={() => copy(s.key, s.code)}>
							{#if copied === s.key}<Check class="size-3.5" />{m.copied()}{:else}<Copy class="size-3.5" />{m.copy()}{/if}
						</button>
					</div>
					<pre class="overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">{s.code}</pre>
				</li>
			{/each}
		</ol>
	</details>
</section>
