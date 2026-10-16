<script lang="ts">
	import { m } from '#lib/paraglide/messages.js';

	let health = $state<{ status: string; version: string } | null>(null);
	let failed = $state(false);

	$effect(() => {
		fetch('/api/health')
			.then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
			.then((h) => (health = h))
			.catch(() => (failed = true));
	});
</script>

<h1 class="text-2xl font-semibold">{m.welcome_title()}</h1>
<p class="mt-2 text-slate-600 dark:text-slate-400">{m.welcome_text()}</p>

<p class="mt-6 text-sm">
	{#if health}
		<span class="text-brand-600">●</span> {m.backend_ok({ version: health.version })}
	{:else if failed}
		<span class="text-red-600">●</span> {m.backend_unreachable()}
	{:else}
		…
	{/if}
</p>
