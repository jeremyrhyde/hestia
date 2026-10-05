// Store core. Operates on a state object it is handed (a $state proxy in the
// app, a plain object in tests). Writes are optimistic: apply locally, call the
// API, reconcile with the server's answer, roll back + toast on failure. A
// device with a write in flight keeps its local state against live events and
// refetches — the write's own response is authoritative.

import type { Api } from './api';
import { brightnessOf, isLight } from './icons';
import type { Device, DeviceActionName, DeviceState, Health, Scene, Schedule, WsEvent } from './types';

export interface HestiaState {
  devices: Device[];
  scenes: Scene[];
  schedules: Schedule[];
  health: Health | null;
  ready: boolean;
  error: string | null;
  /** Bumped when a scene ran elsewhere (another client, a schedule). */
  ripple: { id: string; n: number } | null;
}

export function initialState(): HestiaState {
  return { devices: [], scenes: [], schedules: [], health: null, ready: false, error: null, ripple: null };
}

type ToastFn = (text: string, kind?: 'info' | 'error', action?: { label: string; run: () => void }) => void;

export interface StoreDeps {
  api: Pick<Api, 'health' | 'devices' | 'scenes' | 'schedules' | 'deviceAction' | 'executeScene' | 'setScheduleEnabled'>;
  toast: ToastFn;
  now?: () => number;
  debounceMs?: number;
}

/** A scene event during our own run, or within this long after it returns, is ours. */
export const LOCAL_RUN_WINDOW_MS = 2000;
/** A schedule announcement waits this long for its scene to finish. */
export const ANNOUNCE_TTL_MS = 10 * 60_000;

export const LIVE_EVENT_TYPES = [
  'device_state_changed',
  'device_registered',
  'scene_executed',
  'device_error',
  'schedule_triggered',
] as const;

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

function isDeviceState(v: unknown): v is DeviceState {
  return !!v && typeof v === 'object' && typeof (v as DeviceState).power === 'boolean';
}

