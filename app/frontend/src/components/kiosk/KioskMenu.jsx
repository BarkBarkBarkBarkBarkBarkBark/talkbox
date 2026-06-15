// Browse tab: the backend-provided menu as numbered rows. Press the matching
// number to jump straight to a category, or use – / + to move the highlight
// and Enter to open it.
export default function KioskMenu({ menu, cursor = 0, onMenuEntry }) {
  return (
    <div className="kiosk-content">
      <h1 className="kiosk-title">Browse services</h1>
      <p className="kiosk-subtitle">
        Press a number, or use <strong>–</strong> / <strong>+</strong> to move and{" "}
        <strong>Enter</strong> to open.
      </p>
      <div className="kiosk-list">
        {menu.map((item, i) => (
          <button
            key={item.key}
            type="button"
            className={`kiosk-row ${i === cursor ? "is-selected" : ""}`}
            aria-current={i === cursor}
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
