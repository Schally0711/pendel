// Date/time helpers. All API timestamps are ISO strings with offset; dates are YYYY-MM-DD.
// Local day boundaries and inputs use the user's time zone, not necessarily the browser's.

export function minutesBetween(start: string, end: string | null, now = new Date()): number {
	const e = end ? new Date(end) : now;
	return Math.max(0, (e.getTime() - new Date(start).getTime()) / 60000);
}

/** 450 -> "7:30" */
export function hm(minutes: number): string {
	const m = Math.round(Math.abs(minutes));
	const s = `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
	return minutes < 0 && m > 0 ? `−${s}` : s;
}

/** Signed duration for balances: "+1:15", "−0:30", "±0:00" */
export function signedHm(minutes: number): string {
	const m = Math.round(minutes);
	if (m === 0) return '±0:00';
	return m > 0 ? `+${hm(m)}` : hm(m);
}

/** Running clock "1:02:09" */
export function clock(minutes: number): string {
	const total = Math.floor(minutes * 60);
	const h = Math.floor(total / 3600);
	const m = Math.floor((total % 3600) / 60);
	const s = total % 60;
	return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function parts(date: Date, tz: string) {
	const f = new Intl.DateTimeFormat('en-CA', {
		timeZone: tz,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		second: '2-digit',
		hourCycle: 'h23'
	});
	const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
	return { date: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}`, second: p.second };
}

/** Local calendar date (YYYY-MM-DD) of an instant in the given time zone. */
export function localDate(value: string | Date, tz: string): string {
	return parts(new Date(value), tz).date;
}

/** Local wall-clock time (HH:MM) of an instant in the given time zone. */
export function localTime(value: string | Date, tz: string): string {
	return parts(new Date(value), tz).time;
}

/** Convert a wall-clock date + time in `tz` to an ISO string with offset (UTC). */
export function zonedToIso(date: string, time: string, tz: string): string {
	const [y, mo, d] = date.split('-').map(Number);
	const [h, mi] = time.split(':').map(Number);
	const guess = Date.UTC(y, mo - 1, d, h, mi);
	// Offset of tz at the guessed instant; a second pass handles DST transitions.
	let ts = guess;
	for (let i = 0; i < 2; i++) {
		const p = parts(new Date(ts), tz);
		const [py, pmo, pd] = p.date.split('-').map(Number);
		const [ph, pmi] = p.time.split(':').map(Number);
		const asUtc = Date.UTC(py, pmo - 1, pd, ph, pmi);
		ts = guess - (asUtc - ts);
	}
	return new Date(ts).toISOString();
}

export function addDays(date: string, days: number): string {
	const d = new Date(`${date}T12:00:00Z`);
	d.setUTCDate(d.getUTCDate() + days);
	return d.toISOString().slice(0, 10);
}

export function weekday(date: string): number {
	// 0 = Monday
	return (new Date(`${date}T12:00:00Z`).getUTCDay() + 6) % 7;
}

export function formatDate(date: string, locale: string, opts: Intl.DateTimeFormatOptions): string {
	return new Intl.DateTimeFormat(locale, { timeZone: 'UTC', ...opts }).format(new Date(`${date}T12:00:00Z`));
}

export function monthRange(month: string): { from: string; to: string } {
	const [y, m] = month.split('-').map(Number);
	const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
	return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, '0')}` };
}

export function shiftMonth(month: string, delta: number): string {
	const [y, m] = month.split('-').map(Number);
	const d = new Date(Date.UTC(y, m - 1 + delta, 1));
	return d.toISOString().slice(0, 7);
}
