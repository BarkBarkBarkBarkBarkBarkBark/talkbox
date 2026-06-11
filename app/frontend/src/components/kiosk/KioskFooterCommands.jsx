const PhoneIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" height="1.2em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/>
  </svg>
);

const HangUpIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.2em" height="1.2em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 9c-1.6 0-3.1.3-4.5.7v3.3c0 .4-.2.7-.5.9-1 .6-1.9 1.3-2.7 2.2-.2.2-.4.3-.7.3-.3 0-.5-.1-.7-.3L.2 13.4c-.2-.2-.2-.5 0-.7C3.2 9.5 7.4 8 12 8s8.8 1.5 11.8 4.7c.2.2.2.5 0 .7l-2.7 2.7c-.2.2-.4.3-.7.3-.3 0-.5-.1-.7-.3-.8-.9-1.7-1.6-2.7-2.2-.3-.2-.5-.5-.5-.9V9.7C15.1 9.3 13.6 9 12 9z"/>
  </svg>
);

// Always-visible command bar. The green Call and red Hang Up buttons emit the
// dedicated CALL / HANGUP keys — touch targets today, and the exact vocabulary
// a physical green/red button pair will emit later (keyboard: C / H).
export default function KioskFooterCommands({ onKey, hints }) {
  const items = hints || [
    { key: "0", label: "Back / Home" },
    { key: "*", label: "Repeat / Help" },
    { key: "#", label: "Select" },
  ];
  return (
    <footer className="kiosk-footer">
      <button
        type="button"
        className="kiosk-cmd kiosk-cmd-call"
        onClick={() => onKey?.("CALL")}
        aria-label="Call (green button)"
      >
        <PhoneIcon />
        <span>Call</span>
      </button>
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
      <button
        type="button"
        className="kiosk-cmd kiosk-cmd-hangup"
        onClick={() => onKey?.("HANGUP")}
        aria-label="Hang up (red button)"
      >
        <HangUpIcon />
        <span>Hang Up</span>
      </button>
    </footer>
  );
}
