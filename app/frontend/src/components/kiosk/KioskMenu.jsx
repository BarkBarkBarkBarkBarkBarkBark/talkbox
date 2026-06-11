// Browse tab: the backend-provided menu as numbered rows so each maps to a
// single number key (1-9). No scrolling expected at rest.
export default function KioskMenu({ menu, onMenuEntry }) {
  return (
    <div className="kiosk-content">
      <h1 className="kiosk-title">Browse services</h1>
      <p className="kiosk-subtitle">Press a number to choose a category. Press 0 to go back.</p>
      <div className="kiosk-list">
        {menu.map((item) => (
          <button
            key={item.key}
            type="button"
            className="kiosk-row"
            onClick={() => onMenuEntry?.(item)}
          >
            <span className="kiosk-key-badge">{item.key}</span>
            <span className="kiosk-row-body">
              <span className="kiosk-row-title">{item.label}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
