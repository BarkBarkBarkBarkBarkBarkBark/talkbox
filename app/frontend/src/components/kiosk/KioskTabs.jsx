import { TABS } from "../../hooks/useKioskStateMachine.js";

// Tab bar on the home screen. Press "/" on the keypad to cycle Ask → Browse → Dial.
export default function KioskTabs({ tab, onTab }) {
  const tabs = [
    { id: TABS.ASK, label: "Ask" },
    { id: TABS.BROWSE, label: "Browse" },
    { id: TABS.DIAL, label: "Dial" },
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
          <span className="kiosk-tab-key" aria-hidden="true">/</span>
          <span className="kiosk-tab-label">{t.label}</span>
        </button>
      ))}
    </nav>
  );
}
