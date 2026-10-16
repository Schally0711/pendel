import { ApiError } from './api';
import { m } from '#lib/paraglide/messages.js';

const KNOWN: Record<string, () => string> = {
	invalid_credentials: m.login_failed,
	too_many_attempts: m.too_many_attempts,
	email_taken: m.email_taken,
	invitation_invalid: m.invite_invalid,
	wrong_password: m.wrong_password,
	valid_from_taken: m.valid_from_taken,
	last_work_model: m.last_work_model
};

export function errorText(e: unknown): string {
	const code = e instanceof ApiError ? e.detail : 'network';
	return KNOWN[code]?.() ?? m.error_generic({ code });
}
