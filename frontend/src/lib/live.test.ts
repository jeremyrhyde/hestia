import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { backoffDelay, LiveClient, wsUrl, type SocketLike, type Status } from './live';

class FakeSocket implements SocketLike {
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {}
  close() {
    if (this.closed) return;
    this.closed = true;
    this.onclose?.();
  }
  open() { this.onopen?.(); }
  send(data: unknown) { this.onmessage?.({ data }); }
}

function setup() {
  const sockets: FakeSocket[] = [];
  const statuses: Status[] = [];
  const client = new LiveClient({
    makeSocket: (url) => { const s = new FakeSocket(url); sockets.push(s); return s; },
    baseURI: () => 'http://h:8000/hestia/#/devices',
    random: () => 0.5, // no jitter
    onStatus: (s) => statuses.push(s),
  });
  return { client, sockets, statuses, last: () => sockets[sockets.length - 1] };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('wsUrl', () => {
  it('derives from the page base, keeping a gateway prefix', () => {
    expect(wsUrl('http://h:8000/hestia/')).toBe('ws://h:8000/hestia/api/ws');
    expect(wsUrl('http://h:8000/hestia/#/devices')).toBe('ws://h:8000/hestia/api/ws');
    expect(wsUrl('http://pi:8003/')).toBe('ws://pi:8003/api/ws');
    expect(wsUrl('https://home.example/hestia/')).toBe('wss://home.example/hestia/api/ws');
  });
});

describe('backoffDelay', () => {
  it('doubles from 1s to a 30s cap', () => {
    expect([0, 1, 2, 3, 4, 5, 9].map((a) => backoffDelay(a, () => 0.5))).toEqual([1000, 2000, 4000, 8000, 16000, 30000, 30000]);
  });
  it('jitters ±20%', () => {
    expect(backoffDelay(0, () => 0)).toBe(800);
    expect(backoffDelay(0, () => 1)).toBe(1200);
  });
});

describe('LiveClient', () => {
  it('connects, reports status, and reconnects with backoff', () => {
    const { client, sockets, statuses, last } = setup();
    client.connect();
    expect(sockets).toHaveLength(1);
    expect(sockets[0].url).toBe('ws://h:8000/hestia/api/ws');
    expect(statuses.at(-1)).toBe('connecting');
    last().open();
    expect(statuses.at(-1)).toBe('open');
    last().close();
    expect(statuses.at(-1)).toBe('reconnecting');
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(2);
    last().close(); // failed retry → 2s
    vi.advanceTimersByTime(1999);
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(3);
  });

  it('a failed first attempt shows as reconnecting', () => {
    const { client, statuses, last } = setup();
    client.connect();
    last().close();
    expect(statuses.at(-1)).toBe('reconnecting');
  });

  it('runs onReconnect on every open except the first', () => {
    const { client, last } = setup();
    const onReconnect = vi.fn();
    client.onReconnect(onReconnect);
    client.connect();
    last().open();
    expect(onReconnect).not.toHaveBeenCalled();
    last().close();
    vi.advanceTimersByTime(1000);
    last().open();
    expect(onReconnect).toHaveBeenCalledTimes(1);
  });

  it('dispatches by type; unknown types and bad JSON never throw', () => {
    const { client, last } = setup();
    const debug = vi.spyOn(console, 'debug').mockImplementation(() => {});
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    const onState = vi.fn();
    const off = client.on('device_state_changed', onState);
    client.on('device_state_changed', () => { throw new Error('handler bug'); });
    client.connect();
    last().open();
    const event = { type: 'device_state_changed', device_id: 'lamp', data: { state: { power: true, attributes: {} } } };
    expect(() => last().send(JSON.stringify(event))).not.toThrow();
    expect(onState).toHaveBeenCalledWith(event);
    expect(error).toHaveBeenCalled();
    last().send(JSON.stringify({ type: 'mystery', data: {} }));
    expect(debug).toHaveBeenCalled();
    last().send('{nope');
    last().send(JSON.stringify({ no: 'type' }));
    expect(warn).toHaveBeenCalledTimes(2);
    off();
    last().send(JSON.stringify(event));
    expect(onState).toHaveBeenCalledTimes(1);
  });

  it('disconnect stops reconnecting', () => {
    const { client, sockets, last } = setup();
    client.connect();
    last().open();
    client.disconnect();
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(1);
  });

  it('retryNow skips the backoff wait', () => {
    const { client, sockets, last } = setup();
    client.connect();
    last().open();
    last().close();
    client.retryNow();
    expect(sockets).toHaveLength(2);
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(2); // the pending timer was cancelled
  });

  it('retryNow does nothing while connected', () => {
    const { client, sockets, last } = setup();
    client.connect();
    last().open();
    client.retryNow();
    expect(sockets).toHaveLength(1);
  });
});
