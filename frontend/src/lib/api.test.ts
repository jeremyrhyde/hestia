import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, detailOf } from './api';

function stubFetch(status: number, body: unknown) {
  const fn = vi.fn(async (_url: string, _init?: RequestInit) =>
    status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe('endpoint paths are relative (work under /hestia/)', () => {
  it.each([
    ['devices', () => api.devices(), 'api/devices/'],
    ['scenes', () => api.scenes(), 'api/scenes/'],
    ['schedules', () => api.schedules(), 'api/schedules/'],
    ['health', () => api.health(), './health'],
  ])('%s', async (_name, call, url) => {
    const fetch = stubFetch(200, []);
    await call();
    expect(fetch.mock.calls[0][0]).toBe(url);
    expect(String(fetch.mock.calls[0][0]).startsWith('/')).toBe(false);
  });

  it('device actions encode the id and send action + params', async () => {
    const fetch = stubFetch(200, { power: true, attributes: {} });
    await api.deviceAction('kasa one', 'set_brightness', { level: 40 });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe('api/devices/kasa%20one/action');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ action: 'set_brightness', params: { level: 40 } });
  });

  it('omits params when there are none', async () => {
    const fetch = stubFetch(200, { power: false, attributes: {} });
    await api.deviceAction('lamp', 'toggle');
    expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ action: 'toggle' });
  });

  it('scene execute and schedule patch', async () => {
    const fetch = stubFetch(200, {});
    await api.executeScene('movie');
    await api.setScheduleEnabled('bedtime', false);
    expect(fetch.mock.calls[0][0]).toBe('api/scenes/movie/execute');
    expect(fetch.mock.calls[1][0]).toBe('api/schedules/bedtime');
    expect(fetch.mock.calls[1][1]?.method).toBe('PATCH');
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body))).toEqual({ enabled: false });
  });
});

describe('errors', () => {
  it('a network failure becomes ApiError(0) with a readable message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const err = await api.devices().catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, message: "Can't reach Hestia" });
  });

  it('a non-2xx uses the server detail', async () => {
    stubFetch(404, { detail: 'device not found' });
    await expect(api.deviceAction('x', 'toggle')).rejects.toMatchObject({ status: 404, message: 'device not found' });
  });

  it('204 resolves to undefined', async () => {
    stubFetch(204, null);
    await expect(api.executeScene('a')).resolves.toBeUndefined();
  });
});

describe('detailOf', () => {
  it('string detail', () => expect(detailOf({ detail: 'nope' })).toBe('nope'));
  it('validation detail list', () =>
    expect(detailOf({ detail: [{ loc: ['body', 'level'], msg: 'too big' }] })).toBe('level: too big'));
  it('missing', () => {
    expect(detailOf(null)).toBeNull();
    expect(detailOf({})).toBeNull();
  });
});
