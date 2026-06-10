import { TABS } from "../../hooks/useKioskStateMachine.js";

// Tab bar shown on the home screen only: Ask (chat-first, default), Browse
// (numbered category menu), and Dial (enter a phone number). Touch/click
// driven; keypad users reach the same destinations via digits and 0.
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
          {t.label}
        </button>
      ))}
    </nav>
  );
}
