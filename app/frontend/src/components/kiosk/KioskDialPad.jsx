import { formatDialed } from "../../hooks/useKioskStateMachine.js";
import SimulatedKeypad from "./SimulatedKeypad.jsx";

const PhoneIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.3em" height="1.3em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/>
  </svg>
);

// Dial tab: enter a phone number with the keypad (physical, keyboard, or the
// on-screen pad) and press the green Call button (or #) to call. Calls go
// through the same CALL_CONFIRM flow as resources — nothing dials without
// confirmation, and real outbound calling stays gated by the backend allowlist.
export default function KioskDialPad({ number, onKey, onCall, onDelete, onClear }) {
  const display = formatDialed(number);
  const canCall = number.length >= 3;
  return (
    <div className="kiosk-content kiosk-dial-layout">
      {/* Left: number display + controls */}
      <div className="kiosk-dial-left">
        <div className="kiosk-dial-label">Dial a number</div>
        <div className="kiosk-dial-display" aria-label="Number entered">
          {display || <span className="kiosk-dial-placeholder">Enter…</span>}
        </div>
        <button
          type="button"
          className="kiosk-action call kiosk-dial-call"
          onClick={onCall}
          disabled={!canCall}
          aria-label="Call this number"
        >
          <PhoneIcon /> Call
        </button>
        <button type="button" className="kiosk-dial-btn kiosk-dial-delete" onClick={onDelete} disabled={!number}>⌫ Delete</button>
        <button type="button" className="kiosk-dial-btn kiosk-dial-clear" onClick={onClear} disabled={!number}>Clear</button>
        <p className="kiosk-dial-hint">Tip: dial <strong>211</strong> to reach the community help line</p>
      </div>
      {/* Right: keypad always fully visible */}
      <div className="kiosk-dial-right">
        <SimulatedKeypad onKey={onKey} />
      </div>
    </div>
  );
}
