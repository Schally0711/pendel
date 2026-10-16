import { ApiError } from './api';
import { m } from '#lib/paraglide/messages.js';

const KNOWN: Record<string, () => string> = {
	invalid_credentials: m.login_failed,
	too_many_attempts: m.too_many_attempts,
	email_taken: m.email_taken,
	invitation_invalid: m.invite_invalid,
	wrong_password: m.wrong_password,
	valid_from_taken: m.valid_from_taken,
	last_work_model: m.last_work_model,
	invalid_totp: m.invalid_totp,
	totp_required: m.totp_required,
	employment_overlap: m.employment_overlap,
	employment_open_not_last: m.employment_open_not_last,
	employment_end_before_start: m.employment_end_before_start,
	employment_invalid_end: m.employment_invalid_end,
	employment_still_active: m.employment_still_active,
	session_running: m.session_running,
	no_session_running: m.no_session_running,
	invalid_setup_code: m.invalid_setup_code,
	reset_link_invalid: m.reset_link_invalid,
	last_admin: m.last_admin,
	backup_not_pendel: m.backup_not_pendel,
	backup_damaged: m.backup_damaged,
	backup_too_new: m.backup_too_new,
	request_too_large: m.request_too_large
};

export function errorText(e: unknown): string {
	const code = e instanceof ApiError ? e.detail : 'network';
	return KNOWN[code]?.() ?? m.error_generic({ code });
}
