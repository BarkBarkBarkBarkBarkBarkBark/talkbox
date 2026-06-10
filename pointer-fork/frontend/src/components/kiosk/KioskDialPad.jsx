import { formatDialed } from "../../hooks/useKioskStateMachine.js";
import SimulatedKeypad from "./SimulatedKeypad.jsx";

// Dial tab: enter a phone number with the keypad (physical, keyboard, or the
// on-screen pad below) and press # to call. Calls go through the same
// CALL_CONFIRM flow as resources — nothing dials without confirmation, and
// real outbound calling stays gated by the backend (simulated until M6).
export default function KioskDialPad({ number, onKey, onDelete, onClear }) {
  const display = formatDialed(number);
  return (
    <div className="kiosk-content kiosk-dial-layout">
      {/* Left: number display + controls */}
      <div className="kiosk-dial-left">
        <div className="kiosk-dial-label">Dial a number</div>
        <div className="kiosk-dial-display" aria-label="Number entered">
          {display || <span className="kiosk-dial-placeholder">Enter…</span>}
        </div>
        <button type="button" className="kiosk-dial-btn kiosk-dial-delete" onClick={onDelete} disabled={!number}>⌫ Delete</button>
        <button type="button" className="kiosk-dial-btn kiosk-dial-clear" onClick={onClear} disabled={!number}>Clear</button>
        <p className="kiosk-dial-hint"><strong>#</strong> to call</p>
      </div>
      {/* Right: keypad always fully visible */}
      <div className="kiosk-dial-right">
        <SimulatedKeypad onKey={onKey} />
      </div>
    </div>
  );
}
