// Mirrors backend/pendel/schemas.py

export type PlaceKind = 'home' | 'office' | 'other';
export type BreakMode = 'manual' | 'auto';
export type DayKind =
	| 'vacation'
	| 'vacation_half'
	| 'sick'
	| 'flex_day'
	| 'special_leave'
	| 'public_holiday'
	| 'workday';
export type CommuteDirection = 'to_work' | 'from_work';

export interface User {
	id: number;
	email: string;
	display_name: string;
	locale: 'de' | 'en';
	timezone: string;
	country: string;
	subdivision: string | null;
	is_admin: boolean;
}

export interface Place {
	id: number;
	name: string;
	kind: PlaceKind;
	distance_km: number | null;
	zone: string | null;
	archived: boolean;
}

export interface WorkModel {
	id?: number;
	valid_from: string;
	name: string;
	target_mon: number;
	target_tue: number;
	target_wed: number;
	target_thu: number;
	target_fri: number;
	target_sat: number;
	target_sun: number;
	flexitime: boolean;
	break_mode: BreakMode;
	auto_break_minutes: number;
	auto_break_min_work_minutes: number;
	legal_break_check: boolean;
	office_gap_break_max_minutes: number;
	commute_credit_percent: number;
}

export interface Adjustment {
	id?: number;
	day: string;
	minutes: number;
	note: string;
}

export interface Break {
	id: number;
	start: string;
	end: string | null;
	kind: 'manual' | 'office_gap';
	deducted: boolean;
	note: string;
}

export interface WorkSession {
	id: number;
	kind: PlaceKind;
	place_id: number | null;
	start: string;
	end: string | null;
	source: 'manual' | 'automatic';
	note: string;
	breaks: Break[];
}

export interface Commute {
	id: number;
	direction: CommuteDirection;
	start: string;
	end: string | null;
	from_place_id: number | null;
	to_place_id: number | null;
	source: 'manual' | 'automatic';
	note: string;
}

export interface Day {
	day: string;
	target: number;
	actual: number;
	diff: number;
	gross: number;
	breaks_recorded: number;
	breaks_effective: number;
	commute: number;
	commute_credit: number;
	warnings: string[];
	holiday: string | null;
	entry: DayKind | null;
	kinds: PlaceKind[];
}

export interface Report {
	start: string;
	end: string;
	days: Day[];
	target: number;
	actual: number;
	diff: number;
	balance: number;
}

export interface Today {
	now: string;
	day: Day;
	running_session: WorkSession | null;
	running_break: Break | null;
	running_commute: Commute | null;
	balance: number;
	balance_before_today: number;
	week_actual: number;
	week_target: number;
}

export interface Invitation {
	id: number;
	note: string;
	created_at: string;
	expires_at: string;
	used_at: string | null;
	token?: string;
}

export interface Subdivision {
	code: string;
	name: string;
}

export interface Segment {
	start: string;
	end: string | null;
	type: PlaceKind | 'travel' | 'break';
}
