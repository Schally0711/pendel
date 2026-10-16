<script lang="ts">
	import { getLocale, setLocale, locales } from '#lib/paraglide/runtime.js';
</script>

<div class="flex gap-1 text-xs">
	{#each locales as locale (locale)}
		<button
			class="rounded-md px-2 py-1 uppercase {locale === getLocale()
				? 'bg-white font-semibold shadow-sm dark:bg-slate-800'
				: 'muted hover:text-slate-900 dark:hover:text-white'}"
			onclick={() => setLocale(locale)}>{locale}</button
		>
	{/each}
</div>
