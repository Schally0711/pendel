// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	type ThemeMode = 'system' | 'light' | 'dark';
	interface Window {
		/** static/theme.js */
		pendelTheme: { get(): ThemeMode; set(mode: ThemeMode): void };
	}
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
