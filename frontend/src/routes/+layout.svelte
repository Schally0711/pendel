<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { api, isPublicPath } from '#lib/api.js';
	import { auth } from '#lib/session.svelte.js';
	import favicon from '#lib/assets/favicon.svg';
	import { Clock, CalendarDays, ChartColumn, Palmtree, Settings, Users } from '@lucide/svelte';
	import './layout.css';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();

	const isPublic = $derived(isPublicPath(page.url.pathname));
	let ready = $state(false);

	onMount(async () => {
		const { needed } = await api.get<{ needed: boolean }>('/setup');
		if (needed) {
			// navigate first, otherwise the login redirect below would win
			await goto('/setup');
			ready = true;
			return;
		}
		await auth.load();
		ready = true;
	});

	$effect(() => {
		if (ready && !auth.user && !isPublic) goto('/login');
	});

	const nav = $derived([
		{ href: '/', label: m.nav_today(), icon: Clock },
		{ href: '/history', label: m.nav_history(), icon: CalendarDays },
		{ href: '/absences', label: m.nav_absences(), icon: Palmtree },
		{ href: '/stats', label: m.nav_stats(), icon: ChartColumn },
		{ href: '/settings', label: m.nav_settings(), icon: Settings },
		...(auth.user?.is_admin ? [{ href: '/admin', label: m.nav_admin(), icon: Users, desktopOnly: true }] : [])
	]);

	function active(href: string) {
		return href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{#if !ready}
	<div class="grid min-h-dvh place-items-center muted">{m.loading()}</div>
{:else if isPublic || !auth.user}
	{@render children()}
{:else}
	<div class="min-h-dvh pb-24 md:pb-0 print:pb-0">
		<header
			class="sticky top-0 z-20 print:hidden border-b border-slate-200/70 bg-slate-100/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80"
		>
			<div class="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
				<a href="/" class="flex items-center gap-2 text-lg font-semibold tracking-tight">
					<img src={favicon} alt="" class="size-7" />
					Pendel
				</a>
				<nav class="hidden gap-1 md:flex">
					{#each nav as item (item.href)}
						<a
							href={item.href}
							class="rounded-lg px-3 py-1.5 text-sm font-medium transition {active(item.href)
								? 'bg-white text-brand-700 shadow-sm dark:bg-slate-800 dark:text-brand-400'
								: 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white'}"
							>{item.label}</a
						>
					{/each}
				</nav>
				<a
					href="/account"
					class="ml-auto flex items-center gap-2 rounded-full py-1 pr-1 pl-3 text-sm font-medium transition hover:bg-white dark:hover:bg-slate-800 {active('/account')
						? 'bg-white text-brand-700 shadow-sm dark:bg-slate-800 dark:text-brand-400'
						: 'text-slate-600 dark:text-slate-300'}"
					title={m.account()}
				>
					<span class="hidden sm:inline">{auth.user.display_name}</span>
					<span
						class="grid size-8 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700 dark:bg-brand-900/50 dark:text-brand-300"
						>{auth.user.display_name.slice(0, 1).toUpperCase()}</span
					>
				</a>
			</div>
		</header>

		<main class="mx-auto max-w-5xl px-4 py-6 print:max-w-none print:p-0">
			{@render children()}
		</main>

		<nav
			class="fixed inset-x-0 bottom-0 z-20 print:hidden border-t border-slate-200 bg-white/90 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden dark:border-slate-800 dark:bg-slate-900/90"
		>
			<div class="mx-auto flex max-w-md justify-around">
				{#each nav.filter((i) => !('desktopOnly' in i)) as item (item.href)}
					<a
						href={item.href}
						class="flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium {active(item.href)
							? 'text-brand-600 dark:text-brand-400'
							: 'text-slate-500'}"
					>
						<item.icon class="size-5" />
						{item.label}
					</a>
				{/each}
			</div>
		</nav>
	</div>
{/if}
