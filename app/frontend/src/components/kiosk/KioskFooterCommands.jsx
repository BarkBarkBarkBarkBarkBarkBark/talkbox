// Footer command hints — mirrors the physical keypad labels for the current screen.
export default function KioskFooterCommands({ onKey, hints }) {
  const items = hints || [
    { key: "BS", display: "⌫", label: "Back" },
    { key: "*", label: "Repeat / Help" },
    { key: "#", display: "↵", label: "Select" },
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
          <span className="k">{h.display || h.key}</span>
          <span>{h.label}</span>
        </button>
      ))}
    </footer>
  );
}
