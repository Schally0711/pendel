<script lang="ts">
	import { onMount } from 'svelte';
	import { renderSVG } from 'uqr';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { LoginSessionInfo, TotpStatus, User } from '#lib/types.js';
	import Alert from './Alert.svelte';
	import Modal from './Modal.svelte';
	import { Download, KeyRound, LogOut, Monitor, ShieldCheck, Smartphone } from '@lucide/svelte';

	let status = $state<TotpStatus | null>(null);
	let sessions = $state<LoginSessionInfo[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);

	// dialog state: setup (password -> QR + code), recovery codes, confirm (disable / new codes)
	type Step = 'password' | 'scan' | 'codes' | 'disable' | 'regenerate' | null;
	let step = $state<Step>(null);
	let password = $state('');
	let code = $state('');
	let setup = $state<{ secret: string; uri: string } | null>(null);
	let codes = $state<string[]>([]);

	const qr = $derived(setup ? renderSVG(setup.uri, { border: 2 }) : '');

	const load = async () => {
		[status, sessions] = await Promise.all([
			api.get<TotpStatus>('/me/totp'),
			api.get<LoginSessionInfo[]>('/me/sessions')
		]);
	};
	onMount(load);

	/** Refresh the lists, e.g. after a password change signed out other devices. */
	export const reload = load;

	function open(s: Step) {
		step = s;
		password = '';
		code = '';
		error = null;
	}

	async function run(action: () => Promise<void>) {
		busy = true;
		error = null;
		try {
			await action();
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

	const submitPassword = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			setup = await api.post('/me/totp/setup', { password });
			step = 'scan';
		});
	};

	const submitCode = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			codes = (await api.post<{ codes: string[] }>('/me/totp/enable', { code })).codes;
			setup = null;
			step = 'codes';
			auth.set(await api.get<User>('/me'));
			await load();
		});
	};

	const submitConfirm = (e: SubmitEvent) => {
		e.preventDefault();
		run(async () => {
			if (step === 'disable') {
				await api.post('/me/totp/disable', { password, totp: code });
				step = null;
				auth.set(await api.get<User>('/me'));
			} else {
				codes = (await api.post<{ codes: string[] }>('/me/totp/recovery-codes', { password, totp: code })).codes;
				step = 'codes';
			}
			await load();
		});
	};

	function saveCodes() {
		const text = `Pendel – ${m.recovery_codes()} (${auth.user?.email})\n\n${codes.join('\n')}\n`;
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
		a.download = 'pendel-recovery-codes.txt';
		a.click();
		URL.revokeObjectURL(a.href);
	}

	async function endSession(s: LoginSessionInfo | null) {
		await run(async () => {
			await api.del(s ? `/me/sessions/${s.id}` : '/me/sessions');
			await load();
		});
	}

	const fmt = (iso: string) =>
		new Intl.DateTimeFormat(getLocale(), { dateStyle: 'medium', timeStyle: 'short', timeZone: auth.tz }).format(
			new Date(iso)
		);

	function device(ua: string): { label: string; mobile: boolean } {
		if (!ua) return { label: m.unknown_device(), mobile: false };
		const mobile = /Android|iPhone|iPad|Mobile/i.test(ua);
		const os = /Android/i.test(ua) ? 'Android' : /iPhone|iPad/i.test(ua) ? 'iOS' : /Windows/i.test(ua) ? 'Windows' : /Mac OS/i.test(ua) ? 'macOS' : /Linux/i.test(ua) ? 'Linux' : '';
		const browser = /Edg\//.test(ua) ? 'Edge' : /Firefox\//.test(ua) ? 'Firefox' : /Chrome\//.test(ua) ? 'Chrome' : /Safari\//.test(ua) ? 'Safari' : /HomeAssistant|aiohttp|python/i.test(ua) ? 'Home Assistant' : '';
		const label = [browser, os].filter(Boolean).join(' · ');
		return { label: label || ua.slice(0, 40), mobile };
	}
</script>

