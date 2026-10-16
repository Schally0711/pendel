<script lang="ts">
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { getLocale } from '#lib/paraglide/runtime.js';
	import { api } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import type { CalendarStatus } from '#lib/types.js';
	import { CalendarPlus, CalendarSync, Check, Copy, ExternalLink } from '@lucide/svelte';

	let status = $state<CalendarStatus | null>(null);
	let url = $state<string | null>(null);
	let copied = $state(false);

	onMount(async () => (status = await api.get<CalendarStatus>('/calendar')));

	async function create() {
		if (status?.active && !confirm(m.calendar_renew_hint())) return;
		const r = await api.post<CalendarStatus>('/calendar/token');
		status = r;
		url = `${r.public_url ?? location.origin}${r.url_path}`;
		copied = false;
	}

	async function stop() {
		if (!confirm(m.confirm_delete())) return;
		await api.del('/calendar/token');
		status = { active: false, created_at: null, last_used_at: null, url_path: null, public_url: status?.public_url ?? null };
		url = null;
	}

	async function copy() {
		if (!url) return;
		await navigator.clipboard.writeText(url);
		copied = true;
	}

	const webcal = $derived(url ? url.replace(/^https?:/, 'webcal:') : null);
	const google = $derived(webcal ? `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(webcal)}` : null);

	const fmt = (iso: string) =>
		new Intl.DateTimeFormat(getLocale(), { dateStyle: 'medium', timeZone: auth.tz }).format(new Date(iso));
</script>

<section class="card space-y-3">
	<div class="flex items-start gap-3">
		<div class="rounded-xl bg-sky-50 p-2 text-sky-600 dark:bg-sky-950 dark:text-sky-300"><CalendarSync class="size-5" /></div>
		<div>
			<h2 class="section-title mb-1">{m.calendar_title()}</h2>
			<p class="text-sm muted">{status?.public_url ? m.calendar_text_public() : m.calendar_text()}</p>
		</div>
	</div>
	{#if url}
		<div class="rounded-2xl bg-brand-50 p-4 dark:bg-brand-900/30">
			<p class="mb-2 text-sm font-medium">{m.calendar_url()}</p>
			<div class="flex gap-2">
				<input class="input font-mono text-xs" readonly value={url} onfocus={(e) => e.currentTarget.select()} />
				<button class="btn-secondary shrink-0" onclick={copy}>
					{#if copied}<Check class="size-4" />{m.copied()}{:else}<Copy class="size-4" />{m.copy()}{/if}
				</button>
			</div>
			{#if status?.public_url && google && webcal}
				<div class="mt-3 flex flex-wrap gap-2">
					<a class="btn-secondary" href={google} target="_blank" rel="noopener"><ExternalLink class="size-4" />{m.calendar_google()}</a>
					<a class="btn-secondary" href={webcal} data-sveltekit-reload><CalendarPlus class="size-4" />{m.calendar_webcal()}</a>
				</div>
			{/if}
		</div>
	{/if}
	{#if status}
		<div class="flex flex-wrap items-center gap-3">
			<button class="btn-secondary" onclick={create}>{status.active ? m.calendar_renew() : m.calendar_create()}</button>
			{#if status.active}
				<span class="text-xs muted">{m.calendar_active({ date: fmt(status.created_at!) })}</span>
				<button class="btn-danger ml-auto px-2 py-1 text-xs" onclick={stop}>{m.calendar_stop()}</button>
			{/if}
		</div>
	{/if}
</section>
