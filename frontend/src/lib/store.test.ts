import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ANNOUNCE_TTL_MS, createStore, initialState, type HestiaState, type StoreDeps } from './store';
import type { Device, DeviceState, Health, Scene, Schedule } from './types';

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const lamp = (over: Partial<Device> = {}): Device => ({
  id: 'lamp', name: 'Lamp', device_type: 'switch', driver_name: 'KasaDriver',
  capabilities: ['toggle', 'dimmer'], state: { power: true, attributes: { brightness: 40 } }, ...over,
});
const plug = (over: Partial<Device> = {}): Device => ({
  id: 'plug', name: 'Plug', device_type: 'switch', driver_name: 'KasaDriver',
  capabilities: ['toggle'], state: { power: true, attributes: {} }, ...over,
});
const movie: Scene = { id: 'movie', name: 'Movie', actions: [] };
const bedtime: Schedule = { id: 'bedtime', name: 'Bedtime', scene_id: 'movie', time: '23:00', days: null, enabled: true };
const health: Health = { status: 'ok', devices_registered: 2, devices_failed: [] };
const on = (attrs: Record<string, unknown> = {}): DeviceState => ({ power: true, attributes: attrs });
const off = (attrs: Record<string, unknown> = {}): DeviceState => ({ power: false, attributes: attrs });

function setup(devices: Device[] = [lamp(), plug()]) {
  const api = {
    health: vi.fn(async () => health),
    devices: vi.fn(async () => structuredClone(devices)),
    scenes: vi.fn(async () => [movie]),
    schedules: vi.fn(async () => [bedtime]),
    deviceAction: vi.fn(async (_id: string, _a: string, _p?: Record<string, unknown>) => on()),
    executeScene: vi.fn(async () => []),
    setScheduleEnabled: vi.fn(async (id: string, enabled: boolean) => ({ ...bedtime, id, enabled })),
  } satisfies StoreDeps['api'];
  const toast = vi.fn();
  let t = 1_000;
  const s: HestiaState = initialState();
  const store = createStore(s, { api, toast, now: () => t });
  return { s, store, api, toast, advanceClock: (ms: number) => { t += ms; } };
}

async function loaded(devices?: Device[]) {
  const ctx = setup(devices);
  await ctx.store.loadAll();
  return ctx;
}

const dev = (s: HestiaState, id: string) => s.devices.find((d) => d.id === id)!;

beforeEach(() => vi.useRealTimers());
afterEach(() => vi.useRealTimers());

describe('loadAll', () => {
  it('loads everything and marks ready', async () => {
    const { s } = await loaded();
    expect(s.ready).toBe(true);
    expect(s.devices.map((d) => d.id)).toEqual(['lamp', 'plug']);
    expect(s.scenes).toEqual([movie]);
    expect(s.schedules).toEqual([bedtime]);
    expect(s.health).toEqual(health);
  });

  it('a first-load failure sets error (FatalScreen), no toast', async () => {
    const { s, store, api, toast } = setup();
    api.devices.mockRejectedValueOnce(new Error("Can't reach Hestia"));
    await store.loadAll();
    expect(s.ready).toBe(false);
    expect(s.error).toBe("Can't reach Hestia");
    expect(toast).not.toHaveBeenCalled();
  });

  it('a later failure keeps data and toasts', async () => {
    const { s, store, api, toast } = await loaded();
    api.scenes.mockRejectedValueOnce(new Error('boom'));
    await store.loadAll();
    expect(s.scenes).toEqual([movie]);
    expect(toast).toHaveBeenCalledWith('boom', 'error');
  });

  it('discards a stale response', async () => {
    const { s, store, api } = setup();
    const slow = deferred<Device[]>();
    api.devices.mockImplementationOnce(() => slow.promise);
    const first = store.loadAll();
    await store.loadAll(); // newer load: lamp + plug
    slow.resolve([lamp({ name: 'STALE' })]);
    await first;
    expect(s.devices.map((d) => d.name)).toEqual(['Lamp', 'Plug']);
  });

  it('a device with a write in flight keeps its local state', async () => {
    const { s, store, api } = await loaded([lamp({ state: off() })]);
    const write = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => write.promise);
    const toggling = store.toggle('lamp');
    expect(dev(s, 'lamp').state.power).toBe(true); // optimistic
    await store.loadAll(); // server still says off (pre-write)
    expect(dev(s, 'lamp').state.power).toBe(true);
    write.resolve(on());
    await toggling;
    expect(dev(s, 'lamp').state.power).toBe(true);
  });
});

