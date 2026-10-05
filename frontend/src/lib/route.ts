// Hash routes: '#/devices?open=lamp'. Everything after '#' stays in the
// browser; the server always serves the same index.html.

export interface Route {
  path: string[];
  query: Record<string, string>;
}

export const TABS = ['home', 'devices', 'scenes', 'schedules', 'settings'] as const;
export type Tab = (typeof TABS)[number];

export const TITLES: Record<Tab, string> = {
  home: 'Home',
  devices: 'Devices',
  scenes: 'Scenes',
  schedules: 'Schedules',
  settings: 'Settings',
};

export type Screen =
  | { kind: 'home' }
  | { kind: 'devices'; open?: string }
  | { kind: 'scenes' }
  | { kind: 'schedules' }
  | { kind: 'settings' };

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, '');
  const [p, q = ''] = raw.split('?');
  const path = p.split('/').filter(Boolean).map(decodeURIComponent);
  return { path: path.length ? path : ['home'], query: Object.fromEntries(new URLSearchParams(q)) };
}

export function buildHash(path: string[], query: Record<string, string | undefined> = {}): string {
  const pairs = Object.entries(query).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== '');
  const qs = new URLSearchParams(pairs).toString();
  return `#/${path.map(encodeURIComponent).join('/')}${qs ? `?${qs}` : ''}`;
}

export function isTab(s: string | undefined): s is Tab {
  return (TABS as readonly string[]).includes(s ?? '');
}

/** The screen a route shows, or null when nothing lives there (redirect home). */
export function matchRoute(route: Route): Screen | null {
  const [tab] = route.path;
  if (route.path.length !== 1 || !isTab(tab)) return null;
  if (tab === 'devices') return route.query.open ? { kind: 'devices', open: route.query.open } : { kind: 'devices' };
  return { kind: tab };
}

/** Slide direction when moving between tabs: by position in the pill. */
export function tabDirection(from: Tab, to: Tab): 'forward' | 'back' {
  return TABS.indexOf(to) < TABS.indexOf(from) ? 'back' : 'forward';
}
