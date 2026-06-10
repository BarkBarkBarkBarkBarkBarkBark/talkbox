import { useCallback, useEffect, useRef, useState } from "react";
import { Device } from "@twilio/voice-sdk";
import { kioskApi } from "../lib/kioskApi.js";

// Call status vocabulary (matches CALL_STATUS dispatches in state machine):
//   idle | requesting | connecting | ringing | in-progress | ended | failed
export function useKioskVoiceCall({ onStatus }) {
  const deviceRef = useRef(null);
  const connectionRef = useRef(null);
  const [status, setStatus] = useState("idle");

  const updateStatus = useCallback(
    (s, reason) => {
      setStatus(s);
      onStatus?.(s, reason);
    },
    [onStatus],
  );

  // Tear down device on unmount
  useEffect(() => {
    return () => {
      try {
        deviceRef.current?.destroy();
      } catch (_) {}
      deviceRef.current = null;
    };
  }, []);

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

      // Tear down any previous device
      try {
        deviceRef.current?.destroy();
      } catch (_) {}

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

      // Device ready → connect
      device.on("ready", () => {
        try {
          const conn = device.connect({ params: { identity: tokenData.identity } });
          connectionRef.current = conn;

          conn.on("ringing", () => updateStatus("ringing"));
          conn.on("accept", () => updateStatus("in-progress"));
          conn.on("disconnect", () => {
            updateStatus("ended");
            device.destroy();
            deviceRef.current = null;
          });
          conn.on("error", (err) => {
            updateStatus("failed", err?.message || "Call error.");
            device.destroy();
            deviceRef.current = null;
          });
        } catch (err) {
          updateStatus("failed", "Could not connect the call.");
        }
      });

      device.on("error", (err) => {
        updateStatus("failed", err?.message || "Device error.");
      });

      // Register the device (required before connect in SDK v2)
      try {
        await device.register();
      } catch (err) {
        updateStatus("failed", "Could not reach the voice service.");
        return;
      }
    },
    [updateStatus],
  );

  const hangUp = useCallback(() => {
    try {
      connectionRef.current?.disconnect();
    } catch (_) {}
    try {
      deviceRef.current?.destroy();
    } catch (_) {}
    deviceRef.current = null;
    connectionRef.current = null;
    updateStatus("ended");
  }, [updateStatus]);

  return { status, startCall, hangUp };
}
