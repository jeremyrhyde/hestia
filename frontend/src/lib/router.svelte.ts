// History-aware hash router (from Apollo). Each navigation pushes a history
// entry carrying its index, so popstate can tell back from forward (for the
// slide direction). Screen changes run inside document.startViewTransition
// where supported and just swap otherwise.

import { tick } from 'svelte';
import { motionReduced } from './motion';
import { buildHash, parseHash, type Route } from './route';

export const router: { route: Route } = $state({ route: parseHash(location.hash) });

let index = 0;

type ViewTransitionDoc = Document & { startViewTransition?: (cb: () => Promise<void>) => unknown };

function apply(route: Route, direction: 'forward' | 'back', animate: boolean): void {
  const doc = document as ViewTransitionDoc;
  if (!animate || motionReduced() || !doc.startViewTransition) {
    router.route = route;
    return;
  }
  document.documentElement.dataset.nav = direction;
  doc.startViewTransition(async () => {
    router.route = route;
    await tick();
  });
}

// Safari's edge-swipe back/forward sets this on the PopStateEvent, since it
// already animated the transition itself.
type SwipePopStateEvent = PopStateEvent & { hasUAVisualTransition?: boolean };

export function initRouter(): () => void {
  // A reload keeps history.state; an existing idx means we're re-entering an
  // existing entry, so leave it alone and back/forward still work.
  const existingIdx = typeof history.state?.idx === 'number' ? (history.state.idx as number) : null;
  index = existingIdx ?? 0;
  if (!location.hash) {
    history.replaceState({ idx: index }, '', buildHash(['home']));
  } else if (existingIdx === null) {
    history.replaceState({ idx: index }, '');
  }
  router.route = parseHash(location.hash);
  const onPopState = (event: SwipePopStateEvent) => {
    const idx = typeof event.state?.idx === 'number' ? (event.state.idx as number) : 0;
    const direction = idx < index ? 'back' : 'forward';
    index = idx;
    const swiped = 'hasUAVisualTransition' in event && event.hasUAVisualTransition === true;
    apply(parseHash(location.hash), direction, !swiped);
  };
  addEventListener('popstate', onPopState);
  return () => removeEventListener('popstate', onPopState);
}

export function navigate(
  path: string[],
  query: Record<string, string | undefined> = {},
  opts: { replace?: boolean; direction?: 'forward' | 'back' } = {},
): void {
  const hash = buildHash(path, query);
  if (opts.replace) {
    history.replaceState({ idx: index }, '', hash);
  } else {
    index += 1;
    history.pushState({ idx: index }, '', hash);
  }
  apply(parseHash(hash), opts.direction ?? 'forward', !opts.replace);
}
