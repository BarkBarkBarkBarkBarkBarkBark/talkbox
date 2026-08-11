/** True when the SPA is loaded on a local appliance / dev host (Pi Chromium). */
export function isLocalHost(hostname = typeof window !== "undefined" ? window.location.hostname : "") {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
}
