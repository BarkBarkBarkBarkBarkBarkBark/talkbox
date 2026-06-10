// Always-visible command hints for the three special keys. Clicking a hint
// also triggers the action (useful on a touch panel and in the browser demo).
export default function KioskFooterCommands({ onKey, hints }) {
  const items = hints || [
    { key: "0", label: "Back / Home" },
    { key: "*", label: "Repeat / Help" },
    { key: "#", label: "Select / Call" },
  ];
  return (
    <footer className="kiosk-footer">
      {items.map((h) => (
        <button
          key={h.key}
          type="button"
          className="kiosk-cmd"
          onClick={() => onKey?.(h.key)}
        >
          <span className="k">{h.key}</span>
          <span>{h.label}</span>
        </button>
      ))}
    </footer>
  );
}
