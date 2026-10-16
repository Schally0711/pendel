<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import RegisterForm from '#lib/components/RegisterForm.svelte';

	async function submit(data: Record<string, string>) {
		auth.set(await api.post<User>('/setup', data));
		goto('/settings');
	}
</script>

<AuthCard title={m.setup_title()} text={m.setup_text()}>
	<RegisterForm {submit} label={m.create_account()} />
</AuthCard>
