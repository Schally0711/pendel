<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import RegisterForm from '#lib/components/RegisterForm.svelte';

	let setup_code = $state('');

	async function submit(data: Record<string, string>) {
		auth.set(await api.post<User>('/setup', { ...data, setup_code }));
		goto('/settings');
	}
</script>

<AuthCard title={m.setup_title()} text={m.setup_text()}>
	<div class="mb-4">
		<label class="label" for="setup-code">{m.setup_code()}</label>
		<input
			id="setup-code"
			class="input text-center font-mono tracking-widest uppercase"
			bind:value={setup_code}
			required
			autocomplete="off"
			maxlength="64"
		/>
		<p class="mt-1.5 text-xs muted">{m.setup_code_hint()}</p>
	</div>
	<RegisterForm {submit} label={m.create_account()} />
</AuthCard>
