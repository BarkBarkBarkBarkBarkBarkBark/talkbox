const PhoneIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.4em" height="1.4em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/>
  </svg>
);

const HangUpIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.4em" height="1.4em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 9c-1.6 0-3.1.3-4.5.7v3.3c0 .4-.2.7-.5.9-1 .6-1.9 1.3-2.7 2.2-.2.2-.4.3-.7.3-.3 0-.5-.1-.7-.3L.2 13.4c-.2-.2-.2-.5 0-.7C3.2 9.5 7.4 8 12 8s8.8 1.5 11.8 4.7c.2.2.2.5 0 .7l-2.7 2.7c-.2.2-.4.3-.7.3-.3 0-.5-.1-.7-.3-.8-.9-1.7-1.6-2.7-2.2-.3-.2-.5-.5-.5-.9V9.7C15.1 9.3 13.6 9 12 9z"/>
  </svg>
);

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
          <button type="button" className="kiosk-action hangup" onClick={() => onKey?.("0")}>
            <HangUpIcon /> Cancel
          </button>
          <button type="button" className="kiosk-action call" onClick={() => onKey?.("#")}>
            <PhoneIcon /> Call
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
          <button type="button" className={isLive ? "kiosk-action hangup" : "kiosk-action back"} onClick={() => onKey?.("0")}>
            {isLive ? <HangUpIcon /> : null} {isLive ? "End call" : "Go back"}
          </button>
        </div>
      </div>
    </div>
  );
}
