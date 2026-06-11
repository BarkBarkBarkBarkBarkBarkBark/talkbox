import { useCallback, useEffect, useRef, useState } from "react";
import { Device } from "@twilio/voice-sdk";
import { kioskApi } from "../lib/kioskApi.js";

// Call status vocabulary (matches CALL_STATUS dispatches in state machine):
//   idle | requesting | connecting | ringing | in-progress | ended | failed
export function useKioskVoiceCall({ onStatus }) {
  const deviceRef = useRef(null);
  const callRef = useRef(null);
  const [status, setStatus] = useState("idle");

  const updateStatus = useCallback(
    (s, reason) => {
      setStatus(s);
      onStatus?.(s, reason);
    },
    [onStatus],
  );

  const teardown = useCallback(() => {
    try {
      callRef.current?.disconnect();
    } catch (_) {}
    try {
      deviceRef.current?.destroy();
    } catch (_) {}
    callRef.current = null;
    deviceRef.current = null;
  }, []);

  // Tear down device on unmount
  useEffect(() => teardown, [teardown]);

  const startCall = useCallback(
    async (phone, name) => {
      updateStatus("requesting");
      let tokenData;
      try {
        tokenData = await kioskApi.requestVoiceToken({ phone, name });
      } catch (err) {
        const reason =
          err.status === 403
            ? "This number is not on the approved call list."
            : err.status === 503
              ? "Browser calling is not configured on this device."
              : "The call could not be placed.";
        updateStatus("failed", reason);
        return;
      }

      // Tear down any previous device/call
      teardown();

      updateStatus("connecting");

      let device;
      try {
        device = new Device(tokenData.token, {
          logLevel: "warn",
          codecPreferences: ["opus", "pcmu"],
        });
        deviceRef.current = device;
      } catch (err) {
        updateStatus("failed", "Audio device could not be initialised.");
        return;
      }

      device.on("error", (err) => {
        updateStatus("failed", err?.message || "Device error.");
      });

      // Voice SDK v2: outgoing calls connect directly — no registration needed
      // (registration is only required to *receive* calls). connect() resolves
      // to a Call object once media setup (incl. mic permission) succeeds.
      let call;
      try {
        call = await device.connect({ params: { identity: tokenData.identity } });
      } catch (err) {
        const message = String(err?.message || "").trim();
        const reason = /permission|denied|notallowed/i.test(message)
          ? "Microphone access was blocked. Please allow the microphone."
          : message
            ? `Could not connect the call. ${message}`
            : "Could not connect the call.";
        updateStatus("failed", reason);
        teardown();
        return;
      }
      callRef.current = call;

      call.on("ringing", () => updateStatus("ringing"));
      call.on("accept", () => updateStatus("in-progress"));
      call.on("disconnect", () => {
        updateStatus("ended");
        teardown();
      });
      call.on("error", (err) => {
        updateStatus("failed", err?.message || "Call error.");
        teardown();
      });
    },
    [teardown, updateStatus],
  );

  // Send DTMF tones to the far end (IVR menus, extensions, etc).
  const sendDigits = useCallback((digits) => {
    try {
      callRef.current?.sendDigits(String(digits));
    } catch (_) {}
  }, []);

  const hangUp = useCallback(() => {
    teardown();
    updateStatus("ended");
  }, [teardown, updateStatus]);

  return { status, startCall, hangUp, sendDigits };
}
