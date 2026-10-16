<script lang="ts">
	import type { Snippet } from 'svelte';
	import favicon from '#lib/assets/favicon.svg';
	import { m } from '#lib/paraglide/messages.js';
	import LanguageSwitch from './LanguageSwitch.svelte';

	let { title, text, children }: { title: string; text?: string; children: Snippet } = $props();
</script>

<div class="grid min-h-dvh place-items-center bg-gradient-to-br from-brand-50 via-slate-100 to-slate-200 px-4 py-10 dark:from-brand-900/40 dark:via-slate-950 dark:to-slate-950">
	<div class="w-full max-w-sm">
		<div class="mb-8 text-center">
			<img src={favicon} alt="" class="mx-auto mb-3 size-14 drop-shadow" />
			<div class="text-2xl font-semibold tracking-tight">Pendel</div>
			<p class="mt-1 text-sm muted">{m.tagline()}</p>
		</div>
		<div class="card p-6">
			<h1 class="text-lg font-semibold">{title}</h1>
			{#if text}<p class="mt-1 text-sm muted">{text}</p>{/if}
			<div class="mt-5">{@render children()}</div>
		</div>
		<div class="mt-4 flex justify-center"><LanguageSwitch /></div>
	</div>
</div>
