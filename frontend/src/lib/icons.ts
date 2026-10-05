import type { Capability, Device, Scene } from './types';

export function hasCap(d: Device, cap: Capability): boolean {
  return Array.isArray(d.capabilities) && d.capabilities.includes(cap);
}

export function isDimmable(d: Device): boolean {
  return hasCap(d, 'dimmer');
}

/** Dimmers, plus toggleable Kasa/relay devices (plugs driving a lamp). */
export function isLight(d: Device): boolean {
  if (isDimmable(d)) return true;
  const drv = (d.driver_name || '').toLowerCase();
  return hasCap(d, 'toggle') && (drv.includes('kasa') || drv.includes('relay'));
}

export function brightnessOf(d: Device): number | null {
  const b = d.state?.attributes?.brightness;
  return typeof b === 'number' && Number.isFinite(b) ? Math.max(0, Math.min(100, Math.round(b))) : null;
}

export function deviceIcon(d: Device): string {
  const drv = (d.driver_name || '').toLowerCase();
  const type = (d.device_type || '').toLowerCase();
  if (type === 'media' || drv.includes('spotify')) return 'play';
  if (drv.includes('kasa')) return 'plug';
  if (drv.includes('relay')) return 'power';
  if (isDimmable(d)) return 'lightbulb';
  return 'power';
}

export function sceneIcon(scene: Scene): string {
  const haystack = `${scene.id ?? ''} ${scene.name ?? ''}`.toLowerCase();
  if (/(bed|night|sleep)/.test(haystack)) return 'bed';
  if (/(morn|wake|sunrise)/.test(haystack)) return 'sunrise';
  if (/(movie|film|cinema)/.test(haystack)) return 'film';
  if (/(away|leave|out)/.test(haystack)) return 'log-out';
  return 'power';
}

export function deviceSubtitle(d: Device): string {
  const type = d.device_type || '';
  const drv = (d.driver_name || '').replace(/Driver$/, '');
  return drv && type ? `${drv} · ${type}` : drv || type;
}
