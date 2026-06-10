// Kiosk API client. Mirrors the fetch conventions in lib/api.js but targets the
// additive /api/kiosk/* endpoints. No credentials needed (kiosk routes are open
// when DISABLE_AUTH=true, which is the kiosk default).

const BASE_URL = import.meta.env.VITE_API_URL || "";

async function request(path, opts = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
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

  query: (q) =>
    request("/api/kiosk/query", {
      method: "POST",
      body: JSON.stringify({ query: q }),
    }),

  // Request a real outbound call. The backend refuses any number that is not
  // in the agencies database (allowlist) — no arbitrary dialing.
  startCall: ({ phone, name }) =>
    request("/api/kiosk/call/start", {
      method: "POST",
      body: JSON.stringify({ phone, name }),
    }),

  // Fire-and-forget telemetry. Never blocks or throws into the UI.
  logEvent: (event) => {
    try {
      fetch(`${BASE_URL}/api/kiosk/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
        keepalive: true,
      }).catch(() => {});
    } catch {
      // ignore
    }
  },
};
