import { useEffect } from "react";

// Maps physical keyboard events to the kiosk's 12-key ATM keypad vocabulary so
// the entire UX can be driven from a normal USB keyboard number row (and later
// from a real keypad / USB encoder that emits the same keys).
//
// Canonical keys: "1".."9", "0", "*", "#".
// Convenience aliases so a laptop tester isn't hunting for * and #:
//   Enter / NumpadEnter / "+"  -> "#"      (submit / select)
//   Escape                     -> "0"      (back / home)
//   Backspace                  -> "BS"     (delete digit on dial pad, else back)
//   "/"                        -> "*"      (repeat / help)
//   "c" / "C"                  -> "CALL"   (green call button / future GPIO)
//   "h" / "H"                  -> "HANGUP" (red hang-up button / future GPIO)
//
// While a text field is focused (the ASK_HOME input) we ignore digit keys so
// typing works; only Escape is intercepted so the user can always back out.

const DIGITS = new Set(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]);

function normalize(e) {
  const k = e.key;
  if (DIGITS.has(k)) return k;
  if (k === "*") return "*";
  if (k === "#") return "#";
  if (k === "Enter") return "#";
  if (k === "+") return "#";
  if (k === "Escape") return "0";
  if (k === "Backspace") return "BS";
  if (k === "/") return "*";
  if (k === "c" || k === "C") return "CALL";
  if (k === "h" || k === "H") return "HANGUP";
  return null;
}

export function useKeypadInput(onKey, { enabled = true } = {}) {
  useEffect(() => {
    if (!enabled) return undefined;

    function handler(e) {
      const target = e.target;
      const typing =
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);

      // When typing, let the field handle everything except Escape (always back).
      if (typing && e.key !== "Escape") return;

      const mapped = normalize(e);
      if (!mapped) return;
      e.preventDefault();
      onKey(mapped);
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onKey, enabled]);
}
