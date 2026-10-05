// WebSocket client core: receive-only, reconnects with jittered exponential
// backoff, dispatches events by `type`. Knows nothing about the store —
// store.svelte.ts subscribes with on(type, fn) and onReconnect(fn).

import type { WsEvent } from './types';

export type Status = 'connecting' | 'open' | 'reconnecting';

export interface SocketLike {
  onopen: (() => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  close(): void;
}

export interface LiveDeps {
  makeSocket: (url: string) => SocketLike;
  baseURI: () => string;
  random?: () => number;
  onStatus?: (status: Status) => void;
}

/** api/ws relative to the page, so it works at :8003/ and under /hestia/. */
export function wsUrl(baseURI: string): string {
  const url = new URL('api/ws', baseURI);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.hash = '';
  return url.toString();
}

/** 1s doubling to 30s, ±20% jitter so many clients don't retry in lockstep. */
export function backoffDelay(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(1000 * 2 ** attempt, 30_000);
  return Math.round(base * (1 + 0.2 * (random() * 2 - 1)));
}

type Handler = (event: WsEvent) => void;

export class LiveClient {
  private handlers = new Map<string, Set<Handler>>();
  private reconnectHandlers = new Set<() => void>();
  private socket: SocketLike | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private attempt = 0;
  private everOpened = false;
  private isOpen = false;
  private stopped = true;

  constructor(private deps: LiveDeps) {}

  on(type: string, fn: Handler): () => void {
    let set = this.handlers.get(type);
    if (!set) this.handlers.set(type, (set = new Set()));
    set.add(fn);
    return () => set.delete(fn);
  }

  onReconnect(fn: () => void): () => void {
    this.reconnectHandlers.add(fn);
    return () => this.reconnectHandlers.delete(fn);
  }

  connect(): void {
    this.stopped = false;
    if (!this.socket && !this.timer) this.open();
  }

  disconnect(): void {
    this.stopped = true;
    this.clearTimer();
    const s = this.socket;
    this.socket = null;
    this.isOpen = false;
    s?.close();
  }

  /** Skip the backoff wait (e.g. the page became visible again). */
  retryNow(): void {
    if (this.stopped || this.isOpen || this.socket) return;
    this.clearTimer();
    this.open();
  }

  private setStatus(status: Status): void {
    this.deps.onStatus?.(status);
  }

  private clearTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private open(): void {
    this.setStatus(this.everOpened || this.attempt > 0 ? 'reconnecting' : 'connecting');
    let s: SocketLike;
    try {
      s = this.deps.makeSocket(wsUrl(this.deps.baseURI()));
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = s;
    s.onopen = () => {
      const isReconnect = this.everOpened;
      this.everOpened = true;
      this.isOpen = true;
      this.attempt = 0;
      this.setStatus('open');
      if (isReconnect) for (const fn of this.reconnectHandlers) fn();
    };
    s.onmessage = (ev) => this.dispatch(ev.data);
    s.onclose = () => {
      if (this.socket !== s) return;
      this.socket = null;
      this.isOpen = false;
      if (this.stopped) return;
      this.setStatus('reconnecting');
      this.scheduleReconnect();
    };
    s.onerror = () => {
      try {
        s.close();
      } catch {
        // already closed
      }
    };
  }

  private scheduleReconnect(): void {
    const delay = backoffDelay(this.attempt, this.deps.random);
    this.attempt = Math.min(this.attempt + 1, 10);
    this.timer = setTimeout(() => {
      this.timer = null;
      this.open();
    }, delay);
  }

  private dispatch(raw: unknown): void {
    let event: WsEvent;
    try {
      event = JSON.parse(String(raw)) as WsEvent;
    } catch {
      console.warn('live: unparsable message', raw);
      return;
    }
    if (!event || typeof event.type !== 'string') {
      console.warn('live: message without a type', event);
      return;
    }
    const handlers = this.handlers.get(event.type);
    if (!handlers?.size) {
      console.debug('live: unhandled event type', event.type);
      return;
    }
    for (const fn of handlers) {
      try {
        fn(event);
      } catch (err) {
        console.error('live: handler failed for', event.type, err);
      }
    }
  }
}
