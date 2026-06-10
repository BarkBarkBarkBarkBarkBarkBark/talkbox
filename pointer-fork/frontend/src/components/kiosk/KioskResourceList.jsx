// Numbered resource results. Press N (or tap a row) to open the detail screen.
// The asked question is echoed so the single-turn flow stays legible.
export default function KioskResourceList({ category, items, lastQuery, onKey }) {
  return (
    <div className="kiosk-content">
      {lastQuery ? (
        <p className="kiosk-asked">
          You asked: <em>“{lastQuery}”</em>
        </p>
      ) : null}
      <h1 className="kiosk-title">{category || "Results"}</h1>
      <p className="kiosk-subtitle">Press a number to choose. Press 0 to ask again.</p>
      <div className="kiosk-list">
        {items.map((item) => (
          <button
            key={item.number}
            type="button"
            className="kiosk-row"
            onClick={() => onKey?.(String(item.number))}
          >
            <span className="kiosk-key-badge">{item.number}</span>
            <span className="kiosk-row-body">
              <span className="kiosk-row-title">{item.name}</span>
              {item.description ? (
                <span className="kiosk-row-meta">{item.description}</span>
              ) : null}
            </span>
            {item.phone_display ? (
              <span className="kiosk-row-phone">{item.phone_display}</span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
