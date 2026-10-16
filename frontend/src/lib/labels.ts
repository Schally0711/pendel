import { m } from '#lib/paraglide/messages.js';
import type { DayKind, PlaceKind } from './types.js';

/** Absence kinds offered in pickers, most common first. */
export const ABSENCE_KINDS: DayKind[] = [
	'vacation',
	'vacation_half',
	'sick',
	'sick_child',
	'flex_day',
	'release',
	'special_leave',
	'training',
	'parental_leave',
	'unpaid_leave',
	'public_holiday'
];

export const DAY_KINDS: DayKind[] = [...ABSENCE_KINDS, 'workday'];

const DAY_LABEL: Record<DayKind, () => string> = {
	vacation: m.day_vacation,
	vacation_half: m.day_vacation_half,
	sick: m.day_sick,
	sick_child: m.day_sick_child,
	flex_day: m.day_flex_day,
	release: m.day_release,
	special_leave: m.day_special_leave,
	training: m.day_training,
	parental_leave: m.day_parental_leave,
	unpaid_leave: m.day_unpaid_leave,
	public_holiday: m.day_public_holiday,
	workday: m.day_workday
};

export const dayKindLabel = (k: DayKind) => DAY_LABEL[k]();

/** Badge classes (background + text) per day kind. */
export const DAY_BADGE: Record<DayKind, string> = {
	vacation: 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300',
	vacation_half: 'bg-sky-50 text-sky-600 dark:bg-sky-950/60 dark:text-sky-300',
	sick: 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300',
	sick_child: 'bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300',
	flex_day: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
	release: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
	special_leave: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
	training: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
	parental_leave: 'bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300',
	unpaid_leave: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
	public_holiday: 'bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300',
	workday: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
};

/** Solid colour per day kind (calendar cells). */
export const DAY_DOT: Record<DayKind, string> = {
	vacation: 'bg-sky-500',
	vacation_half: 'bg-sky-300',
	sick: 'bg-rose-500',
	sick_child: 'bg-pink-400',
	flex_day: 'bg-amber-400',
	release: 'bg-indigo-400',
	special_leave: 'bg-indigo-400',
	training: 'bg-emerald-500',
	parental_leave: 'bg-teal-500',
	unpaid_leave: 'bg-slate-400',
	public_holiday: 'bg-violet-400',
	workday: 'bg-slate-300'
};

export const placeKindLabel = (k: PlaceKind) =>
	k === 'home' ? m.kind_home() : k === 'office' ? m.kind_office() : m.kind_other();

const ACTIONS: Record<string, () => string> = {
	commute_to_work_started: m.act_commute_to_work_started,
	commute_to_work_ended: m.act_commute_to_work_ended,
	commute_to_work_discarded: m.act_commute_to_work_discarded,
	commute_from_work_recorded: m.act_commute_from_work_recorded,
	commute_from_work_ended: m.act_commute_from_work_ended,
	commute_from_work_discarded: m.act_commute_from_work_discarded,
	office_session_started: m.act_office_session_started,
	office_session_ended: m.act_office_session_ended,
	home_session_ended: m.act_home_session_ended,
	office_gap_started: m.act_office_gap_started,
	gap_closed_break: m.act_gap_closed_break,
	gap_closed_work: m.act_gap_closed_work,
	gap_dropped_jitter: m.act_gap_dropped_jitter,
	ignored_no_workday: m.act_ignored_no_workday,
	ignored_unknown_zone: m.act_ignored_unknown_zone,
	device_session_started: m.act_device_session_started,
	ignored_absence: m.act_ignored_absence,
	ignored_already_running: m.act_ignored_already_running,
	ignored_commuting: m.act_ignored_commuting,
	ignored_already_worked: m.act_ignored_already_worked,
	no_change: m.act_no_change
};

export const actionLabel = (a: string) => ACTIONS[a]?.() ?? a;
