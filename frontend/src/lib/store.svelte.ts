import { api } from './api';
import { live } from './live.svelte';
import { createStore, initialState, LIVE_EVENT_TYPES, type HestiaState } from './store';
import { toast } from './toast.svelte';

export const hestia: HestiaState = $state(initialState());

export const store = createStore(hestia, { api, toast });

/** Feed live events into the store; refetch everything after a reconnect. */
export function registerLiveHandlers(): () => void {
  const offs = LIVE_EVENT_TYPES.map((type) => live.on(type, store.handleEvent));
  offs.push(live.onReconnect(() => void store.loadAll()));
  return () => offs.forEach((off) => off());
}
