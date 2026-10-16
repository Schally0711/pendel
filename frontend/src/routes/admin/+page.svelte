<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import { instance } from '#lib/instance.svelte.js';
	import type { Invitation, User } from '#lib/types.js';
	import Alert from '#lib/components/Alert.svelte';
	import { Check, Copy, Globe, Plus, ShieldOff, Trash2 } from '@lucide/svelte';

	let invitations = $state<Invitation[]>([]);
	let users = $state<User[]>([]);
	let note = $state('');
	let validDays = $state(7);
	let link = $state<string | null>(null);
	let copied = $state(false);
	let error = $state<string | null>(null);

	const fmt = (iso: string) =>
		new Intl.DateTimeFormat(getLocale(), { dateStyle: 'medium', timeZone: auth.tz }).format(new Date(iso));

	let publicUrl = $state('');
	let instanceMsg = $state<{ text: string; tone: 'error' | 'success' } | null>(null);

	async function saveInstance(e: SubmitEvent) {
		e.preventDefault();
		instanceMsg = null;
		try {
			const r = await api.put<{ public_url: string | null }>('/admin/instance', { public_url: publicUrl || null });
			await instance.load(true);
			publicUrl = r.public_url ?? '';
			instanceMsg = { text: m.saved(), tone: 'success' };
		} catch {
			instanceMsg = { text: m.public_url_invalid(), tone: 'error' };
		}
	}

	async function load() {
		await instance.load();
		publicUrl = instance.publicUrl ?? '';
		[invitations, users] = await Promise.all([
			api.get<Invitation[]>('/admin/invitations'),
			api.get<User[]>('/admin/users')
		]);
	}
	onMount(load);

	async function create(e: SubmitEvent) {
		e.preventDefault();
		error = null;
		try {
			const inv = await api.post<Invitation>('/admin/invitations', { note, valid_days: validDays });
			link = `${instance.baseUrl}/invite/${inv.token}`;
			copied = false;
			note = '';
			await load();
		} catch (err) {
			error = errorText(err);
		}
	}

	async function copy() {
		if (!link) return;
		await navigator.clipboard.writeText(link);
		copied = true;
	}

	async function removeInvitation(inv: Invitation) {
		await api.del(`/admin/invitations/${inv.id}`);
		await load();
	}

	async function resetTotp(u: User) {
		if (!confirm(m.reset_totp_confirm({ name: u.display_name }))) return;
		try {
			await api.del(`/admin/users/${u.id}/totp`);
			await load();
		} catch (err) {
			error = errorText(err);
		}
	}

	async function removeUser(u: User) {
		if (!confirm(`${m.confirm_delete()} ${u.display_name} (${u.email})`)) return;
		try {
			await api.del(`/admin/users/${u.id}`);
			await load();
		} catch (err) {
			error = errorText(err);
		}
	}

	const expired = (inv: Invitation) => !inv.used_at && new Date(inv.expires_at) < new Date();
</script>

<div class="space-y-6">
	<h1 class="text-2xl font-semibold tracking-tight">{m.admin_title()}</h1>

	<form class="card space-y-3" onsubmit={saveInstance}>
		<div class="flex items-start gap-3">
			<div class="rounded-xl bg-brand-50 p-2 text-brand-600 dark:bg-brand-900/40 dark:text-brand-400"><Globe class="size-5" /></div>
			<div>
				<h2 class="section-title mb-1">{m.instance()}</h2>
				<p class="text-sm muted">{m.public_url_help()}</p>
			</div>
		</div>
		<div class="flex flex-wrap items-end gap-2">
			<div class="min-w-64 flex-1">
				<label class="label" for="purl">{m.public_url()}</label>
				<input id="purl" class="input" type="url" placeholder="https://pendel.example.com" bind:value={publicUrl} />
			</div>
			<button class="btn-primary">{m.save()}</button>
		</div>
		{#if instanceMsg}<Alert message={instanceMsg.text} tone={instanceMsg.tone} />{/if}
		{#if instance.version}<p class="text-xs muted">{m.version({ v: instance.version })}</p>{/if}
	</form>

	<section class="card space-y-4">
		<h2 class="section-title">{m.invitations()}</h2>
		<form class="grid gap-2 sm:grid-cols-[1fr_8rem_auto] sm:items-end" onsubmit={create}>
			<div>
				<label class="label" for="note">{m.invite_note()}</label>
				<input id="note" class="input" bind:value={note} maxlength="255" />
			</div>
			<div>
				<label class="label" for="days">{m.valid_days()}</label>
				<input id="days" type="number" min="1" max="90" class="input" bind:value={validDays} />
			</div>
			<button class="btn-primary"><Plus class="size-4" />{m.create_invitation()}</button>
		</form>

		{#if link}
			<div class="rounded-2xl bg-brand-50 p-4 dark:bg-brand-900/30">
				<p class="mb-2 text-sm font-medium">{m.invitation_link()}</p>
				<div class="flex gap-2">
					<input class="input font-mono text-xs" readonly value={link} onfocus={(e) => e.currentTarget.select()} />
					<button class="btn-secondary shrink-0" onclick={copy}>
						{#if copied}<Check class="size-4" />{m.copied()}{:else}<Copy class="size-4" />{m.copy()}{/if}
					</button>
				</div>
			</div>
		{/if}
		<Alert message={error} />

		{#if invitations.length}
			<ul class="divide-y divide-slate-100 dark:divide-slate-800">
				{#each invitations as inv (inv.id)}
					<li class="flex items-center gap-3 py-2.5 text-sm">
						<span class="flex-1 truncate font-medium">{inv.note || '—'}</span>
						<span class="muted">
							{#if inv.used_at}{m.used({ date: fmt(inv.used_at) })}
							{:else if expired(inv)}{m.expired()}
							{:else}{m.expires({ date: fmt(inv.expires_at) })}{/if}
						</span>
						<button class="btn-danger p-1.5" aria-label={m.delete()} onclick={() => removeInvitation(inv)}>
							<Trash2 class="size-4" />
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</section>

	<section class="card">
		<h2 class="section-title">{m.users()}</h2>
		<ul class="divide-y divide-slate-100 dark:divide-slate-800">
			{#each users as u (u.id)}
				<li class="flex items-center gap-3 py-2.5 text-sm">
					<span class="grid size-8 shrink-0 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">
						{u.display_name.slice(0, 1).toUpperCase()}
					</span>
					<span class="min-w-0 flex-1">
						<span class="block truncate font-medium">{u.display_name}</span>
						<span class="block truncate text-xs muted">{u.email}</span>
					</span>
					{#if u.is_admin}
						<span class="rounded-md bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">{m.admin_badge()}</span>
					{/if}
					{#if u.totp_enabled}
						<span class="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">2FA</span>
						{#if u.id !== auth.user?.id}
							<button class="btn-ghost p-1.5" aria-label={m.reset_totp()} title={m.reset_totp()} onclick={() => resetTotp(u)}>
								<ShieldOff class="size-4" />
							</button>
						{/if}
					{/if}
					{#if u.id !== auth.user?.id}
						<button class="btn-danger p-1.5" aria-label={m.delete()} onclick={() => removeUser(u)}>
							<Trash2 class="size-4" />
						</button>
					{/if}
				</li>
			{/each}
		</ul>
	</section>
</div>
