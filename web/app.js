/* Hestia touchscreen UI — single Alpine.js state object.
 *
 * Architecture:
 *   - REST: fetch() against /devices/, /scenes/, /schedules/, /health
 *   - Realtime: WebSocket /ws receives Event JSON; applyEvent() patches state
 *   - Optimism: user actions flip UI immediately; revert on HTTP failure
 *
 * No build step. No external deps beyond Alpine.js (loaded via CDN in index.html).
 */

function app() {
  return {
    // ---------------------------------------------------------------- state
    tab: 'dashboard',
    devices: [],
    scenes: [],
    schedules: [],
    wsConnected: false,
    boot_failures: [],
    clockText: '',

    // ---------------------------------------------------------------- internals
    _ws: null,
    _backoff: 1000,
    _maxBackoff: 30000,
    _clockTimer: null,

    // ---------------------------------------------------------------- lifecycle
    async init() {
      this._tickClock();
      this._clockTimer = setInterval(() => this._tickClock(), 30_000);
      await this.refreshAll();
      this.connectWebSocket();
    },

    async refreshAll() {
      // Parallel fetch of all four endpoints. Each setter is independent so
      // a single failing endpoint doesn't blank the rest of the page.
      const [devices, scenes, schedules, health] = await Promise.allSettled([
        this._json('/devices/'),
        this._json('/scenes/'),
        this._json('/schedules/'),
        this._json('/health'),
      ]);

      if (devices.status === 'fulfilled') this.devices = devices.value || [];
      else console.error('refreshAll: /devices/', devices.reason);

      if (scenes.status === 'fulfilled') this.scenes = scenes.value || [];
      else console.error('refreshAll: /scenes/', scenes.reason);

      if (schedules.status === 'fulfilled') this.schedules = schedules.value || [];
      else console.error('refreshAll: /schedules/', schedules.reason);

      if (health.status === 'fulfilled') {
        this.boot_failures = health.value?.devices_failed || [];
      } else {
        console.error('refreshAll: /health', health.reason);
      }
    },

    // ---------------------------------------------------------------- helpers
    async _json(path, opts = {}) {
      const res = await fetch(path, opts);
      if (!res.ok) throw new Error(`${path} ${res.status}`);
      // 204 No Content has no body
      if (res.status === 204) return null;
      return res.json();
    },

    _findDevice(id) {
      return this.devices.find(d => d.id === id);
    },

    hasCap(dev, cap) {
      return Array.isArray(dev?.capabilities) && dev.capabilities.includes(cap);
    },

    isOn(dev) {
      return Boolean(dev?.state?.power);
    },

    deviceSubtitle(dev) {
      // Pretty-print the driver_name + device_type so users know what they're touching.
      const dt = dev.device_type || '';
      const drv = dev.driver_name || '';
      // Drop the "Driver" suffix if present (e.g. KasaDriver -> Kasa)
      const drvShort = drv.replace(/Driver$/, '');
      if (dt && drvShort) return `${drvShort} · ${dt}`;
      return drvShort || dt || '';
    },

    mediaText(dev) {
      const a = dev?.state?.attributes || {};
      if (a.track && a.artist) return `${a.track} — ${a.artist}`;
      return a.track || a.artist || '';
    },

    actionsSummary(scene) {
      const n = (scene.actions || []).length;
      return n === 1 ? '1 action' : `${n} actions`;
    },

    formatTime(t) {
      // "23:00" -> "11:00 PM"
      if (!t || typeof t !== 'string') return t || '';
      const [hStr, mStr] = t.split(':');
      const h = parseInt(hStr, 10);
      const m = parseInt(mStr, 10);
      if (Number.isNaN(h) || Number.isNaN(m)) return t;
      const period = h >= 12 ? 'PM' : 'AM';
      const h12 = ((h + 11) % 12) + 1;
      return `${h12}:${String(m).padStart(2, '0')} ${period}`;
    },

    formatDays(days) {
      if (!days || days.length === 0) return 'Every day';
      const order = ['mon','tue','wed','thu','fri','sat','sun'];
      const sorted = [...days].sort((a, b) => order.indexOf(a) - order.indexOf(b));
      const weekdays = ['mon','tue','wed','thu','fri'];
      const weekend = ['sat','sun'];
      const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
      if (eq(sorted, weekdays)) return 'Weekdays';
      if (eq(sorted, weekend)) return 'Weekends';
      return sorted.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(' · ');
    },

    iconForDevice(dev) {
      const drv = (dev.driver_name || '').toLowerCase();
      const type = (dev.device_type || '').toLowerCase();
      if (type === 'media' || drv.includes('spotify')) return '#icon-play';
      if (drv.includes('kasa')) return '#icon-plug';
      if (drv.includes('relay')) return '#icon-power';
      if (this.hasCap(dev, 'dimmer')) return '#icon-bulb';
      return '#icon-power';
    },

    iconForScene(scene) {
      const id = (scene.id || '').toLowerCase();
      const name = (scene.name || '').toLowerCase();
      const haystack = `${id} ${name}`;
      if (/(bed|night|sleep)/.test(haystack)) return '#icon-bed';
      if (/(morn|wake|sunrise)/.test(haystack)) return '#icon-sunrise';
      if (/(movie|film|cinema)/.test(haystack)) return '#icon-film';
      if (/(away|leave|out)/.test(haystack)) return '#icon-log-out';
      return '#icon-power';
    },

    _tickClock() {
      const d = new Date();
      const h = d.getHours();
      const m = d.getMinutes();
      const period = h >= 12 ? 'PM' : 'AM';
      const h12 = ((h + 11) % 12) + 1;
      this.clockText = `${h12}:${String(m).padStart(2, '0')} ${period}`;
    },

    // ---------------------------------------------------------------- user actions

    async toggleDevice(dev) {
      // Optimistic flip. Revert on failure.
      const prev = !!dev.state.power;
      dev.state = { ...dev.state, power: !prev };
      try {
        const newState = await this._json(`/devices/${encodeURIComponent(dev.id)}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'toggle' }),
        });
        // Re-sync from the authoritative response (server state may differ).
        if (newState) dev.state = newState;
      } catch (err) {
        console.error('toggleDevice failed', dev.id, err);
        dev.state = { ...dev.state, power: prev };
      }
    },

    async toggleMedia(dev) {
      const playing = !!dev.state.power;
      const action = playing ? 'pause' : 'play';
      // Optimistic flip
      dev.state = { ...dev.state, power: !playing };
      try {
        const newState = await this._json(`/devices/${encodeURIComponent(dev.id)}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action }),
        });
        if (newState) dev.state = newState;
      } catch (err) {
        console.error('toggleMedia failed', dev.id, err);
        dev.state = { ...dev.state, power: playing };
      }
    },

    async setBrightness(dev, level) {
      const prevAttrs = dev.state.attributes || {};
      const prevLevel = prevAttrs.brightness;
      // Optimistic
      dev.state = {
        ...dev.state,
        attributes: { ...prevAttrs, brightness: level },
      };
      try {
        const newState = await this._json(`/devices/${encodeURIComponent(dev.id)}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'set_brightness', params: { level } }),
        });
        if (newState) dev.state = newState;
      } catch (err) {
        console.error('setBrightness failed', dev.id, err);
        dev.state = {
          ...dev.state,
          attributes: { ...prevAttrs, brightness: prevLevel },
        };
      }
    },

    async executeScene(scene) {
      // Server-side sources `device_state_changed` for each step, so we don't
      // need to merge the result list here — the WS will deliver state diffs.
      try {
        await this._json(`/scenes/${encodeURIComponent(scene.id)}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
      } catch (err) {
        console.error('executeScene failed', scene.id, err);
      }
      this._flashScene(scene.id);
    },

    _flashScene(sceneId) {
      const scene = this.scenes.find(s => s.id === sceneId);
      if (!scene) return;
      scene._flash = true;
      setTimeout(() => { scene._flash = false; }, 600);
    },

    async toggleSchedule(sch) {
      const prev = !!sch.enabled;
      sch.enabled = !prev;
      try {
        const updated = await this._json(`/schedules/${encodeURIComponent(sch.id)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: sch.enabled }),
        });
        // Replace with authoritative version (preserves server-side coercions).
        if (updated) Object.assign(sch, updated);
      } catch (err) {
        console.error('toggleSchedule failed', sch.id, err);
        sch.enabled = prev;
      }
    },

    // ---------------------------------------------------------------- WebSocket

    connectWebSocket() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const url = `${proto}://${location.host}/ws`;
      let ws;
      try {
        ws = new WebSocket(url);
      } catch (err) {
        console.error('WebSocket construct failed', err);
        this._scheduleReconnect();
        return;
      }
      this._ws = ws;
      ws.onopen = () => {
        this.wsConnected = true;
        this._backoff = 1000;
      };
      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data);
          this.applyEvent(event);
        } catch (err) {
          console.error('WS message parse error', err, msg.data);
        }
      };
      ws.onclose = () => {
        this.wsConnected = false;
        this._scheduleReconnect();
      };
      ws.onerror = () => {
        // Force close to trigger reconnect path.
        try { ws.close(); } catch (_) { /* noop */ }
      };
    },

    _scheduleReconnect() {
      const delay = Math.min(this._backoff, this._maxBackoff);
      setTimeout(() => this.connectWebSocket(), delay);
      this._backoff = Math.min(this._backoff * 2, this._maxBackoff);
    },

    applyEvent(event) {
      // Event shape is from schemas/events.py:
      //   { type, device_id, data, timestamp, source }
      if (!event || !event.type) return;
      switch (event.type) {
        case 'device_state_changed': {
          const dev = this._findDevice(event.device_id);
          if (!dev) return;
          const newState = event.data?.state;
          if (newState) dev.state = newState;
          break;
        }
        case 'scene_executed': {
          const sceneId = event.data?.scene_id;
          if (sceneId) this._flashScene(sceneId);
          break;
        }
        case 'device_registered': {
          // A new driver came online (or restarted). Pull fresh device list.
          // Cheap operation — handful of rows — and avoids invented keys.
          const info = event.data?.info;
          if (info) {
            const idx = this.devices.findIndex(d => d.id === info.id);
            if (idx >= 0) this.devices.splice(idx, 1, info);
            else this.devices.push(info);
          }
          break;
        }
        case 'device_error': {
          // Surface in console for now — Phase 4a doesn't render an error toast.
          console.warn('device_error', event.device_id, event.data);
          break;
        }
        case 'schedule_triggered':
          // No-op visually; the schedule's scene will fire its own events.
          break;
        default:
          // Unknown event — log once and move on.
          console.debug('unknown event type', event.type);
      }
    },
  };
}

// Expose globally so Alpine's x-data="app()" can find it.
window.app = app;
