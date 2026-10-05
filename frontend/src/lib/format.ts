import type { DeviceState, Scene, Schedule } from './types';

export type ClockMode = '12h' | '24h';

export function formatHM(h: number, m: number, mode: ClockMode): string {
  const mm = String(m).padStart(2, '0');
  if (mode === '24h') return `${String(h).padStart(2, '0')}:${mm}`;
  return `${((h + 11) % 12) + 1}:${mm} ${h >= 12 ? 'PM' : 'AM'}`;
}

export function formatClock(d: Date, mode: ClockMode): string {
  return formatHM(d.getHours(), d.getMinutes(), mode);
}

/** "HH:MM" → [h, m], or null when it isn't a valid 24h time. */
export function parseHM(t: string): [number, number] | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(t);
  if (!match) return null;
  const h = Number(match[1]);
  const m = Number(match[2]);
  return h > 23 || m > 59 ? null : [h, m];
}

export function formatTime(t: string, mode: ClockMode): string {
  const hm = parseHM(t);
  return hm ? formatHM(hm[0], hm[1], mode) : t;
}

export function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

const WEEK = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const BY_JS_DAY = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

export function formatDays(days: string[] | null | undefined): string {
  if (!days || days.length === 0) return 'Every day';
  const sorted = [...new Set(days)].sort((a, b) => WEEK.indexOf(a) - WEEK.indexOf(b));
  const same = (want: string[]) => sorted.length === want.length && sorted.every((d, i) => d === want[i]);
  if (same(WEEK)) return 'Every day';
  if (same(WEEK.slice(0, 5))) return 'Weekdays';
  if (same(WEEK.slice(5))) return 'Weekends';
  return sorted.map((d) => d.charAt(0).toUpperCase() + d.slice(1)).join(' · ');
}

/** The enabled schedule that fires soonest after `now`, and when. */
export function nextSchedule(schedules: Schedule[], now: Date): { schedule: Schedule; at: Date } | null {
  let best: { schedule: Schedule; at: Date } | null = null;
  for (const schedule of schedules) {
    if (!schedule.enabled) continue;
    const hm = parseHM(schedule.time);
    if (!hm) continue;
    for (let offset = 0; offset <= 7; offset++) {
      const at = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset, hm[0], hm[1]);
      if (at <= now) continue;
      const days = schedule.days;
      if (days && days.length && !days.includes(BY_JS_DAY[at.getDay()])) continue;
      if (!best || at < best.at) best = { schedule, at };
      break;
    }
  }
  return best;
}

export function actionsSummary(scene: Scene): string {
  const n = scene.actions?.length ?? 0;
  return n === 1 ? '1 action' : `${n} actions`;
}

export function mediaText(state: DeviceState): string {
  const a = state.attributes ?? {};
  const track = typeof a.track === 'string' ? a.track : '';
  const artist = typeof a.artist === 'string' ? a.artist : '';
  return track && artist ? `${track} — ${artist}` : track || artist;
}
