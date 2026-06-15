import { TABS } from "../../hooks/useKioskStateMachine.js";

// Tab bar shown on the home screen only: Ask, Browse, and Dial. Each tab is
// reachable by a single dedicated keypad key (shown as a badge) so a printed
// sticker over that key is always accurate: * = Ask, / = Browse, . = Dial.
export default function KioskTabs({ tab, onTab }) {
  const tabs = [
    { id: TABS.ASK, label: "Ask", badge: "*", key: "*" },
    { id: TABS.BROWSE, label: "Browse", badge: "/", key: "BROWSE" },
    { id: TABS.DIAL, label: "Dial", badge: ".", key: "DIAL" },
  ];
  return (
    <nav className="kiosk-tabs" aria-label="Mode">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`kiosk-tab ${tab === t.id ? "is-active" : ""}`}
          aria-pressed={tab === t.id}
          onClick={() => onTab?.(t.id)}
        >
          <span className="kiosk-tab-key" aria-hidden="true">{t.badge}</span>
          <span className="kiosk-tab-label">{t.label}</span>
        </button>
      ))}
    </nav>
  );
}
