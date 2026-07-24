import { useEffect, useState } from "react";
import { kioskApi } from "../lib/kioskApi.js";

// Watches the browser's view of the audio hardware. The kiosk is a phone —
// if the microphone or speaker disappears (USB unplugged, hub glitch) we
// surface a maintenance banner and log telemetry instead of failing silently
// on the next call.
//
// Expected hardware (matched against MediaDeviceInfo.label when available):
//   input:  TONOR USB microphone
//   output: MV-SILICON P10S puck speakerphone
//
// A missing device *class* (no inputs / no outputs at all) is a hard failure
// and raises the banner. A label mismatch is telemetry only — the OS
// audio-init script may have legitimately fallen back to another card, and
// ALSA-only Chromium often reports generic labels like "Default".
const MIC_LABEL = /tonor/i;
const SPEAKER_LABEL = /p10s|mv[\s-]?silicon/i;

export function useAudioHealth() {
  const [health, setHealth] = useState({ micMissing: false, speakerMissing: false });

  useEffect(() => {
    const md = navigator.mediaDevices;
    if (!md?.enumerateDevices) return undefined;
    let cancelled = false;
    let lastReport = "";

    const check = async () => {
      let devices;
      try {
        devices = await md.enumerateDevices();
      } catch {
        return;
      }
      if (cancelled) return;
      const inputs = devices.filter((d) => d.kind === "audioinput");
      const outputs = devices.filter((d) => d.kind === "audiooutput");
      const labelled = devices.some((d) => d.label);
      const micMissing = inputs.length === 0;
      const speakerMissing = outputs.length === 0;
      const micMatched = labelled ? inputs.some((d) => MIC_LABEL.test(d.label)) : null;
      const speakerMatched = labelled ? outputs.some((d) => SPEAKER_LABEL.test(d.label)) : null;

      setHealth({ micMissing, speakerMissing });

      const payload = {
        mic_missing: micMissing,
        speaker_missing: speakerMissing,
        mic_matched: micMatched,
        speaker_matched: speakerMatched,
        input_count: inputs.length,
        output_count: outputs.length,
      };
      const report = JSON.stringify(payload);
      if (report !== lastReport) {
        lastReport = report;
        kioskApi.logEvent({ event_type: "audio_health", payload });
      }
    };

    check();
    const onChange = () => check();
    md.addEventListener?.("devicechange", onChange);
    return () => {
      cancelled = true;
      md.removeEventListener?.("devicechange", onChange);
    };
  }, []);

  return health;
}
