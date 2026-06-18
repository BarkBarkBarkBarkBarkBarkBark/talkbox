import { useEffect, useMemo, useRef, useState } from "react";

const LOCK_KEY = "talkbox:kiosk-active-window";
const HEARTBEAT_MS = 1500;
const STALE_AFTER_MS = 6000;

function makeWindowId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function readLock() {
  try {
    const raw = localStorage.getItem(LOCK_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeLock(lock) {
  try {
    localStorage.setItem(LOCK_KEY, JSON.stringify(lock));
  } catch {
    // If storage is unavailable, let this window run rather than dead-ending.
  }
}

export function useSingleKioskWindow({ enabled = true } = {}) {
  const id = useMemo(makeWindowId, []);
  const [isPrimary, setIsPrimary] = useState(!enabled);
  const isPrimaryRef = useRef(!enabled);

  useEffect(() => {
    isPrimaryRef.current = isPrimary;
  }, [isPrimary]);

  useEffect(() => {
    if (!enabled) return undefined;

    function claimIfAvailable() {
      const now = Date.now();
      const existing = readLock();
      const stale = !existing?.updatedAt || now - Number(existing.updatedAt) > STALE_AFTER_MS;
      const mine = existing?.id === id;

      if (!existing || stale || mine) {
        writeLock({ id, updatedAt: now });
        setIsPrimary(true);
      } else {
        setIsPrimary(false);
      }
    }

    function heartbeat() {
      if (!isPrimaryRef.current) return;
      const existing = readLock();
      if (existing?.id && existing.id !== id) {
        setIsPrimary(false);
        return;
      }
      writeLock({ id, updatedAt: Date.now() });
    }

    function onStorage(event) {
      if (event.key === LOCK_KEY) claimIfAvailable();
    }

    function onFocusOrVisible() {
      if (document.visibilityState !== "hidden") claimIfAvailable();
    }

    claimIfAvailable();
    const interval = setInterval(() => {
      claimIfAvailable();
      heartbeat();
    }, HEARTBEAT_MS);

    window.addEventListener("storage", onStorage);
    window.addEventListener("focus", onFocusOrVisible);
    document.addEventListener("visibilitychange", onFocusOrVisible);

    return () => {
      clearInterval(interval);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("focus", onFocusOrVisible);
      document.removeEventListener("visibilitychange", onFocusOrVisible);
      const existing = readLock();
      if (existing?.id === id) {
        try {
          localStorage.removeItem(LOCK_KEY);
        } catch {
          // ignore
        }
      }
    };
  }, [enabled, id]);

  return { isPrimary };
}