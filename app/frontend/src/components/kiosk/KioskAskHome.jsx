import { useEffect, useRef } from "react";
import { useMicLevel } from "../../hooks/useVoiceSearch.js";

const PhoneIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.3em" height="1.3em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/>
  </svg>
);

// Chat-first home surface (chat-first). Calling 211 is the
// headline action — a big green button anyone can hit without typing. The
// open-ended input and numbered category chips sit beneath it for people who
// want to find a specific organisation instead.
export default function KioskAskHome({
  query,
  menu,
  onChange,
  onSubmit,
  onMenuEntry,
  voiceStatus = "idle",
  voiceError = null,
  lastTranscript = "",
  speechEnabled = true,
}) {
  const ref = useRef(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);

  const { micLevel, micReady } = useMicLevel({ enabled: speechEnabled });

  const canSubmit = Boolean(query.trim());
  const isListening = voiceStatus === "listening";

  const voiceMessage = (() => {
    if (!speechEnabled) return "Speech search is unavailable.";
    if (voiceStatus === "requesting-permission") return "Allow microphone access.";
    if (isListening) return "Listening... speak now.";
    if (voiceStatus === "transcribing") return "Transcribing...";
    if (voiceStatus === "error") return voiceError || "Couldn't hear that. Press * and try again.";
    if (lastTranscript) return `I heard: ${lastTranscript}`;
    return "Press * to speak.";
  })();

  // VOICE_INPUT is redundant here (the input is right there) and CALL_211 is
  // promoted to the hero button above.
  const chips = (menu || []).filter(
    (m) => m.action !== "VOICE_INPUT" && m.action !== "CALL_211",
  );
  const call211Entry = (menu || []).find((m) => m.action === "CALL_211") || {
    key: 9,
    action: "CALL_211",
    label: "Call 211 help line",
  };

  return (
    <div className="kiosk-content kiosk-ask">
      <button
        type="button"
        className="kiosk-hero-211"
        onClick={() => onMenuEntry?.(call211Entry)}
        aria-label="Call 211 to get help now (key 9)"
      >
        <span className="kiosk-hero-211-icon">
          <PhoneIcon />
        </span>
        <span className="kiosk-hero-211-text">
          <span className="kiosk-hero-211-title">Call 211 — Get Help Now</span>
          <span className="kiosk-hero-211-sub">
            Free help line for shelter, food, health care and more
          </span>
        </span>
        <span className="kiosk-hero-211-key">{call211Entry.key}</span>
      </button>

      <p className="kiosk-subtitle kiosk-ask-or">
        Or search for a specific organisation — for example "I need a shelter for tonight".
      </p>

      <div
        className={`kiosk-voice-banner ${isListening ? "kiosk-pulse" : ""}`}
        aria-live="polite"
      >
        <span className="k">*</span>
        <div className="kiosk-voice-banner-body">
          <span>{voiceMessage}</span>
          {speechEnabled && (
            <div
              className={`kiosk-voice-meter ${isListening ? "kiosk-voice-meter--active" : ""}`}
              role="meter"
              aria-label="Microphone level"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(micLevel * 100)}
            >
              <div
                className="kiosk-voice-meter-fill"
                style={{ width: `${Math.max(micReady ? 2 : 0, micLevel * 100)}%` }}
              />
            </div>
          )}
        </div>
      </div>

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
