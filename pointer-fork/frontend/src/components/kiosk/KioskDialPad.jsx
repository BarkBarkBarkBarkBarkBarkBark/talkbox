import { formatDialed } from "../../hooks/useKioskStateMachine.js";
import SimulatedKeypad from "./SimulatedKeypad.jsx";

// Dial tab: enter a phone number with the keypad (physical, keyboard, or the
// on-screen pad below) and press # to call. Calls go through the same
// CALL_CONFIRM flow as resources — nothing dials without confirmation, and
// real outbound calling stays gated by the backend (simulated until M6).
export default function KioskDialPad({ number, onKey, onDelete, onClear }) {
  const display = formatDialed(number);
  return (
    <div className="kiosk-content">
      <h1 className="kiosk-title">Dial a number</h1>
      <p className="kiosk-subtitle">
        Enter the number, then press <strong>#</strong> to call. Backspace deletes a digit.
      </p>

      <div className="kiosk-dial-display" aria-label="Number entered">
        {display || <span className="kiosk-dial-placeholder">Enter a number…</span>}
      </div>

      <div className="kiosk-dial-edit">
        <button
          type="button"
          className="kiosk-dial-btn"
          onClick={onDelete}
          disabled={!number}
        >
          ⌫ Delete
        </button>
        <button
          type="button"
          className="kiosk-dial-btn"
          onClick={onClear}
          disabled={!number}
        >
          Clear
        </button>
      </div>

      <div className="kiosk-dial-pad">
        <SimulatedKeypad onKey={onKey} />
      </div>
    </div>
  );
}
