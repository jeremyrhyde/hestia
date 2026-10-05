/** Wall clock for the header and glance; minute resolution is plenty. */
export const clock = $state({ now: new Date() });

export function startClock(): () => void {
  const timer = setInterval(() => {
    clock.now = new Date();
  }, 10_000);
  return () => clearInterval(timer);
}
