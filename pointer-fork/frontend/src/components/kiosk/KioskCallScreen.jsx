// Call confirmation + active-call screens.
export function KioskCallConfirm({ item, onKey }) {
  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        <h1 className="kiosk-title">Call this resource?</h1>
        <p className="kiosk-subtitle">{item?.name}</p>
        {item?.phone_display ? <p className="kiosk-phone">{item.phone_display}</p> : null}
        <p className="kiosk-subtitle" style={{ fontSize: "clamp(0.8rem,1.8vh,0.95rem)", opacity: 0.7 }}>
          This is a live call — please speak clearly into the microphone.
        </p>
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

const STATUS_LABEL = {
  connecting:    "Connecting…",
  ringing:       "Ringing…",
  "in-progress": "Call connected",
  connected:     "Call connected",
  ended:         "Call ended",
  failed:        "Call not placed",
};

export function KioskCallActive({ item, status, simulated, reason, onKey }) {
  const label = STATUS_LABEL[status] || "Calling…";
  const isLive = !simulated && (status === "in-progress" || status === "connected");
  const isPulsing = status === "connecting" || status === "ringing";

  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        {simulated ? <span className="kiosk-badge demo">Simulated call</span> : null}
        {isLive ? <span className="kiosk-badge" style={{background:"hsl(var(--success))",color:"hsl(var(--success-foreground))"}}>● Live call</span> : null}
        <h1 className={`kiosk-title ${isPulsing ? "kiosk-pulse" : ""}`}>{label}</h1>
        <p className="kiosk-subtitle">{item?.name}</p>
        {item?.phone_display ? <p className="kiosk-phone">{item.phone_display}</p> : null}
        {status === "failed" && reason ? <p className="kiosk-subtitle">{reason}</p> : null}
        {simulated ? (
          <p className="kiosk-subtitle">This is a demonstration. No real call is placed.</p>
        ) : null}
        <div className="kiosk-actions">
          <button type="button" className="kiosk-action back" onClick={() => onKey?.("0")}>
            <span className="k">0</span> {isLive ? "Hang up" : "Go back"}
          </button>
        </div>
      </div>
    </div>
  );
}
