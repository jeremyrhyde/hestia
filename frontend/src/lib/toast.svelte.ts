export interface ToastAction {
  label: string;
  run: () => void;
}

export interface ToastItem {
  id: number;
  text: string;
  kind: 'info' | 'error';
  action?: ToastAction;
}

export const toasts: ToastItem[] = $state([]);
let nextId = 1;

export function dismissToast(id: number): void {
  const i = toasts.findIndex((t) => t.id === id);
  if (i >= 0) toasts.splice(i, 1);
}

/** Show a toast. One with an action (e.g. Undo) stays 4s. */
export function toast(text: string, kind: 'info' | 'error' = 'info', action?: ToastAction): void {
  const id = nextId++;
  toasts.push({ id, text, kind, action });
  setTimeout(() => dismissToast(id), action ? 4000 : kind === 'error' ? 5000 : 2500);
}

export function toastError(error: unknown): void {
  toast(error instanceof Error ? error.message : String(error), 'error');
}
