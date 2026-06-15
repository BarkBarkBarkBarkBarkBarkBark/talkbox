// On-screen keypad for the browser demo and touch panels. It emits the exact
// same key tokens as the physical USB numpad, so the state machine cannot tell
// the difference between a tap, a keyboard press, and a real keypad key.
//
// variant="numeric"  → plain 3x4 number pad, used inside the Dial tab.
// variant="full"     → mirrors a real USB numpad including the navigation keys
//                      (/ Browse, * Talk, – Up, + Down, Enter OK, . Dial, ⌫).

const NUMERIC = [
  { label: "1", token: "1" },
  { label: "2", token: "2" },
  { label: "3", token: "3" },
  { label: "4", token: "4" },
  { label: "5", token: "5" },
  { label: "6", token: "6" },
  { label: "7", token: "7" },
  { label: "8", token: "8" },
  { label: "9", token: "9" },
  { label: "*", token: "*" },
  { label: "0", token: "0" },
  { label: "#", token: "#" },
];

const FULL = [
  { label: "/", token: "BROWSE" },
  { label: "*", token: "*" },
  { label: "⌫", token: "BS" },
  { label: "7", token: "7" },
  { label: "8", token: "8" },
  { label: "9", token: "9" },
  { label: "–", token: "PREV" },
  { label: "4", token: "4" },
  { label: "5", token: "5" },
  { label: "6", token: "6" },
  { label: "+", token: "NEXT" },
  { label: "1", token: "1" },
  { label: "2", token: "2" },
  { label: "3", token: "3" },
  { label: "↵", token: "#" },
  { label: "0", token: "0", span: 2 },
  { label: ".", token: "DIAL" },
];

export default function SimulatedKeypad({ onKey, variant = "numeric" }) {
  const keys = variant === "full" ? FULL : NUMERIC;
  return (
    <div className={`kiosk-keypad ${variant === "full" ? "kiosk-keypad--full" : ""}`} aria-label="Keypad">
      {keys.map((k) => (
        <button
          key={k.token + k.label}
          type="button"
          onClick={() => onKey?.(k.token)}
          aria-label={`Key ${k.label}`}
          style={k.span ? { gridColumn: `span ${k.span}` } : undefined}
        >
          {k.label}
        </button>
      ))}
    </div>
  );
}
