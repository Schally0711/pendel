<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { errorText } from '#lib/errors.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import Alert from '#lib/components/Alert.svelte';

	const token = $derived(page.params.token ?? '');
	let check = $state<{ valid: boolean; display_name: string } | null>(null);
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	$effect(() => {
		api.get<{ valid: boolean; display_name: string }>(`/password-reset/${encodeURIComponent(token)}`).then(
			(r) => (check = r)
		);
	});

	async function onsubmit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = null;
		try {
			await api.post(`/password-reset/${encodeURIComponent(token)}`, { new_password: password });
			goto('/login?reset=1');
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<AuthCard
	title={m.reset_title()}
	text={check?.valid ? m.reset_text({ name: check.display_name }) : undefined}
>
	{#if check === null}
		<p class="muted">{m.loading()}</p>
	{:else if !check.valid}
		<Alert message={m.reset_link_invalid()} />
	{:else}
		<form class="space-y-4" {onsubmit}>
			<div>
				<label class="label" for="new-password">{m.new_password()}</label>
				<input id="new-password" type="password" class="input" bind:value={password} required minlength="10" autocomplete="new-password" />
				<p class="mt-1.5 text-xs muted">{m.reset_hint()}</p>
			</div>
			<Alert message={error} />
			<button class="btn-primary w-full" disabled={busy}>{m.reset_button()}</button>
		</form>
	{/if}
</AuthCard>
