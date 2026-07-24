import { useEffect, useRef, useState } from "react";
import { kioskApi } from "../lib/kioskApi.js";

// Detects a dead backend (Docker stopped, network down) so the kiosk can show
// an honest "Reconnecting…" screen instead of appearing frozen. Suspended
// during live calls — call audio flows through Twilio, not our backend, and
// an overlay must never interrupt a crisis call.
const PING_INTERVAL_MS = 15_000;
const FAILURES_BEFORE_OFFLINE = 2;

export function useBackendHealth({ suspended = false } = {}) {
  const [offline, setOffline] = useState(false);
  const suspendedRef = useRef(suspended);
  suspendedRef.current = suspended;
  const offlineRef = useRef(false);
  const failuresRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      if (suspendedRef.current) return;
      try {
        await kioskApi.health();
        if (cancelled) return;
        failuresRef.current = 0;
        if (offlineRef.current) {
          offlineRef.current = false;
          setOffline(false);
          kioskApi.logEvent({ event_type: "backend_online" });
        }
      } catch {
        if (cancelled) return;
        failuresRef.current += 1;
        if (failuresRef.current >= FAILURES_BEFORE_OFFLINE && !offlineRef.current) {
          offlineRef.current = true;
          setOffline(true);
          kioskApi.logEvent({ event_type: "backend_offline" });
        }
      }
    };

    const id = setInterval(tick, PING_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return offline;
}
