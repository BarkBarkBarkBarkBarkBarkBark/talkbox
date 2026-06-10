// Call confirmation + active-call screens. Real outbound calling is gated by the
// backend (Twilio Voice + allowlist, milestone M6); until then the call is
// clearly labeled as simulated so the demo never dials a real number.
export function KioskCallConfirm({ item, onKey }) {
  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        <h1 className="kiosk-title">Call this resource?</h1>
        <p className="kiosk-subtitle">{item?.name}</p>
        {item?.phone_display ? <p className="kiosk-phone">{item.phone_display}</p> : null}
        <div className="kiosk-actions">
          <button type="button" className="kiosk-action back" onClick={() => onKey?.("0")}>
            <span className="k">0</span> Cancel
          </button>
          <button type="button" className="kiosk-action call" onClick={() => onKey?.("#")}>
            <span className="k">#</span> Call now
          </button>
        </div>
      </div>
    </div>
  );
}

export function KioskCallActive({ item, status, simulated, reason, onKey }) {
  const label =
    status === "connecting"
      ? "Connecting…"
      : status === "connected"
        ? "Call placed"
        : status === "failed"
          ? "Call not placed"
          : "Call";
  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        {simulated ? <span className="kiosk-badge demo">Simulated call</span> : null}
        <h1 className={`kiosk-title ${status === "connecting" ? "kiosk-pulse" : ""}`}>{label}</h1>
        <p className="kiosk-subtitle">{item?.name}</p>
        {item?.phone_display ? <p className="kiosk-phone">{item.phone_display}</p> : null}
        {status === "failed" && reason ? <p className="kiosk-subtitle">{reason}</p> : null}
        {simulated ? (
          <p className="kiosk-subtitle">
            This is a demonstration. No real call is placed.
          </p>
        ) : null}
        <div className="kiosk-actions">
          <button type="button" className="kiosk-action back" onClick={() => onKey?.("0")}>
            <span className="k">0</span> Hang up
          </button>
        </div>
      </div>
    </div>
  );
}