export function createStore(s: HestiaState, deps: StoreDeps) {
  const now = deps.now ?? (() => Date.now());
  const debounceMs = deps.debounceMs ?? 150;
  let loadSeq = 0;
  const pending = new Map<string, number>();
  const dimming = new Map<string, { seq: number; base: DeviceState; timer: ReturnType<typeof setTimeout> | null }>();
  const localRuns = new Map<string, number>();
  const announced = new Map<string, number>();

  const find = (id: string) => s.devices.find((d) => d.id === id);
  const isPending = (id: string) => pending.has(id) || dimming.has(id);
  const begin = (id: string) => pending.set(id, (pending.get(id) ?? 0) + 1);
  const end = (id: string) => {
    const n = (pending.get(id) ?? 1) - 1;
    if (n <= 0) pending.delete(id);
    else pending.set(id, n);
  };
  const recent = (map: Map<string, number>, id: string) => {
    const t = map.get(id);
    return t !== undefined && now() - t <= LOCAL_RUN_WINDOW_MS;
  };

  async function loadAll(): Promise<void> {
    const seq = ++loadSeq;
    try {
      const [devices, scenes, schedules, health] = await Promise.all([
        deps.api.devices(),
        deps.api.scenes(),
        deps.api.schedules(),
        deps.api.health(),
      ]);
      if (seq !== loadSeq) return;
      s.devices = devices.map((d) => (isPending(d.id) ? { ...d, state: find(d.id)?.state ?? d.state } : d));
      s.scenes = scenes;
      s.schedules = schedules;
      s.health = health;
      s.error = null;
      s.ready = true;
    } catch (e) {
      if (seq !== loadSeq) return;
      if (s.ready) deps.toast(message(e), 'error');
      else s.error = message(e);
    }
  }

  async function refreshHealth(): Promise<void> {
    try {
      s.health = await deps.api.health();
    } catch {
      // The next poll retries; the connection banner covers outages.
    }
  }

  async function act(
    id: string,
    action: DeviceActionName,
    params: Record<string, unknown> | undefined,
    optimistic: (st: DeviceState) => DeviceState,
    quiet = false,
  ): Promise<boolean> {
    const d = find(id);
    if (!d) return false;
    const prev = d.state;
    d.state = optimistic(prev);
    begin(id);
    try {
      const next = await deps.api.deviceAction(id, action, params);
      const cur = find(id);
      if (cur) cur.state = next;
      return true;
    } catch (e) {
      const cur = find(id);
      if (cur) cur.state = prev;
      if (!quiet) deps.toast(`${d.name}: ${message(e)}`, 'error');
      return false;
    } finally {
      end(id);
    }
  }

  const toggle = (id: string) => act(id, 'toggle', undefined, (st) => ({ ...st, power: !st.power }));
  const play = (id: string) => act(id, 'play', undefined, (st) => ({ ...st, power: true }));
  const pause = (id: string) => act(id, 'pause', undefined, (st) => ({ ...st, power: false }));

  /** Dragging: debounced sends; `final` (release/keyboard) sends at once. The
   *  dim session ends when the latest send settles with nothing queued. */
  function setBrightness(id: string, level: number, opts: { final: boolean }): void {
    const d = find(id);
    if (!d) return;
    let entry = dimming.get(id);
    if (!entry) {
      entry = { seq: 0, base: d.state, timer: null };
      dimming.set(id, entry);
    }
    d.state = { ...d.state, attributes: { ...d.state.attributes, brightness: level } };
    if (entry.timer) clearTimeout(entry.timer);
    entry.timer = null;
    if (opts.final) {
      void sendBrightness(id, level);
    } else {
      const e = entry;
      e.timer = setTimeout(() => {
        e.timer = null;
        void sendBrightness(id, level);
      }, debounceMs);
    }
  }

  async function sendBrightness(id: string, level: number): Promise<void> {
    const entry = dimming.get(id);
    if (!entry) return;
    const seq = ++entry.seq;
    begin(id);
    try {
      const next = await deps.api.deviceAction(id, 'set_brightness', { level });
      const cur = find(id);
      if (entry.seq === seq && cur) {
        // A queued debounce means the finger is still moving: take the server's
        // state but keep the local level, or the controlled slider snaps back.
        cur.state = entry.timer === null
          ? next
          : { ...next, attributes: { ...next.attributes, brightness: cur.state.attributes.brightness } };
      }
    } catch (e) {
      if (entry.seq === seq) {
        const cur = find(id);
        if (cur) cur.state = entry.base;
        deps.toast(`${cur?.name ?? id}: ${message(e)}`, 'error');
      }
    } finally {
      end(id);
      if (entry.seq === seq && entry.timer === null && dimming.get(id) === entry) dimming.delete(id);
    }
  }

  async function runScene(id: string): Promise<boolean> {
    localRuns.set(id, Number.POSITIVE_INFINITY); // in flight: always ours
    try {
      await deps.api.executeScene(id);
      return true;
    } catch (e) {
      const scene = s.scenes.find((x) => x.id === id);
      deps.toast(`${scene?.name ?? id}: ${message(e)}`, 'error');
      return false;
    } finally {
      localRuns.set(id, now());
    }
  }

  async function setScheduleEnabled(id: string, enabled: boolean): Promise<void> {
    const sch = s.schedules.find((x) => x.id === id);
    if (!sch) return;
    const prev = sch.enabled;
    sch.enabled = enabled;
    try {
      const updated = await deps.api.setScheduleEnabled(id, enabled);
      const i = s.schedules.findIndex((x) => x.id === id);
      if (i >= 0) s.schedules[i] = updated;
    } catch (e) {
      const cur = s.schedules.find((x) => x.id === id);
      if (cur) cur.enabled = prev;
      deps.toast(`${sch.name}: ${message(e)}`, 'error');
    }
  }

  async function restore(snapshot: { id: string; level: number | null }[]): Promise<void> {
    await Promise.all(
      snapshot.map(async ({ id, level }) => {
        const ok = await act(id, 'turn_on', undefined, (st) => ({ ...st, power: true }));
        if (ok && level !== null) {
          await act(id, 'set_brightness', { level }, (st) => ({ ...st, attributes: { ...st.attributes, brightness: level } }));
        }
      }),
    );
  }

  /** Turn off every light that's on, except the ids in *skip* (hidden on this display). */
  async function allOff(skip: readonly string[] = []): Promise<void> {
    const targets = s.devices.filter((d) => isLight(d) && d.state.power && !skip.includes(d.id));
    if (!targets.length) return;
    const snapshot = targets.map((d) => ({ id: d.id, level: brightnessOf(d) }));
    const results = await Promise.all(
      targets.map((d) => act(d.id, 'turn_off', undefined, (st) => ({ ...st, power: false }), true)),
    );
    const failed = results.filter((ok) => !ok).length;
    if (failed) {
      deps.toast(`${failed} of ${targets.length} lights didn't respond`, 'error');
      return;
    }
    deps.toast('All off', 'info', { label: 'Undo', run: () => void restore(snapshot) });
  }

  function handleEvent(event: WsEvent): void {
    const data = event.data ?? {};
    switch (event.type) {
      case 'device_state_changed': {
        const id = event.device_id;
        if (!id || isPending(id)) return;
        const d = find(id);
        if (d && isDeviceState(data.state)) d.state = data.state;
        return;
      }
      case 'device_registered': {
        const info = data.info as Device | undefined;
        if (!info || typeof info.id !== 'string') return;
        const i = s.devices.findIndex((d) => d.id === info.id);
        if (i >= 0) s.devices[i] = isPending(info.id) ? { ...info, state: s.devices[i].state } : info;
        else s.devices.push(info);
        return;
      }
      case 'scene_executed': {
        const id = data.scene_id;
        if (typeof id !== 'string' || recent(localRuns, id)) return;
        s.ripple = { id, n: (s.ripple?.n ?? 0) + 1 };
        const a = announced.get(id);
        announced.delete(id);
        if (a === undefined || now() - a > ANNOUNCE_TTL_MS) deps.toast(`${s.scenes.find((x) => x.id === id)?.name ?? id} ran`);
        return;
      }
      case 'device_error': {
        const d = event.device_id ? find(event.device_id) : undefined;
        const err = typeof data.error === 'string' ? data.error : 'device error';
        deps.toast(`${d?.name ?? event.device_id ?? 'Device'}: ${err}`, 'error');
        return;
      }
      case 'schedule_triggered': {
        const sch = s.schedules.find((x) => x.id === data.schedule_id);
        if (typeof data.scene_id === 'string') announced.set(data.scene_id, now());
        deps.toast(`${sch?.name ?? 'Schedule'} ran`);
        return;
      }
    }
  }

  return {
    loadAll, refreshHealth, toggle, play, pause, setBrightness, runScene,
    setScheduleEnabled, allOff, handleEvent, isPending,
  };
}

export type Store = ReturnType<typeof createStore>;
