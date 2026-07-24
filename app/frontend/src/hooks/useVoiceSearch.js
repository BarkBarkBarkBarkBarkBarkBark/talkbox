import { useCallback, useEffect, useRef, useState } from "react";
import { kioskApi } from "../lib/kioskApi.js";

const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];

// Explicit processing constraints: the kiosk mic (TONOR) and speaker (P10S)
// are separate devices, so the speakerphone's hardware echo cancellation
// never applies to the mic path — always ask the browser for software
// AEC / noise suppression / auto gain on every capture.
const MIC_CONSTRAINTS = {
  audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
  },
};

function chooseMimeType() {
  if (!window.MediaRecorder) return "";
  return MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

// Always-on mic level monitor. Mounts a persistent getUserMedia stream and
// runs an AudioContext analyser loop. Use in any component that needs a live
// volume reading without starting a full recording session.
export function useMicLevel({ enabled = true } = {}) {
  const [micLevel, setMicLevel] = useState(0);
  const [micReady, setMicReady] = useState(false);
  const streamRef = useRef(null);
  const contextRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;
    if (!navigator.mediaDevices?.getUserMedia) return;

    let cancelled = false;

    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS);
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;

        const ctx = new AudioContext();
        contextRef.current = ctx;

        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        ctx.createMediaStreamSource(stream).connect(analyser);

        const samples = new Uint8Array(analyser.fftSize);
        setMicReady(true);

        const tick = () => {
          if (cancelled) return;
          analyser.getByteTimeDomainData(samples);
          let sum = 0;
          for (let i = 0; i < samples.length; i++) {
            const s = (samples[i] - 128) / 128;
            sum += s * s;
          }
          const rms = Math.sqrt(sum / samples.length);
          setMicLevel(Math.min(1, rms * 6));
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
      } catch {
        // permission denied or no mic — stay at zero
      }
    };

    start();

    return () => {
      cancelled = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      contextRef.current?.close?.().catch(() => {});
      contextRef.current = null;
      streamRef.current?.getTracks?.().forEach((t) => t.stop());
      streamRef.current = null;
      setMicLevel(0);
      setMicReady(false);
    };
  }, [enabled]);

  return { micLevel, micReady };
}

export function useVoiceSearch({ maxSeconds = 6, enabled = true } = {}) {
  const [voiceStatus, setVoiceStatus] = useState("idle");
  const [voiceError, setVoiceError] = useState(null);
  const [lastTranscript, setLastTranscript] = useState("");
  const statusRef = useRef(voiceStatus);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    statusRef.current = voiceStatus;
  }, [voiceStatus]);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const cancelVoiceSearch = useCallback(() => {
    clearTimer();
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    recorderRef.current = null;
    stopStream();
    setVoiceStatus("idle");
  }, [clearTimer, stopStream]);

  const startVoiceSearch = useCallback(async () => {
    if (!enabled) {
      setVoiceError("Speech search is disabled.");
      setVoiceStatus("error");
      return null;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setVoiceError("This browser cannot record microphone audio.");
      setVoiceStatus("error");
      return null;
    }
    if (
      statusRef.current === "requesting-permission" ||
      statusRef.current === "listening" ||
      statusRef.current === "transcribing"
    ) {
      return null;
    }

    setVoiceError(null);
    setLastTranscript("");
    setVoiceStatus("requesting-permission");

    try {
      const stream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS);
      streamRef.current = stream;
      const mimeType = chooseMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks = [];
      recorderRef.current = recorder;

      const stopped = new Promise((resolve, reject) => {
        recorder.ondataavailable = (event) => {
          if (event.data?.size) chunks.push(event.data);
        };
        recorder.onerror = () => reject(new Error("Microphone recording failed."));
        recorder.onstop = () => resolve();
      });

      recorder.start();
      setVoiceStatus("listening");
      timerRef.current = setTimeout(() => {
        if (recorder.state !== "inactive") recorder.stop();
      }, Math.max(1, maxSeconds) * 1000);

      await stopped;
      clearTimer();
      recorderRef.current = null;
      stopStream();

      const blobType = chunks[0]?.type || mimeType || "audio/webm";
      const blob = new Blob(chunks, { type: blobType });
      if (!blob.size) throw new Error("No audio was recorded.");

      setVoiceStatus("transcribing");
      const result = await kioskApi.transcribeAudio(blob);
      const transcript = (result?.text || "").trim();
      if (!transcript) throw new Error(result?.error || "I could not hear that.");

      setLastTranscript(transcript);
      setVoiceStatus("idle");
      return transcript;
    } catch (err) {
      clearTimer();
      recorderRef.current = null;
      stopStream();
      setVoiceError(err.message || "Voice search failed.");
      setVoiceStatus("error");
      return null;
    }
  }, [clearTimer, enabled, maxSeconds, stopStream]);

  useEffect(() => cancelVoiceSearch, [cancelVoiceSearch]);

  return {
    startVoiceSearch,
    cancelVoiceSearch,
    voiceStatus,
    voiceError,
    lastTranscript,
  };
}
