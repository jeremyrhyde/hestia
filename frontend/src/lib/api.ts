import type { Device, DeviceActionName, DeviceState, Health, Scene, Schedule } from './types';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** FastAPI error bodies: `{detail: "msg"}` or a validation list. From Apollo. */
export function detailOf(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('detail' in body)) return null;
  const detail = (body as { detail: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const item = d as { loc?: unknown; msg?: string };
        const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
        const msg = item.msg ?? String(d);
        return typeof field === 'string' ? `${field}: ${msg}` : msg;
      })
      .join('; ');
  }
  return null;
}

async function request<T>(method: string, path: string, body?: unknown, base = 'api'): Promise<T> {
  let res: Response;
  try {
    // Relative to the page (no leading slash), so it works at :8003/ and
    // under Pantheon's /hestia/.
    res = await fetch(`${base}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach Hestia");
  }
  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, detailOf(data) ?? (res.statusText || `HTTP ${res.status}`));
  return data as T;
}

const enc = encodeURIComponent;

export const api = {
  health: () => request<Health>('GET', '/health', undefined, '.'),
  devices: () => request<Device[]>('GET', '/devices/'),
  scenes: () => request<Scene[]>('GET', '/scenes/'),
  schedules: () => request<Schedule[]>('GET', '/schedules/'),
  deviceAction: (id: string, action: DeviceActionName, params?: Record<string, unknown>) =>
    request<DeviceState>('POST', `/devices/${enc(id)}/action`, params === undefined ? { action } : { action, params }),
  executeScene: (id: string) => request<unknown>('POST', `/scenes/${enc(id)}/execute`),
  setScheduleEnabled: (id: string, enabled: boolean) =>
    request<Schedule>('PATCH', `/schedules/${enc(id)}`, { enabled }),
};

export type Api = typeof api;
