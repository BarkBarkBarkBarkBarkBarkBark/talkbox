// On-screen 12-key ATM-style keypad for the browser demo and touch panels.
// It emits the exact same key vocabulary as the physical keypad, so the state
// machine cannot tell the difference between a tap, a keyboard press, and a
// real ATM key. All twelve keys are neutral — call / hang-up actions live on
// dedicated green and red buttons in the surrounding screens, never on the
// keypad itself (so e.g. pressing 0 on an IVR is never confused with hanging up).
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
        <button key={k} type="button" onClick={() => onKey?.(k)} aria-label={`Key ${k}`}>
          {k}
        </button>
      ))}
    </div>
  );
}