<section class="card space-y-6">
	<h2 class="section-title">{m.security()}</h2>

	<div class="flex flex-wrap items-start gap-4">
		<span
			class="grid size-10 shrink-0 place-items-center rounded-full {status?.enabled
				? 'bg-brand-100 text-brand-700 dark:bg-brand-900/50 dark:text-brand-300'
				: 'bg-slate-100 text-slate-500 dark:bg-slate-800'}"
		>
			<ShieldCheck class="size-5" />
		</span>
		<div class="min-w-0 flex-1 basis-60">
			<div class="font-medium">{m.totp_title()}</div>
			<p class="text-sm muted">
				{status?.enabled ? m.totp_on_text({ n: status.recovery_codes_left }) : m.totp_off_text()}
			</p>
		</div>
		{#if status?.enabled}
			<div class="flex flex-wrap gap-2">
				<button class="btn-secondary" onclick={() => open('regenerate')}><KeyRound class="size-4" />{m.recovery_codes_new()}</button>
				<button class="btn-danger" onclick={() => open('disable')}>{m.totp_disable()}</button>
			</div>
		{:else if status}
			<button class="btn-primary" onclick={() => open('password')}>{m.totp_setup()}</button>
		{/if}
	</div>

	<div>
		<div class="mb-1 font-medium">{m.sessions_title()}</div>
		<p class="mb-3 text-sm muted">{m.sessions_text()}</p>
		<ul class="divide-y divide-slate-100 dark:divide-slate-800">
			{#each sessions as s (s.id)}
				{@const d = device(s.user_agent)}
				<li class="flex items-center gap-3 py-2.5 text-sm">
					{#if d.mobile}<Smartphone class="size-4 shrink-0 muted" />{:else}<Monitor class="size-4 shrink-0 muted" />{/if}
					<span class="min-w-0 flex-1">
						<span class="flex items-center gap-2">
							<span class="truncate font-medium" title={s.user_agent}>{d.label}</span>
							{#if s.current}
								<span class="rounded-md bg-brand-100 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-900/50 dark:text-brand-300">{m.session_current()}</span>
							{/if}
						</span>
						<span class="block truncate text-xs muted">
							{m.session_created({ date: fmt(s.created_at) })}{#if s.last_seen_at}{' · '}{m.session_seen({ time: fmt(s.last_seen_at) })}{/if}
						</span>
					</span>
					{#if !s.current}
						<button class="btn-ghost p-1.5" aria-label={m.session_end()} title={m.session_end()} onclick={() => endSession(s)}>
							<LogOut class="size-4" />
						</button>
					{/if}
				</li>
			{/each}
		</ul>
		{#if sessions.length > 1}
			<button class="btn-secondary mt-3" disabled={busy} onclick={() => endSession(null)}>
				<LogOut class="size-4" />{m.sessions_end_others()}
			</button>
		{/if}
		{#if !step}<div class="mt-2"><Alert message={error} /></div>{/if}
	</div>
</section>

{#if step}
	<Modal
		title={step === 'codes' ? m.recovery_codes() : step === 'regenerate' ? m.recovery_codes_new() : step === 'disable' ? m.totp_disable() : m.totp_title()}
		onclose={() => ((step = null), (setup = null))}
	>
		{#if step === 'password'}
			<form class="space-y-4" onsubmit={submitPassword}>
				<p class="text-sm muted">{m.totp_setup_password()}</p>
				<div>
					<label class="label" for="tp-pw">{m.password()}</label>
					<input id="tp-pw" type="password" class="input" bind:value={password} required autocomplete="current-password" />
				</div>
				<Alert message={error} />
				<div class="flex justify-end"><button class="btn-primary" disabled={busy}>{m.totp_setup()}</button></div>
			</form>
		{:else if step === 'scan' && setup}
			<form class="space-y-4" onsubmit={submitCode}>
				<p class="text-sm muted">{m.totp_scan()}</p>
				<div class="mx-auto w-52 rounded-2xl bg-white p-2 [&_svg]:h-auto [&_svg]:w-full">
					{@html qr}
				</div>
				<div>
					<div class="label">{m.totp_secret()}</div>
					<code class="block rounded-xl bg-slate-100 px-3 py-2 text-center font-mono text-sm break-all select-all dark:bg-slate-800">
						{setup.secret.match(/.{1,4}/g)?.join(' ')}
					</code>
				</div>
				<div>
					<label class="label" for="tp-code">{m.totp_code()}</label>
					<input id="tp-code" class="input text-center font-mono text-lg tracking-widest" bind:value={code} required inputmode="numeric" autocomplete="one-time-code" maxlength="6" />
				</div>
				<Alert message={error} />
				<div class="flex justify-end"><button class="btn-primary" disabled={busy}>{m.totp_activate()}</button></div>
			</form>
		{:else if step === 'codes'}
			<div class="space-y-4">
				<p class="text-sm muted">{m.recovery_codes_text()}</p>
				<ul class="grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-4 font-mono text-sm dark:bg-slate-800">
					{#each codes as c (c)}<li class="text-center select-all">{c}</li>{/each}
				</ul>
				<div class="flex flex-wrap justify-end gap-2">
					<button class="btn-secondary" onclick={saveCodes}><Download class="size-4" />{m.recovery_codes_save()}</button>
					<button class="btn-primary" onclick={() => (step = null)}>{m.recovery_codes_saved()}</button>
				</div>
			</div>
		{:else}
			<form class="space-y-4" onsubmit={submitConfirm}>
				<p class="text-sm muted">{m.totp_confirm_text()}</p>
				<div>
					<label class="label" for="tc-pw">{m.password()}</label>
					<input id="tc-pw" type="password" class="input" bind:value={password} required autocomplete="current-password" />
				</div>
				<div>
					<label class="label" for="tc-code">{m.totp_code()}</label>
					<input id="tc-code" class="input font-mono" bind:value={code} required autocomplete="one-time-code" maxlength="32" />
				</div>
				<Alert message={error} />
				<div class="flex justify-end">
					<button class={step === 'disable' ? 'btn-danger' : 'btn-primary'} disabled={busy}>
						{step === 'disable' ? m.totp_disable() : m.recovery_codes_new()}
					</button>
				</div>
			</form>
		{/if}
	</Modal>
{/if}
