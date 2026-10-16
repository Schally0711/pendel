<script lang="ts">
	import type { Snippet } from 'svelte';
	import { X } from '@lucide/svelte';
	import { m } from '#lib/paraglide/messages.js';

	let { title, onclose, children }: { title: string; onclose: () => void; children: Snippet } = $props();
	let dialog: HTMLDialogElement;

	$effect(() => {
		dialog.showModal();
	});
</script>

<dialog
	bind:this={dialog}
	{onclose}
	class="m-0 mt-auto max-h-[92dvh] w-full max-w-none overflow-y-auto rounded-t-3xl bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/50 backdrop:backdrop-blur-sm sm:m-auto sm:max-w-xl sm:rounded-3xl dark:bg-slate-900 dark:text-slate-100"
>
	<div class="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white/95 px-5 py-4 backdrop-blur dark:border-slate-800 dark:bg-slate-900/95">
		<h2 class="text-base font-semibold">{title}</h2>
		<button class="btn-ghost p-1.5" onclick={() => dialog.close()} aria-label={m.close()}>
			<X class="size-5" />
		</button>
	</div>
	<div class="p-5">{@render children()}</div>
</dialog>
