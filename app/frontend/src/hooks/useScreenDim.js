import { useEffect, useRef, useState } from "react";

// Dims the kiosk screen after a period with no physical activity (default 30
// minutes) to limit panel burn-in on an always-on public display. Any key or
// touch wakes the screen instantly; the waking press is swallowed so it never
// dials or navigates. While a call is active the screen never dims.
//
// The moment the screen dims is also the safest time for SPA hygiene: if the
// app has been running for more than a day, reload once, invisibly, so a
// long-lived kiosk session can never accumulate leaks for weeks.
const RELOAD_AFTER_MS = 24 * 60 * 60 * 1000;
const startedAt = Date.now();

export function useScreenDim({ dimAfterSeconds = 1800, suspended = false } = {}) {
  const [dimmed, setDimmed] = useState(false);
  const dimmedRef = useRef(false);
  const suspendedRef = useRef(suspended);
  suspendedRef.current = suspended;
  const timerRef = useRef(null);

  useEffect(() => {
    dimmedRef.current = dimmed;
  }, [dimmed]);

  useEffect(() => {
    const arm = () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(fire, Math.max(60, dimAfterSeconds) * 1000);
    };

    const fire = () => {
      if (suspendedRef.current) {
        arm(); // live call — try again later
        return;
      }
      setDimmed(true);
      if (Date.now() - startedAt > RELOAD_AFTER_MS) {
        // Screen is dark and nobody is here: restart to a fresh SPA.
        setTimeout(() => window.location.reload(), 5000);
      }
    };

    const onActivity = (e) => {
      if (dimmedRef.current) {
        // The waking press only wakes — it must never reach the keypad.
        e.preventDefault();
        e.stopImmediatePropagation?.();
        e.stopPropagation();
        setDimmed(false);
      }
      arm();
    };

    // Capture phase so activity is seen even when other handlers consume it.
    window.addEventListener("keydown", onActivity, true);
    window.addEventListener("pointerdown", onActivity, true);
    arm();
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      window.removeEventListener("keydown", onActivity, true);
      window.removeEventListener("pointerdown", onActivity, true);
    };
  }, [dimAfterSeconds]);

  return dimmed;
}
