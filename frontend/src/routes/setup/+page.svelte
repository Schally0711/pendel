<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import type { User } from '#lib/types.js';
	import AuthCard from '#lib/components/AuthCard.svelte';
	import RegisterForm from '#lib/components/RegisterForm.svelte';
	import Alert from '#lib/components/Alert.svelte';
	import { errorText } from '#lib/errors.js';
	import { Upload } from '@lucide/svelte';

	let setup_code = $state('');
	let restoreMode = $state(false);
	let file = $state<File | null>(null);
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function restore(e: SubmitEvent) {
		e.preventDefault();
		if (!file) return;
		busy = true;
		error = null;
		try {
			await api.upload('/setup/restore', file, { 'X-Setup-Code': setup_code.trim() });
			goto('/login?restored=1');
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}

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
	{#if restoreMode}
		<form class="space-y-4" onsubmit={restore}>
			<p class="text-sm muted">{m.setup_restore_text()}</p>
			<div>
				<label class="label" for="setup-file">{m.restore_file()}</label>
				<input
					id="setup-file"
					type="file"
					accept=".db,.sqlite,.sqlite3,application/vnd.sqlite3"
					class="input"
					required
					onchange={(e) => (file = e.currentTarget.files?.[0] ?? null)}
				/>
			</div>
			<Alert message={error} />
			<button class="btn-primary w-full" disabled={busy}>{busy ? m.loading() : m.restore_button()}</button>
			<button type="button" class="btn-ghost w-full" onclick={() => (restoreMode = false)}>{m.setup_new_instead()}</button>
		</form>
	{:else}
		<RegisterForm {submit} label={m.create_account()} />
		<button type="button" class="btn-ghost mt-3 w-full text-sm" onclick={() => (restoreMode = true)}>
			<Upload class="size-4" />{m.setup_restore()}
		</button>
	{/if}
</AuthCard>
