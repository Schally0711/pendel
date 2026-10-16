<script lang="ts">
	let { message, tone = 'error' }: { message: string | null; tone?: 'error' | 'success' } = $props();
</script>

{#if message}
	<p
		class="rounded-xl px-3 py-2 text-sm {tone === 'error'
			? 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300'
			: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300'}"
		role={tone === 'error' ? 'alert' : 'status'}
	>
		{message}
	</p>
{/if}