describe('device actions', () => {
  it('toggle is optimistic, then takes the server state', async () => {
    const { s, store, api } = await loaded([plug({ state: off() })]);
    api.deviceAction.mockResolvedValueOnce(on({ from: 'server' }));
    const p = store.toggle('plug');
    expect(dev(s, 'plug').state.power).toBe(true);
    await p;
    expect(dev(s, 'plug').state).toEqual(on({ from: 'server' }));
    expect(api.deviceAction).toHaveBeenCalledWith('plug', 'toggle', undefined);
  });

  it('a failed toggle rolls back and toasts with the device name', async () => {
    const { s, store, api, toast } = await loaded([plug({ state: off() })]);
    api.deviceAction.mockRejectedValueOnce(new Error('timeout'));
    await store.toggle('plug');
    expect(dev(s, 'plug').state.power).toBe(false);
    expect(toast).toHaveBeenCalledWith('Plug: timeout', 'error');
  });

  it('play / pause', async () => {
    const { store, api } = await loaded();
    await store.play('lamp');
    await store.pause('lamp');
    expect(api.deviceAction.mock.calls.map((c) => c[1])).toEqual(['play', 'pause']);
  });
});

describe('setBrightness', () => {
  it('debounces drags and always sends the final value', async () => {
    vi.useFakeTimers();
    const { s, store, api } = await loaded();
    store.setBrightness('lamp', 10, { final: false });
    store.setBrightness('lamp', 20, { final: false });
    store.setBrightness('lamp', 30, { final: false });
    expect(dev(s, 'lamp').state.attributes.brightness).toBe(30);
    expect(api.deviceAction).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(150);
    expect(api.deviceAction).toHaveBeenCalledTimes(1);
    expect(api.deviceAction).toHaveBeenLastCalledWith('lamp', 'set_brightness', { level: 30 });
    store.setBrightness('lamp', 55, { final: true });
    expect(api.deviceAction).toHaveBeenCalledTimes(2);
    expect(api.deviceAction).toHaveBeenLastCalledWith('lamp', 'set_brightness', { level: 55 });
  });

  it('drops a stale response', async () => {
    vi.useFakeTimers();
    const { s, store, api } = await loaded();
    const first = deferred<DeviceState>();
    const last = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => first.promise).mockImplementationOnce(() => last.promise);
    store.setBrightness('lamp', 30, { final: false });
    await vi.advanceTimersByTimeAsync(150);
    store.setBrightness('lamp', 60, { final: true });
    last.resolve(on({ brightness: 60 }));
    await vi.advanceTimersByTimeAsync(0);
    first.resolve(on({ brightness: 30 }));
    await vi.advanceTimersByTimeAsync(0);
    expect(dev(s, 'lamp').state.attributes.brightness).toBe(60);
  });

  it('a failure restores the pre-drag state', async () => {
    const { s, store, api, toast } = await loaded();
    api.deviceAction.mockRejectedValueOnce(new Error('nope'));
    store.setBrightness('lamp', 90, { final: true });
    await vi.waitFor(() => expect(toast).toHaveBeenCalledWith('Lamp: nope', 'error'));
    expect(dev(s, 'lamp').state.attributes.brightness).toBe(40);
  });

  it('a drag that never sends final still releases the device', async () => {
    vi.useFakeTimers();
    const { s, store } = await loaded();
    store.setBrightness('lamp', 30, { final: false });
    await vi.advanceTimersByTimeAsync(150);
    expect(store.isPending('lamp')).toBe(false);
    store.handleEvent({ type: 'device_state_changed', data: { state: off() }, device_id: 'lamp' });
    expect(dev(s, 'lamp').state.power).toBe(false);
  });

  it('a reply that lands mid-drag does not move the slider back', async () => {
    vi.useFakeTimers();
    const { s, store, api } = await loaded();
    const d = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => d.promise);
    store.setBrightness('lamp', 30, { final: false });
    await vi.advanceTimersByTimeAsync(150);
    store.setBrightness('lamp', 60, { final: false });
    d.resolve(on({ brightness: 30, extra: 'x' }));
    await vi.advanceTimersByTimeAsync(0);
    expect(dev(s, 'lamp').state.attributes.brightness).toBe(60);
    expect(dev(s, 'lamp').state.attributes.extra).toBe('x');
    await vi.advanceTimersByTimeAsync(150);
    expect(dev(s, 'lamp').state).toEqual(on());
  });

  it('a send that lands while the drag continues keeps the device pending', async () => {
    vi.useFakeTimers();
    const { store, api } = await loaded();
    const d = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => d.promise);
    store.setBrightness('lamp', 30, { final: false });
    await vi.advanceTimersByTimeAsync(150);
    store.setBrightness('lamp', 40, { final: false });
    d.resolve(on({ brightness: 30 }));
    await vi.advanceTimersByTimeAsync(0);
    expect(store.isPending('lamp')).toBe(true);
    await vi.advanceTimersByTimeAsync(150);
    expect(store.isPending('lamp')).toBe(false);
  });
});

