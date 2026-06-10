// Persistent top bar: kiosk identity + status flags (mock data, demo mode).
export default function KioskStatusBar({ title = "Pointer", demo = false, mock = false, clock }) {
  return (
    <header className="kiosk-status">
      <span style={{ fontSize: "clamp(1rem, 3vh, 1.4rem)" }}>{title}</span>
      <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {mock ? <span className="kiosk-badge mock">Sample data</span> : null}
        {demo ? <span className="kiosk-badge demo">Demo</span> : null}
        {clock ? <span style={{ fontVariantNumeric: "tabular-nums" }}>{clock}</span> : null}
      </span>
    </header>
  );
}
