import { describe, expect, it } from 'vitest';
import { brightnessOf, deviceIcon, deviceSubtitle, isDimmable, isLight, sceneIcon } from './icons';
import type { Device } from './types';

const dev = (over: Partial<Device>): Device => ({
  id: 'd', name: 'D', device_type: 'switch', driver_name: 'KasaDriver',
  capabilities: ['toggle'], state: { power: false, attributes: {} }, ...over,
});

describe('lights', () => {
  it('dimmers, and toggleable kasa/relay devices, are lights', () => {
    expect(isLight(dev({ capabilities: ['toggle', 'dimmer'] }))).toBe(true);
    expect(isLight(dev({ driver_name: 'KasaDriver' }))).toBe(true);
    expect(isLight(dev({ driver_name: 'RelayDriver', device_type: 'relay' }))).toBe(true);
    expect(isLight(dev({ driver_name: 'SpotifyDriver', device_type: 'media', capabilities: ['media_control'] }))).toBe(false);
  });
  it('isDimmable', () => expect(isDimmable(dev({ capabilities: ['dimmer'] }))).toBe(true));
});

describe('brightnessOf', () => {
  it('reads and clamps attributes.brightness', () => {
    expect(brightnessOf(dev({ state: { power: true, attributes: { brightness: 42.4 } } }))).toBe(42);
    expect(brightnessOf(dev({ state: { power: true, attributes: { brightness: 140 } } }))).toBe(100);
    expect(brightnessOf(dev({ state: { power: true, attributes: {} } }))).toBeNull();
    expect(brightnessOf(dev({ state: { power: true, attributes: { brightness: 'hi' } } }))).toBeNull();
  });
});

describe('deviceIcon (same rules as app.js)', () => {
  it.each([
    [{ device_type: 'media' as const, driver_name: 'X' }, 'play'],
    [{ driver_name: 'SpotifyDriver' }, 'play'],
    [{ driver_name: 'KasaDriver' }, 'plug'],
    [{ driver_name: 'RelayDriver' }, 'power'],
    [{ driver_name: 'HueDriver', capabilities: ['dimmer' as const] }, 'lightbulb'],
    [{ driver_name: 'Other' }, 'power'],
  ])('%o → %s', (over, icon) => expect(deviceIcon(dev(over))).toBe(icon));
});

describe('sceneIcon', () => {
  it.each([
    ['bedtime', 'Bedtime', 'bed'],
    ['x', 'Good night', 'bed'],
    ['wakeup', 'Morning', 'sunrise'],
    ['movie', 'Movie', 'film'],
    ['away', 'Leaving', 'log-out'],
    ['misc', 'Party', 'power'],
  ])('%s/%s → %s', (id, name, icon) => expect(sceneIcon({ id, name, actions: [] })).toBe(icon));
});

describe('deviceSubtitle', () => {
  it('drops the Driver suffix', () => {
    expect(deviceSubtitle(dev({ driver_name: 'KasaDriver', device_type: 'switch' }))).toBe('Kasa · switch');
    expect(deviceSubtitle(dev({ driver_name: '', device_type: 'relay' }))).toBe('relay');
  });
});