describe('scenes and schedules', () => {
  it('runScene reports success and toasts failures', async () => {
    const { store, api, toast } = await loaded();
    expect(await store.runScene('movie')).toBe(true);
    api.executeScene.mockRejectedValueOnce(new Error('bad'));
    expect(await store.runScene('movie')).toBe(false);
    expect(toast).toHaveBeenCalledWith('Movie: bad', 'error');
  });

  it('setScheduleEnabled is optimistic and rolls back', async () => {
    const { s, store, api, toast } = await loaded();
    await store.setScheduleEnabled('bedtime', false);
    expect(s.schedules[0].enabled).toBe(false);
    api.setScheduleEnabled.mockRejectedValueOnce(new Error('db'));
    await store.setScheduleEnabled('bedtime', true);
    expect(s.schedules[0].enabled).toBe(false);
    expect(toast).toHaveBeenCalledWith('Bedtime: db', 'error');
  });
});

describe('allOff', () => {
  it('turns off lights that are on and offers Undo that restores brightness', async () => {
    const { s, store, api, toast } = await loaded();
    api.deviceAction.mockImplementation(async (_id, action) => (action === 'turn_off' ? off() : on()));
    await store.allOff();
    expect(api.deviceAction.mock.calls.map((c) => [c[0], c[1]])).toEqual([['lamp', 'turn_off'], ['plug', 'turn_off']]);
    expect(dev(s, 'lamp').state.power).toBe(false);
    const [text, kind, action] = toast.mock.calls.at(-1)!;
    expect([text, kind, action.label]).toEqual(['All off', 'info', 'Undo']);
    api.deviceAction.mockClear();
    action.run();
    await vi.waitFor(() => expect(api.deviceAction).toHaveBeenCalledWith('lamp', 'set_brightness', { level: 40 }));
    expect(api.deviceAction).toHaveBeenCalledWith('lamp', 'turn_on', undefined);
    expect(api.deviceAction).toHaveBeenCalledWith('plug', 'turn_on', undefined);
  });

  it('reports partial failure once, without per-device toasts', async () => {
    const { store, api, toast } = await loaded();
    api.deviceAction.mockImplementation(async (id) => { if (id === 'plug') throw new Error('x'); return off(); });
    await store.allOff();
    expect(toast).toHaveBeenCalledTimes(1);
    expect(toast).toHaveBeenCalledWith("1 of 2 lights didn't respond", 'error');
  });

  it('leaves skipped (hidden) lights alone', async () => {
    const { s, store, api } = await loaded();
    api.deviceAction.mockImplementation(async () => off());
    await store.allOff(['plug']);
    expect(api.deviceAction.mock.calls.map((c) => [c[0], c[1]])).toEqual([['lamp', 'turn_off']]);
    expect(dev(s, 'plug').state.power).toBe(true);
  });

  it('does nothing when no lights are on', async () => {
    const { store, api, toast } = await loaded([plug({ state: off() })]);
    await store.allOff();
    expect(api.deviceAction).not.toHaveBeenCalled();
    expect(toast).not.toHaveBeenCalled();
  });
});

