import { describe, expect, it } from 'vitest';
import { actionsSummary, formatDays, formatHM, formatTime, mediaText, nextSchedule } from './format';
import type { Schedule } from './types';

const sched = (over: Partial<Schedule>): Schedule => ({
  id: 'x', name: 'X', scene_id: 'x', time: '07:00', days: null, enabled: true, ...over,
});

describe('formatHM / formatTime', () => {
  it('12h', () => {
    expect(formatHM(0, 5, '12h')).toBe('12:05 AM');
    expect(formatHM(12, 30, '12h')).toBe('12:30 PM');
    expect(formatHM(23, 0, '12h')).toBe('11:00 PM');
  });
  it('24h', () => {
    expect(formatHM(7, 5, '24h')).toBe('07:05');
    expect(formatHM(23, 0, '24h')).toBe('23:00');
  });
  it('formats schedule strings and passes through junk', () => {
    expect(formatTime('23:00', '12h')).toBe('11:00 PM');
    expect(formatTime('7:30', '24h')).toBe('07:30');
    expect(formatTime('soon', '12h')).toBe('soon');
    expect(formatTime('25:00', '12h')).toBe('25:00');
  });
});

describe('formatDays', () => {
  it('labels common sets', () => {
    expect(formatDays(null)).toBe('Every day');
    expect(formatDays([])).toBe('Every day');
    expect(formatDays(['fri', 'mon', 'tue', 'wed', 'thu'])).toBe('Weekdays');
    expect(formatDays(['sun', 'sat'])).toBe('Weekends');
    expect(formatDays(['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])).toBe('Every day');
  });
  it('lists others in week order', () => {
    expect(formatDays(['wed', 'mon'])).toBe('Mon · Wed');
  });
});

describe('nextSchedule', () => {
  const sun2200 = new Date(2026, 9, 4, 22, 0); // Sunday
  const bedtime = sched({ id: 'bed', name: 'Bedtime', time: '23:00' });
  const wake = sched({ id: 'wake', name: 'Wake', time: '07:00', days: ['mon', 'tue', 'wed', 'thu', 'fri'] });

  it('picks the earliest upcoming run', () => {
    const next = nextSchedule([wake, bedtime], sun2200);
    expect(next?.schedule.id).toBe('bed');
    expect(next?.at).toEqual(new Date(2026, 9, 4, 23, 0));
  });

  it('crosses midnight', () => {
    const next = nextSchedule([wake, bedtime], new Date(2026, 9, 4, 23, 30));
    expect(next?.schedule.id).toBe('wake');
    expect(next?.at).toEqual(new Date(2026, 9, 5, 7, 0));
  });

  it('wraps a full week', () => {
    const sundayEvening = sched({ id: 'sun', time: '21:00', days: ['sun'] });
    expect(nextSchedule([sundayEvening], sun2200)?.at).toEqual(new Date(2026, 9, 11, 21, 0));
  });

  it('ignores disabled and malformed schedules', () => {
    expect(nextSchedule([sched({ enabled: false }), sched({ time: 'later' })], sun2200)).toBeNull();
  });
});

describe('small labels', () => {
  it('actionsSummary', () => {
    expect(actionsSummary({ id: 'a', name: 'A', actions: [] })).toBe('0 actions');
    expect(actionsSummary({ id: 'a', name: 'A', actions: [{ device_id: 'd', action: 'toggle' }] })).toBe('1 action');
  });
  it('mediaText', () => {
    expect(mediaText({ power: true, attributes: { track: 'Roundabout', artist: 'Yes' } })).toBe('Roundabout — Yes');
    expect(mediaText({ power: true, attributes: { track: 'Roundabout' } })).toBe('Roundabout');
    expect(mediaText({ power: false, attributes: {} })).toBe('');
  });
});
