// Mirrors backend/pendel/schemas.py

export type PlaceKind = 'home' | 'office' | 'other';
export type BreakMode = 'manual' | 'auto';
export type DayKind =
	| 'vacation'
	| 'vacation_half'
	| 'sick'
	| 'flex_day'
	| 'special_leave'
	| 'release'
	| 'sick_child'
	| 'training'
	| 'parental_leave'
	| 'unpaid_leave'
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

export interface AbsencePeriod {
	start: string;
	end: string;
	kind: DayKind;
	note: string;
	workdays: number;
	vacation_days: number;
}

export interface VacationAccount {
	year: number;
	configured: boolean;
	days: number;
	carried_over: number;
	total: number;
	taken: number;
	planned: number;
	remaining: number;
	suggested_carry_over: number;
}

export interface ApiTokenInfo {
	id: number;
	name: string;
	created_at: string;
	last_used_at: string | null;
	revoked_at: string | null;
	token?: string;
}

export interface PendelEvent {
	id: number;
	occurred_at: string;
	received_at: string;
	type: string;
	zone: string | null;
	payload: { actions?: string[]; source?: string };
	processed: boolean;
}

export interface DayStat {
	day: string;
	target: number;
	actual: number;
	diff: number;
	balance: number;
	place: PlaceKind | null;
	entry: DayKind | null;
	holiday: string | null;
	start: number | null;
	end: number | null;
	breaks: number;
	commute_to: number;
	commute_from: number;
	warnings: number;
}

export interface PeriodStat {
	key: string;
	start: string;
	end: string;
	target: number;
	actual: number;
	diff: number;
	office_days: number;
	home_days: number;
	absence_days: number;
}

export interface StatsSummary {
	worked_days: number;
	target: number;
	actual: number;
	diff: number;
	balance_start: number;
	balance_end: number;
	avg_actual: number;
	office_days: number;
	home_days: number;
	other_days: number;
	absence_days: Record<string, number>;
	avg_start: number | null;
	avg_end: number | null;
	earliest_start: number | null;
	latest_end: number | null;
	avg_commute_to: number | null;
	avg_commute_from: number | null;
	commute_by_weekday: (number | null)[];
	longest_day: string | null;
	longest_minutes: number;
	overtime_days: number;
	warning_days: number;
}

export interface Stats {
	start: string;
	end: string;
	group: 'week' | 'month';
	days: DayStat[];
	periods: PeriodStat[];
	summary: StatsSummary;
}

export interface TaxOverview {
	year: number;
	until: string;
	offices: { place: string; distance_km: number | null; days: number; amount: number }[];
	office_days: number;
	commuter_total: number;
	commuter_rate: [number, number];
	home_office_days: number;
	home_office_days_counted: number;
	home_office_rate: number;
	home_office_max_days: number;
	home_office_total: number;
	missing_distance: boolean;
}

export interface CalendarStatus {
	active: boolean;
	created_at: string | null;
	last_used_at: string | null;
	url_path: string | null;
}
