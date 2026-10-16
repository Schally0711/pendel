<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { User } from '#lib/types.js';
	import Alert from '#lib/components/Alert.svelte';
	import Security from '#lib/components/Security.svelte';
	import Modal from '#lib/components/Modal.svelte';
	import { Download, LogOut, Monitor, Moon, Sun, Trash2, Users } from '@lucide/svelte';

	type Status = { message: string | null; tone: 'error' | 'success' };
	const status = $state<Record<string, Status>>({});
	function ok(key: string) {
		status[key] = { message: m.saved(), tone: 'success' };
		setTimeout(() => (status[key] = { message: null, tone: 'success' }), 2500);
	}
	const fail = (key: string, e: unknown) => (status[key] = { message: errorText(e), tone: 'error' });

	const u = auth.user!;
	let profile = $state({ display_name: u.display_name, locale: u.locale });

	async function saveProfile(e: SubmitEvent) {
		e.preventDefault();
		try {
			const user = await api.patch<User>('/me', profile);
			auth.set(user);
			if (user.locale !== getLocale()) setLocale(user.locale);
			ok('profile');
		} catch (err) {
			fail('profile', err);
		}
	}

	let theme = $state<ThemeMode>(window.pendelTheme?.get() ?? 'system');
	function setTheme(mode: ThemeMode) {
		theme = mode;
		window.pendelTheme?.set(mode);
	}
	const themes = $derived([
		{ mode: 'system' as const, label: m.theme_system(), icon: Monitor },
		{ mode: 'light' as const, label: m.theme_light(), icon: Sun },
		{ mode: 'dark' as const, label: m.theme_dark(), icon: Moon }
	]);

	let pw = $state({ current_password: '', new_password: '' });
	let security: Security;
	async function changePassword(e: SubmitEvent) {
		e.preventDefault();
		try {
			await api.post('/me/password', pw);
			pw = { current_password: '', new_password: '' };
			ok('password');
			security?.reload(); // other devices were signed out
		} catch (err) {
			fail('password', err);
		}
	}

	// delete the own account
	let deleting = $state(false);
	let del = $state({ password: '', totp: '' });
	let delError = $state<string | null>(null);
	async function deleteAccount(e: SubmitEvent) {
		e.preventDefault();
		delError = null;
		try {
			await api.post('/me/delete', { password: del.password, totp: del.totp || null });
			auth.set(null);
			goto('/login');
		} catch (err) {
			delError = errorText(err);
		}
	}

	async function logout() {
		await api.post('/auth/logout');
		auth.set(null);
		goto('/login');
	}
</script>

<div class="space-y-6">
	<div class="flex flex-wrap items-center gap-4">
		<span
			class="grid size-14 shrink-0 place-items-center rounded-full bg-brand-100 text-2xl font-semibold text-brand-700 dark:bg-brand-900/50 dark:text-brand-300"
		>
			{(auth.user?.display_name ?? '?').slice(0, 1).toUpperCase()}
		</span>
		<div class="min-w-0 flex-1">
			<h1 class="truncate text-2xl font-semibold tracking-tight">{auth.user?.display_name}</h1>
			<p class="truncate muted">{auth.user?.email}</p>
		</div>
		<div class="flex w-full gap-2 sm:w-auto">
			{#if auth.user?.is_admin}
				<a href="/admin" class="btn-secondary md:hidden"><Users class="size-4" />{m.nav_admin()}</a>
			{/if}
			<button class="btn-secondary" onclick={logout}><LogOut class="size-4" />{m.logout()}</button>
		</div>
	</div>

	<form class="card space-y-4" onsubmit={saveProfile}>
		<h2 class="section-title">{m.profile()}</h2>
		<div class="grid gap-4 sm:grid-cols-2">
			<div>
				<label class="label" for="name">{m.display_name()}</label>
				<input id="name" class="input" bind:value={profile.display_name} required maxlength="100" />
			</div>
			<div>
				<label class="label" for="locale">{m.language()}</label>
				<select id="locale" class="input" bind:value={profile.locale}>
					<option value="de">Deutsch</option>
					<option value="en">English</option>
				</select>
			</div>
		</div>
		<div class="flex items-center gap-3">
			<button class="btn-primary">{m.save()}</button>
			<Alert message={status.profile?.message ?? null} tone={status.profile?.tone} />
		</div>
	</form>

	<section class="card space-y-3">
		<div>
			<h2 class="section-title mb-1">{m.appearance()}</h2>
			<p class="text-sm muted">{m.appearance_text()}</p>
		</div>
		<div class="inline-flex flex-wrap gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800" role="radiogroup" aria-label={m.appearance()}>
			{#each themes as t (t.mode)}
				<button
					type="button"
					role="radio"
					aria-checked={theme === t.mode}
					class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition {theme === t.mode
						? 'bg-white text-brand-700 shadow-sm dark:bg-slate-900 dark:text-brand-400'
						: 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'}"
					onclick={() => setTheme(t.mode)}
				>
					<t.icon class="size-4" />{t.label}
				</button>
			{/each}
		</div>
	</section>

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

	<Security bind:this={security} />

	<section class="card space-y-3">
		<div>
			<h2 class="section-title mb-1">{m.your_data()}</h2>
			<p class="text-sm muted">{m.your_data_text()}</p>
		</div>
		<div class="flex flex-wrap gap-2">
			<a class="btn-secondary" href="/api/me/export" download><Download class="size-4" />{m.export_data()}</a>
			<button class="btn-danger" onclick={() => ((deleting = true), (delError = null))}><Trash2 class="size-4" />{m.delete_account()}</button>
		</div>
	</section>
</div>

{#if deleting}
	<Modal title={m.delete_account()} onclose={() => (deleting = false)}>
		<form class="space-y-4" onsubmit={deleteAccount}>
			<p class="text-sm">{m.delete_account_text()}</p>
			<div>
				<label class="label" for="del-pw">{m.password()}</label>
				<input id="del-pw" type="password" class="input" bind:value={del.password} required autocomplete="current-password" />
			</div>
			{#if auth.user?.totp_enabled}
				<div>
					<label class="label" for="del-code">{m.totp_code()}</label>
					<input id="del-code" class="input font-mono" bind:value={del.totp} required autocomplete="one-time-code" />
				</div>
			{/if}
			<Alert message={delError} />
			<div class="flex justify-end gap-2">
				<button type="button" class="btn-ghost" onclick={() => (deleting = false)}>{m.cancel()}</button>
				<button class="btn-danger">{m.delete_account_button()}</button>
			</div>
		</form>
	</Modal>
{/if}
