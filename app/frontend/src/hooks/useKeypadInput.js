import { useEffect } from "react";

// Maps physical keyboard / USB numpad events to the kiosk's key vocabulary so
// the entire UX can be driven from a standard numeric keypad. Every physical
// key has ONE stable meaning regardless of screen — this is deliberate so a
// printed sticker over a key is always accurate.
//
// Numpad layout → meaning:
//   1..9, 0                    -> digits        (jump straight to a numbered item / dial)
//   "*"                        -> "*"           (Talk: ask out loud / read screen aloud)
//   "/"                        -> "BROWSE"      (open the Browse menu)
//   "."  (Del)                 -> "DIAL"        (open the Dial pad)
//   "-"                        -> "PREV"        (move the highlight up / previous item)
//   "+"                        -> "NEXT"        (move the highlight down / next item)
//   Enter / NumpadEnter        -> "#"           (OK: open highlighted item / place call)
//   Backspace                  -> "BS"          (delete a dialed digit, otherwise back)
//   Escape                     -> "0"           (back / home)
//   "c" / "C"                  -> "CALL"        (green call button / future GPIO)
//   "h" / "H"                  -> "HANGUP"      (red hang-up button / future GPIO)

const DIGITS = new Set(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]);

function normalize(e) {
  const k = e.key;
  if (DIGITS.has(k)) return k;
  if (k === "*") return "*";
  if (k === "#") return "#";
  if (k === "Enter") return "#";
  if (k === "/") return "BROWSE";
  if (k === "." || k === "Delete") return "DIAL";
  if (k === "-") return "PREV";
  if (k === "+") return "NEXT";
  if (k === "Escape") return "0";
  if (k === "Backspace") return "BS";
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

      // When typing, let the field handle text entry. Escape and star remain
      // kiosk commands so users can back out or start voice search from Ask.
      if (typing && e.key !== "Escape" && e.key !== "*" && e.key !== "/") return;

      const mapped = normalize(e);
      if (!mapped) return;
      e.preventDefault();
      onKey(mapped);
    }

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onKey, enabled]);
}
