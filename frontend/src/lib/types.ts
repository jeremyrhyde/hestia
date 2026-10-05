// Mirrors the backend's Pydantic models (schemas/*.py) and /health (main.py).

export type Capability = 'toggle' | 'dimmer' | 'media_control' | 'custom';
export type DeviceType = 'switch' | 'relay' | 'media' | 'custom';

export interface DeviceState {
  power: boolean;
  /** Free-form: `brightness` (0-100) on dimmers; `track`, `artist`, `volume` on media. */
  attributes: Record<string, unknown>;
}

export interface Device {
  id: string;
  name: string;
  device_type: DeviceType;
  driver_name: string;
  capabilities: Capability[];
  state: DeviceState;
}

export interface SceneAction {
  device_id: string;
  action: string;
  params?: Record<string, unknown> | null;
  delay_ms?: number | null;
}

export interface Scene {
  id: string;
  name: string;
  description?: string | null;
  actions: SceneAction[];
}

export interface Schedule {
  id: string;
  name: string;
  scene_id: string;
  /** "HH:MM", 24h. */
  time: string;
  /** Three-letter codes ("mon"…"sun"); null means every day. */
  days: string[] | null;
  enabled: boolean;
}

export interface BootFailure {
  id: string;
  driver: string;
  error: string;
}

export interface Health {
  status: string;
  devices_registered: number;
  devices_failed: BootFailure[];
}

export interface WsEvent {
  type: string;
  device_id?: string | null;
  data: Record<string, unknown>;
  timestamp?: string;
  source?: string;
}

export type DeviceActionName = 'toggle' | 'turn_on' | 'turn_off' | 'play' | 'pause' | 'set_brightness';
