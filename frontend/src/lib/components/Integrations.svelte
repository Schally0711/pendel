<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { ApiTokenInfo } from '#lib/types.js';
	import { instance } from '#lib/instance.svelte.js';
	import Alert from './Alert.svelte';
	import { Check, Copy, House, KeyRound, Plus, Trash2 } from '@lucide/svelte';

	let tokens = $state<ApiTokenInfo[]>([]);
	let name = $state('');
	let created = $state<string | null>(null);
	let copied = $state<string | null>(null);
	let error = $state<string | null>(null);

	const load = async () => (tokens = await api.get<ApiTokenInfo[]>('/tokens'));
	onMount(() => {
		load();
		instance.load();
	});

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
		</div>
	</details>
</section>