describe('live events', () => {
  const evt = (type: string, data: Record<string, unknown>, device_id?: string) => ({ type, data, device_id });

  it('device_state_changed applies, unless a write is in flight', async () => {
    const { s, store, api } = await loaded();
    store.handleEvent(evt('device_state_changed', { state: off() }, 'plug'));
    expect(dev(s, 'plug').state.power).toBe(false);
    const write = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => write.promise);
    const p = store.toggle('lamp'); // lamp → off optimistically
    store.handleEvent(evt('device_state_changed', { state: on({ brightness: 40 }) }, 'lamp'));
    expect(dev(s, 'lamp').state.power).toBe(false);
    write.resolve(off());
    await p;
  });

  it('ignores malformed state', async () => {
    const { s, store } = await loaded();
    store.handleEvent(evt('device_state_changed', { state: 'garbage' }, 'plug'));
    expect(dev(s, 'plug').state.power).toBe(true);
  });

  it('device_registered upserts', async () => {
    const { s, store } = await loaded();
    store.handleEvent(evt('device_registered', { info: plug({ name: 'Renamed' }) }));
    store.handleEvent(evt('device_registered', { info: plug({ id: 'new', name: 'New' }) }));
    expect(s.devices.map((d) => d.name)).toEqual(['Lamp', 'Renamed', 'New']);
  });

  it('scene_executed: a remote run ripples and toasts; a local run does neither', async () => {
    const { s, store, toast, advanceClock } = await loaded();
    await store.runScene('movie');
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(s.ripple).toBeNull();
    expect(toast).not.toHaveBeenCalled();
    advanceClock(2_001);
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(s.ripple).toEqual({ id: 'movie', n: 1 });
    expect(toast).toHaveBeenCalledWith('Movie ran');
  });

  it('schedule_triggered toasts once; its scene still ripples', async () => {
    const { s, store, toast } = await loaded();
    store.handleEvent(evt('schedule_triggered', { schedule_id: 'bedtime', scene_id: 'movie' }));
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(toast.mock.calls).toEqual([['Bedtime ran']]);
    expect(s.ripple?.id).toBe('movie');
  });

  it('device_registered keeps local state while a write is in flight', async () => {
    const { s, store, api } = await loaded();
    const write = deferred<DeviceState>();
    api.deviceAction.mockImplementationOnce(() => write.promise);
    const p = store.toggle('lamp'); // lamp -> off optimistically
    store.handleEvent(evt('device_registered', { info: lamp({ name: 'Renamed', state: on() }) }));
    expect(dev(s, 'lamp').name).toBe('Renamed');
    expect(dev(s, 'lamp').state.power).toBe(false);
    write.resolve(off());
    await p;
  });

  it('a local run longer than the window is still ours until it completes', async () => {
    const { s, store, api, toast, advanceClock } = await loaded();
    const d = deferred<never[]>();
    api.executeScene.mockImplementationOnce(() => d.promise);
    const p = store.runScene('movie');
    advanceClock(5_000);
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(s.ripple).toBeNull();
    expect(toast).not.toHaveBeenCalled();
    d.resolve([]);
    await p;
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(s.ripple).toBeNull();
    expect(toast).not.toHaveBeenCalled();
    advanceClock(2_001);
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(s.ripple).toEqual({ id: 'movie', n: 1 });
    expect(toast).toHaveBeenCalledWith('Movie ran');
  });

  it('a schedule announcement outlasts a long scene and is consumed once', async () => {
    const { s, store, toast, advanceClock } = await loaded();
    store.handleEvent(evt('schedule_triggered', { schedule_id: 'bedtime', scene_id: 'movie' }));
    advanceClock(5_000);
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(toast.mock.calls).toEqual([['Bedtime ran']]);
    expect(s.ripple?.id).toBe('movie');
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(toast.mock.calls.at(-1)).toEqual(['Movie ran']);
  });

  it('an announcement with no scene run expires', async () => {
    const { store, toast, advanceClock } = await loaded();
    store.handleEvent(evt('schedule_triggered', { schedule_id: 'bedtime', scene_id: 'movie' }));
    advanceClock(ANNOUNCE_TTL_MS + 1);
    store.handleEvent(evt('scene_executed', { scene_id: 'movie' }));
    expect(toast).toHaveBeenCalledWith('Movie ran');
  });

  it('device_error toasts with the device name', async () => {
    const { store, toast } = await loaded();
    store.handleEvent(evt('device_error', { action: 'toggle', error: 'unreachable' }, 'plug'));
    expect(toast).toHaveBeenCalledWith('Plug: unreachable', 'error');
  });
});
