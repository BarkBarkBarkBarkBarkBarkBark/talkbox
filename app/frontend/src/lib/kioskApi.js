// Kiosk API client. Mirrors the fetch conventions in lib/api.js but targets the
// additive /api/kiosk/* endpoints. Public resource calls remain anonymous, but
// including credentials lets an enrolled physical kiosk use its HttpOnly cookie.

const BASE_URL = import.meta.env.VITE_API_URL || "";

async function request(path, opts = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...opts,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = new Error(data?.detail || data?.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export const kioskApi = {
  config: () => request("/api/kiosk/config"),
  deviceStatus: () => request("/api/kiosk/device/status"),
  enrollDevice: (device) => request("/api/kiosk/device/enroll", {
    method: "POST",
    body: JSON.stringify(device),
  }),

  // Lightweight liveness probe with a hard timeout so a dead backend is
  // detected instead of hanging fetches piling up.
  health: () => request("/api/health", { signal: AbortSignal.timeout(5000) }),

  query: (q) =>
    request("/api/kiosk/query", {
      method: "POST",
      body: JSON.stringify({ query: q }),
    }),

  // Flat A–Z organization directory for the Browse tab.
  directory: () => request("/api/kiosk/directory"),

  transcribeAudio: async (blob) => {
    const form = new FormData();
    form.append("audio", blob, "kiosk-voice.webm");
    const res = await fetch(`${BASE_URL}/api/kiosk/speech/transcribe`, {
      method: "POST",
      body: form,
      credentials: "include",
    });
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (!res.ok) {
      const err = new Error(data?.detail || data?.error || `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return data;
  },

  // Request a real outbound call. The backend refuses any number that is not
  // in the agencies database (allowlist) — no arbitrary dialing.
  startCall: ({ phone, name }) =>
    request("/api/kiosk/call/start", {
      method: "POST",
      body: JSON.stringify({ phone, name }),
    }),

  // Request a Twilio Voice access token for browser SDK calling.
  // Backend validates the allowlist before issuing the token.
  requestVoiceToken: ({ phone, name, demo = false }) =>
    request("/api/kiosk/call/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-TalkBox-Mode": demo ? "demo" : "kiosk",
      },
      body: JSON.stringify({ phone, name }),
    }),

  // Fire-and-forget telemetry. Never blocks or throws into the UI.
  logEvent: (event) => {
    try {
      fetch(`${BASE_URL}/api/kiosk/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
          credentials: "include",
        body: JSON.stringify(event),
        keepalive: true,
      }).catch(() => {});
    } catch {
      // ignore
    }
  },
};
