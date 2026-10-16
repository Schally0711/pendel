<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import Alert from '#lib/components/Alert.svelte';

	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function onsubmit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = null;
		try {
			auth.set(await api.post<User>('/auth/login', { email, password }));
			goto('/');
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<AuthCard title={m.login_title()}>
	<form class="space-y-4" {onsubmit}>
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
		<Alert message={error} />
		<button class="btn-primary w-full" disabled={busy}>{m.login_button()}</button>
	</form>
</AuthCard>
