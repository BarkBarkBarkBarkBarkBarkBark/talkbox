import { useEffect, useRef } from "react";

// Chat-first home surface (original Pointer style). The open-ended input is
// the primary control; compact numbered category chips sit beneath it so a
// keypad-only user can still press 1-9 while the input is empty.
export default function KioskAskHome({ query, menu, onChange, onSubmit, onMenuEntry }) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);

  const canSubmit = Boolean(query.trim());
  // VOICE_INPUT is redundant on the ask surface — the input is already here.
  const chips = (menu || []).filter((m) => m.action !== "VOICE_INPUT");

  return (
    <div className="kiosk-content kiosk-ask">
      <h1 className="kiosk-title">What do you need?</h1>
      <p className="kiosk-subtitle">
        Type or speak in your own words — for example “I need a shelter for tonight”.
      </p>

      <form
        className="kiosk-ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
      >
        <textarea
          ref={ref}
          className="kiosk-ask-input"
          rows={2}
          value={query}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
          placeholder="I need help with…"
          aria-label="Describe what you need"
        />
        <button
          type="submit"
          className="kiosk-ask-submit"
          disabled={!canSubmit}
          aria-label="Search (hash key)"
        >
          <span className="k">#</span>
          Search
        </button>
      </form>

      <div className="kiosk-ask-chips" aria-label="Quick categories">
        {chips.map((item) => (
          <button
            key={item.key}
            type="button"
            className="kiosk-chip"
            onClick={() => onMenuEntry?.(item)}
          >
            <span className="kiosk-chip-key">{item.key}</span>
            {item.label}
          </button>
        ))}
      </div>
    </div>
  );
}
