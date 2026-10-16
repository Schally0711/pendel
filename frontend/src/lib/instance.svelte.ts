import { api } from './api.js';

/** Instance info; `baseUrl` is the address used in links shared outside the browser. */
class Instance {
	publicUrl = $state<string | null>(null);
	version = $state('');
	loaded = false;

	async load(force = false): Promise<void> {
		if (this.loaded && !force) return;
		const r = await api.get<{ version: string; public_url: string | null }>('/instance');
		this.publicUrl = r.public_url;
		this.version = r.version;
		this.loaded = true;
	}

	get baseUrl(): string {
		return this.publicUrl ?? (typeof location !== 'undefined' ? location.origin : '');
	}
}

export const instance = new Instance();
