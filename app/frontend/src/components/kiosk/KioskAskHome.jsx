import { useMicLevel } from "../../hooks/useVoiceSearch.js";

const PhoneIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.3em" height="1.3em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1L6.6 10.8z"/>
  </svg>
);

const MicIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="1.3em" height="1.3em" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
  </svg>
);

// Ask tab: Call 211 hero + push-to-talk voice entry (key *).
export default function KioskAskHome({
  menu,
  onKey,
  voiceStatus = "idle",
  voiceError = null,
  lastTranscript = "",
  speechEnabled = true,
}) {
  const { micLevel, micReady } = useMicLevel({ enabled: speechEnabled });

  const isListening = voiceStatus === "listening";

  const voiceMessage = (() => {
    if (!speechEnabled) return "Speech search is unavailable.";
    if (voiceStatus === "requesting-permission") return "Allow microphone access.";
    if (isListening) return "Listening… speak now.";
    if (voiceStatus === "transcribing") return "Transcribing…";
    if (voiceStatus === "error") return voiceError || "Couldn't hear that. Press * and try again.";
    if (lastTranscript) return `I heard: ${lastTranscript}`;
    return "Press * to speak.";
  })();

  const call211Entry = (menu || []).find((m) => m.action === "CALL_211") || {
    key: 9,
    action: "CALL_211",
    label: "Call 211 help line",
  };

  return (
    <div className="kiosk-content kiosk-ask">
      <button
        type="button"
        className="kiosk-ask-card kiosk-ask-card--call"
        onClick={() => onKey?.(String(call211Entry.key))}
        aria-label="Call 211 help line"
      >
        <span className="kiosk-ask-card-icon">
          <PhoneIcon />
        </span>
        <span className="kiosk-ask-card-title">Call 211</span>
        <span className="kiosk-ask-card-action">
          Press <span className="kiosk-ask-card-key">{call211Entry.key}</span>
        </span>
      </button>

      <button
        type="button"
        className={`kiosk-ask-card kiosk-ask-card--talk ${isListening ? "kiosk-ask-card--active kiosk-pulse" : ""}`}
        onClick={() => onKey?.("*")}
        aria-live="polite"
        aria-label="Ask for something using voice"
      >
        <span className="kiosk-ask-card-icon">
          <MicIcon />
        </span>
        <span className="kiosk-ask-card-title">Ask for Something</span>
        <span className="kiosk-ask-card-action">
          Press <span className="kiosk-ask-card-key">*</span> to talk
        </span>
        <span className="kiosk-ask-card-status">{voiceMessage}</span>
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
      </button>
    </div>
  );
}
