// On-screen 12-key ATM-style keypad for the browser demo and touch panels.
// It emits the exact same key vocabulary as the physical keypad, so the state
// machine cannot tell the difference between a tap, a keyboard press, and a
// real ATM key.
const LAYOUT = [
  ["1", "2", "3"],
  ["4", "5", "6"],
  ["7", "8", "9"],
  ["*", "0", "#"],
];

export default function SimulatedKeypad({ onKey }) {
  return (
    <div className="kiosk-keypad" aria-label="Keypad">
      {LAYOUT.flat().map((k) => (
        <button
          key={k}
          type="button"
          className={k === "#" ? "call" : k === "0" ? "back" : ""}
          onClick={() => onKey?.(k)}
          aria-label={k === "#" ? "Select or call" : k === "0" ? "Back or home" : `Key ${k}`}
        >
          {k}
        </button>
      ))}
    </div>
  );
}
