import { Component } from "react";
import { kioskApi } from "../../lib/kioskApi.js";

// Appliance guard rails for the kiosk surface: a crash screen that
// self-heals, the full-screen overlays (reconnecting / screen dim /
// "are you still there?"), and the hardware-fault banner.

const CRASH_RELOAD_DELAY_MS = 8000;

export class KioskErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { crashed: false };
  }

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  componentDidCatch(error) {
    kioskApi.logEvent({
      event_type: "ui_crash",
      payload: { message: String(error?.message || error) },
    });
    // A public kiosk must never sit on a broken screen: reload to recover.
    this.timer = setTimeout(() => window.location.reload(), CRASH_RELOAD_DELAY_MS);
  }

  componentWillUnmount() {
    if (this.timer) clearTimeout(this.timer);
  }

  render() {
    if (!this.state.crashed) return this.props.children;
    return (
      <div className="kiosk-root">
        <div className="kiosk-center" style={{ margin: "auto" }}>
          <div className="kiosk-spinner" />
          <h1 className="kiosk-title">Restarting…</h1>
          <p className="kiosk-subtitle">
            Sorry — something went wrong. The phone will be back in a few seconds.
          </p>
        </div>
      </div>
    );
  }
}

export function ReconnectOverlay() {
  return (
    <div className="kiosk-overlay kiosk-overlay-reconnect">
      <div className="kiosk-spinner" />
      <h1 className="kiosk-title">Reconnecting…</h1>
      <p className="kiosk-subtitle">
        The phone is having trouble reaching its service. It keeps trying
        automatically — please wait a moment.
      </p>
    </div>
  );
}

export function DimOverlay() {
  return (
    <div className="kiosk-overlay kiosk-overlay-dim">
      <p className="kiosk-dim-hint">Free phone — press any key to start</p>
    </div>
  );
}

// Shown when a live call has had no keypad activity for a long time (someone
// walked away mid-hold). Two escalating warnings, then the state machine
// hangs up. Tab (or a screen tap) confirms presence without sending DTMF.
export function PresenceOverlay({ level, onConfirm }) {
  return (
    <div className="kiosk-overlay kiosk-overlay-presence" onPointerDown={onConfirm}>
      <h1 className="kiosk-title">Are you still there?</h1>
      <p className="kiosk-subtitle">
        {level >= 2
          ? "The call will hang up in less than a minute."
          : "This call has been quiet for a while."}
      </p>
      <p className="kiosk-presence-action">
        Press the <kbd>Tab</kbd> key to stay on the call.
      </p>
    </div>
  );
}

export function HardwareBanner({ micMissing, speakerMissing }) {
  if (!micMissing && !speakerMissing) return null;
  const parts = [];
  if (micMissing) parts.push("microphone");
  if (speakerMissing) parts.push("speaker");
  return (
    <div className="kiosk-alert-banner" role="alert">
      Phone {parts.join(" and ")} not detected — calls may not work. Please tell staff.
    </div>
  );
}
