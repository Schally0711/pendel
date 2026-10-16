<script lang="ts">
	import { goto } from '$app/navigation';
	import { m } from '#lib/paraglide/messages.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import { errorText } from '#lib/errors.js';
	import Alert from './Alert.svelte';
	import { DatabaseBackup, Download, Upload } from '@lucide/svelte';

	let file = $state<File | null>(null);
	let password = $state('');
	let code = $state('');
	let confirmed = $state(false);
	let busy = $state(false);
	let error = $state<string | null>(null);

	async function restore(e: SubmitEvent) {
		e.preventDefault();
		if (!file) return;
		busy = true;
		error = null;
		try {
			const headers: Record<string, string> = { 'X-Confirm-Password': password };
			if (code) headers['X-Confirm-Totp'] = code;
			await api.upload('/admin/restore', file, headers);
			// all sessions now come from the backup: log in again (navigate first, the layout
			// would otherwise redirect to a plain /login as soon as the user is cleared)
			await goto('/login?restored=1');
			auth.set(null);
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<section class="card space-y-4">
	<div class="flex items-start gap-3">
		<DatabaseBackup class="mt-0.5 size-5 shrink-0 text-brand-600" />
		<div>
			<h2 class="section-title mb-1">{m.backup_title()}</h2>
			<p class="text-sm muted">{m.backup_text()}</p>
		</div>
	</div>
	<a class="btn-secondary" href="/api/admin/backup" download><Download class="size-4" />{m.backup_download()}</a>

	<details class="rounded-2xl ring-1 ring-slate-200 dark:ring-slate-700">
		<summary class="flex cursor-pointer items-center gap-2 px-4 py-3 text-sm font-medium">
			<Upload class="size-4 text-brand-600" />{m.restore_title()}
		</summary>
		<form class="space-y-3 px-4 pb-4 text-sm" onsubmit={restore}>
			<p class="text-amber-700 dark:text-amber-400">{m.restore_warning()}</p>
			<div>
				<label class="label" for="restore-file">{m.restore_file()}</label>
				<input
					id="restore-file"
					type="file"
					accept=".db,.sqlite,.sqlite3,application/vnd.sqlite3"
					class="input"
					required
					onchange={(e) => (file = e.currentTarget.files?.[0] ?? null)}
				/>
			</div>
			<div class="grid gap-3 sm:grid-cols-2">
				<div>
					<label class="label" for="restore-pw">{m.password()}</label>
					<input id="restore-pw" type="password" class="input" bind:value={password} required autocomplete="current-password" />
				</div>
				{#if auth.user?.totp_enabled}
					<div>
						<label class="label" for="restore-code">{m.totp_code()}</label>
						<input id="restore-code" class="input font-mono" bind:value={code} required autocomplete="one-time-code" />
					</div>
				{/if}
			</div>
			<label class="flex items-start gap-2">
				<input type="checkbox" class="mt-0.5 size-4 accent-brand-600" bind:checked={confirmed} required />
				<span>{m.restore_confirm()}</span>
			</label>
			<Alert message={error} />
			<button class="btn-danger" disabled={busy || !confirmed}>{busy ? m.loading() : m.restore_button()}</button>
		</form>
	</details>
</section>
