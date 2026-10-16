<script lang="ts">
	import { getLocale, setLocale, locales } from '#lib/paraglide/runtime.js';
	import { m } from '#lib/paraglide/messages.js';
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	$effect(() => {
		document.documentElement.lang = getLocale();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="min-h-dvh bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
	<header class="border-b border-slate-200 dark:border-slate-800">
		<div class="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
			<span class="text-lg font-semibold tracking-tight text-brand-700 dark:text-brand-500">Pendel</span>
			<nav class="flex gap-1 text-sm" aria-label={m.language()}>
				{#each locales as locale (locale)}
					<button
						class="rounded px-2 py-1 uppercase hover:bg-slate-200 dark:hover:bg-slate-800"
						class:font-bold={locale === getLocale()}
						onclick={() => setLocale(locale)}>{locale}</button
					>
				{/each}
			</nav>
		</div>
	</header>
	<main class="mx-auto max-w-5xl px-4 py-6">
		{@render children()}
	</main>
</div>
