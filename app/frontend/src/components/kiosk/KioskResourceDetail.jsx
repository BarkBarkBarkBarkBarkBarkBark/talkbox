// One focused resource. # calls (after a confirm screen), 0 returns to the list.
// Big touch targets mirror the keypad actions for touch panels and the demo.
export default function KioskResourceDetail({ item, onKey }) {
  if (!item) return null;
  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        <h1 className="kiosk-title">{item.name}</h1>
        {item.description ? <p className="kiosk-subtitle">{item.description}</p> : null}
        {item.address ? (
          <p className="kiosk-subtitle" style={{ margin: 0 }}>
            {item.address}
          </p>
        ) : null}
        {item.phone_display ? <p className="kiosk-phone">{item.phone_display}</p> : null}
        <div className="kiosk-actions">
          <button type="button" className="kiosk-action back" onClick={() => onKey?.("0")}>
            <span className="k">0</span> Back
          </button>
          <button type="button" className="kiosk-action call" onClick={() => onKey?.("#")}>
            <span className="k">#</span> Call
          </button>
        </div>
      </div>
    </div>
  );
}
