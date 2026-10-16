<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '#lib/paraglide/messages.js';
	import { api, ApiError } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import Alert from '#lib/components/Alert.svelte';

	let email = $state('');
	let password = $state('');
	let totp = $state('');
	let needsCode = $state(false);
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function onsubmit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = null;
		try {
			auth.set(await api.post<User>('/auth/login', { email, password, totp: needsCode ? totp : null }));
			goto('/');
		} catch (err) {
			if (err instanceof ApiError && err.detail === 'totp_required') needsCode = true;
			else error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<AuthCard title={m.login_title()}>
	<form class="space-y-4" {onsubmit}>
		{#if page.url.searchParams.has('reset')}
			<Alert message={m.reset_done()} tone="success" />
		{:else if page.url.searchParams.has('restored')}
			<Alert message={m.restore_done()} tone="success" />
		{/if}
		<div>
			<label class="label" for="email">{m.email()}</label>
			<input id="email" class="input" type="email" bind:value={email} required autocomplete="username" />
		</div>
		<div>
			<label class="label" for="password">{m.password()}</label>
			<input
				id="password"
				class="input"
				type="password"
				bind:value={password}
				required
				autocomplete="current-password"
			/>
		</div>
		{#if needsCode}
			<div>
				<label class="label" for="totp">{m.totp_code()}</label>
				<!-- svelte-ignore a11y_autofocus -->
				<input
					id="totp"
					class="input text-center font-mono text-lg tracking-widest"
					bind:value={totp}
					required
					autofocus
					autocomplete="one-time-code"
					inputmode="text"
					maxlength="32"
				/>
				<p class="mt-1.5 text-xs muted">{m.totp_login_hint()}</p>
			</div>
		{/if}
		<Alert message={error} />
		<button class="btn-primary w-full" disabled={busy}>{m.login_button()}</button>
	</form>
</AuthCard>
