/** Small helpers for the SVG charts (no chart library). */

export function linear(d0: number, d1: number, r0: number, r1: number) {
	const span = d1 - d0 || 1;
	return (v: number) => r0 + ((v - d0) / span) * (r1 - r0);
}

/** "Nice" tick values covering [min, max], roughly `count` of them. */
export function niceTicks(min: number, max: number, count = 4): number[] {
	if (min === max) {
		min -= 1;
		max += 1;
	}
	const raw = (max - min) / count;
	const mag = 10 ** Math.floor(Math.log10(raw));
	const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((s) => raw <= s) ?? 10 * mag;
	const out = [];
	for (let v = Math.floor(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
	if (out[out.length - 1] < max) out.push(out[out.length - 1] + step);
	return out;
}

/** Ticks in hours for values given in minutes (multiples of 1, 2, 5, 10 … hours). */
export function hourTicks(minMinutes: number, maxMinutes: number, count = 4): number[] {
	return niceTicks(minMinutes / 60, maxMinutes / 60, count).map((h) => h * 60);
}

export const fmtHours = (minutes: number) => `${Math.round(minutes / 6) / 10}`.replace('.', ',');
