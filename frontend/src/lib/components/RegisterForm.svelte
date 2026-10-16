<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { errorText } from '#lib/errors.js';
	import Alert from './Alert.svelte';

	let {
		submit,
		label
	}: { submit: (data: Record<string, string>) => Promise<void>; label: string } = $props();

	let display_name = $state('');
	let email = $state('');
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	async function onsubmit(e: SubmitEvent) {
		e.preventDefault();
		busy = true;
		error = null;
		try {
			await submit({ display_name, email, password, locale: getLocale() });
		} catch (err) {
			error = errorText(err);
		} finally {
			busy = false;
		}
	}
</script>

<form class="space-y-4" {onsubmit}>
	<div>
		<label class="label" for="name">{m.display_name()}</label>
		<input id="name" class="input" bind:value={display_name} required autocomplete="name" />
	</div>
	<div>
		<label class="label" for="email">{m.email()}</label>
		<input id="email" class="input" type="email" bind:value={email} required autocomplete="email" />
	</div>
	<div>
		<label class="label" for="password">{m.password()}</label>
		<input
			id="password"
			class="input"
			type="password"
			bind:value={password}
			required
			minlength="10"
			autocomplete="new-password"
		/>
		<p class="mt-1 text-xs muted">{m.password_hint()}</p>
	</div>
	<Alert message={error} />
	<button class="btn-primary w-full" disabled={busy}>{label}</button>
</form>
