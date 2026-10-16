<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import Alert from '#lib/components/Alert.svelte';
	import RegisterForm from '#lib/components/RegisterForm.svelte';

	const token = $derived(page.params.token ?? '');
	let valid = $state<boolean | null>(null);

	$effect(() => {
		api.get<{ valid: boolean }>(`/invitations/${encodeURIComponent(token)}`).then((r) => (valid = r.valid));
	});

	async function submit(data: Record<string, string>) {
		auth.set(await api.post<User>(`/invitations/${encodeURIComponent(token)}/accept`, data));
		goto('/settings');
	}
</script>

<AuthCard title={m.invite_title()} text={valid ? m.invite_text() : undefined}>
	{#if valid === null}
		<p class="muted">{m.loading()}</p>
	{:else if valid}
		<RegisterForm {submit} label={m.create_account()} />
	{:else}
		<Alert message={m.invite_invalid()} />
	{/if}
</AuthCard>
