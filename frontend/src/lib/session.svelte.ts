import { api, ApiError } from './api';
import type { User } from './types';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';

class Auth {
	user = $state<User | null>(null);
	loaded = $state(false);

	async load(): Promise<void> {
		try {
			this.set(await api.get<User>('/me'));
		} catch (e) {
			if (!(e instanceof ApiError) || e.status !== 401) throw e;
			this.user = null;
		} finally {
			this.loaded = true;
		}
	}

	set(user: User | null): void {
		this.user = user;
		if (user && user.locale !== getLocale()) setLocale(user.locale, { reload: false });
	}

	get tz(): string {
		return this.user?.timezone ?? 'Europe/Berlin';
	}
}

export const auth = new Auth();
