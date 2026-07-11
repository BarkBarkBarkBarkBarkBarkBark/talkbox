import { useCallback, useEffect, useState } from "react";
import "./kiosk.css";
import { useKeypadInput } from "../../hooks/useKeypadInput.js";
import { SCREENS, TABS, useKioskStateMachine } from "../../hooks/useKioskStateMachine.js";
import { useSingleKioskWindow } from "../../hooks/useSingleKioskWindow.js";
import { playKeyTone } from "../../lib/keyTone.js";
import KioskStatusBar from "./KioskStatusBar.jsx";
import KioskFooterCommands from "./KioskFooterCommands.jsx";
import KioskTabs from "./KioskTabs.jsx";
import KioskAskHome from "./KioskAskHome.jsx";
import KioskDialPad from "./KioskDialPad.jsx";
import KioskMenu from "./KioskMenu.jsx";
import KioskResourceList from "./KioskResourceList.jsx";
import KioskResourceDetail from "./KioskResourceDetail.jsx";
import { KioskCallActive, KioskCallConfirm } from "./KioskCallScreen.jsx";
import SimulatedKeypad from "./SimulatedKeypad.jsx";

const INTRO_KEYSTROKES_TO_DISMISS = 2;

function CenterMessage({ title, subtitle, spinner }) {
  return (
    <div className="kiosk-content">
      <div className="kiosk-center">
        {spinner ? <div className="kiosk-spinner" /> : null}
        <h1 className="kiosk-title">{title}</h1>
        {subtitle ? <p className="kiosk-subtitle">{subtitle}</p> : null}
      </div>
    </div>
  );
}

function IntroHeroPanel({ keystrokes, onDismiss }) {
  const remaining = Math.max(0, INTRO_KEYSTROKES_TO_DISMISS - keystrokes);

  return (
    <section
      className="kiosk-intro-overlay"
      aria-live="polite"
      aria-label="Welcome to TalkBox. Tap anywhere to start."
      onClick={onDismiss}
    >
      <div className="kiosk-intro-panel">
        <header className="kiosk-intro-header">
          <div>
            <p className="kiosk-intro-eyebrow">Welcome to</p>
            <h1>TalkBox</h1>
          </div>
          <p className="kiosk-intro-header-note">Two quick paths to help</p>
        </header>

        <div className="kiosk-intro-grid">
          <div className="kiosk-intro-primary">
            <h2>Need shelter?</h2>
            <ol className="kiosk-intro-steps">
              <li><span>Press the <strong>big blue button</strong> to call 2-1-1</span></li>
              <li><span>Choose your language</span></li>
              <li><span>Press <strong>8</strong> for shelter and housing</span></li>
              <li><span>Ask for a <strong>Crisis assessment</strong></span></li>
              <li><span>Tell them <strong>where you are</strong></span></li>
              <li><span>Share medical needs or disabilities</span></li>
              <li><span>Say if you do not have a phone</span></li>
              <li><span>Ask how to follow up</span></li>
            </ol>
            <p className="kiosk-intro-note">
              Shelter may not be available today. Call 2-1-1 again when you can.
            </p>
          </div>

          <div className="kiosk-intro-secondary">
            <h2>Need something else?</h2>
            <div className="kiosk-intro-action-card kiosk-intro-action-card--white">
              <span>Press the big white button and ask</span>
            </div>
            <p className="kiosk-intro-note">
              Ask TalkBox:
            </p>
            <ul className="kiosk-intro-prompts">
              <li>"I'm looking for food"</li>
              <li>"I'm looking for mental health services"</li>
              <li>"I need medical care"</li>
            </ul>
          </div>
        </div>

        <div className="kiosk-intro-safety-row">
          <p className="kiosk-intro-call-note">
            You can use this phone to call pre-approved local resources that TalkBox finds.
          </p>
          <p className="kiosk-intro-911-warning">
            This phone WILL NOT CALL 911.
          </p>
        </div>

        <footer className="kiosk-intro-footer">
          <span className="kiosk-intro-key-prompt">
            {remaining === 1 ? "Press any key one more time" : "Press any key twice"}
          </span>
          <span className="kiosk-intro-touch-prompt">Tap anywhere to start</span>
          <span className="kiosk-intro-progress" aria-hidden="true">
            {Array.from({ length: INTRO_KEYSTROKES_TO_DISMISS }, (_, index) => (
              <span key={index} className={index < keystrokes ? "is-filled" : ""} />
            ))}
          </span>
        </footer>
      </div>
    </section>
  );
}

// The shared kiosk surface. `demo` adds the on-screen keypad + demo badge; the
// physical kiosk passes demo={false} and relies on the real keypad / keyboard.
export default function KioskShell({ demo = false }) {
  const windowLock = useSingleKioskWindow({ enabled: !demo });

  if (!windowLock.isPrimary) {
    return (
      <div className="kiosk-root">
        <KioskStatusBar title="Talk Box" demo={demo} mock={false} clock="" />
        <CenterMessage
          title="Kiosk already open"
          subtitle="Another Talk Box window is controlling the kiosk. Close the other window, then refresh."
        />
      </div>
    );
  }

  return <KioskRuntime demo={demo} />;
}

function KioskRuntime({ demo }) {
  // /demo always simulates; /kiosk places real (allowlisted) calls when the
  // backend reports calling_enabled.
  const machine = useKioskStateMachine({ fakeCall: demo });
  const {
    state,
    handleKey,
    setTab,
    selectMenuEntry,
    dialDelete,
    dialClear,
    dialCall,
  } = machine;
  const [clock, setClock] = useState("");
  const [introKeystrokes, setIntroKeystrokes] = useState(0);
  const showIntro = introKeystrokes < INTRO_KEYSTROKES_TO_DISMISS;

  const dismissIntro = useCallback(() => {
    setIntroKeystrokes(INTRO_KEYSTROKES_TO_DISMISS);
  }, []);

  const handleKeyWithTone = useCallback((key) => {
    playKeyTone(key);

    if (showIntro) {
      setIntroKeystrokes((count) => Math.min(INTRO_KEYSTROKES_TO_DISMISS, count + 1));
      return;
    }

    handleKey(key);
  }, [handleKey, showIntro]);

  useKeypadInput(handleKeyWithTone, { enabled: !showIntro });

  useEffect(() => {
    if (!showIntro) return undefined;

    function countIntroKey(e) {
      if (e.repeat) return;
      e.preventDefault();
      e.stopPropagation();
      setIntroKeystrokes((count) => Math.min(INTRO_KEYSTROKES_TO_DISMISS, count + 1));
    }

    window.addEventListener("keydown", countIntroKey, true);
    return () => window.removeEventListener("keydown", countIntroKey, true);
  }, [showIntro]);

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const date = now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
      const time = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      setClock(`${date}  ${time}`);
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const onHome = state.screen === SCREENS.ASK_HOME;

  function renderScreen() {
    switch (state.screen) {
      case SCREENS.ASK_HOME:
        if (state.tab === TABS.BROWSE) {
          return <KioskMenu menu={state.menu} cursor={state.cursor} onMenuEntry={selectMenuEntry} />;
        }
        if (state.tab === TABS.DIAL) {
          return (
            <KioskDialPad
              number={state.dialNumber}
              onKey={handleKeyWithTone}
              onCall={dialCall}
              onDelete={dialDelete}
              onClear={dialClear}
            />
          );
        }
        return (
          <KioskAskHome
            menu={state.menu}
            onKey={handleKeyWithTone}
            voiceStatus={state.voiceStatus}
            voiceError={state.voiceError}
            lastTranscript={state.lastTranscript}
            speechEnabled={state.speechEnabled}
          />
        );
      case SCREENS.LOADING:
        return <CenterMessage title="Searching…" spinner />;
      case SCREENS.RESULTS_LIST:
        return (
          <KioskResourceList
            category={state.category}
            items={state.items}
            cursor={state.cursor}
            lastQuery={state.lastQuery}
            onKey={handleKeyWithTone}
          />
        );
      case SCREENS.RESOURCE_DETAIL:
        return <KioskResourceDetail item={state.selected} onKey={handleKeyWithTone} />;
      case SCREENS.CALL_CONFIRM:
        return <KioskCallConfirm item={state.selected} />;
      case SCREENS.CALL_ACTIVE:
        return (
          <KioskCallActive
            item={state.selected}
            status={state.callStatus}
            simulated={state.callSimulated}
            reason={state.callReason}
            onKey={handleKeyWithTone}
          />
        );
      case SCREENS.EMPTY:
        return (
          <CenterMessage
            title="No match found"
            subtitle="Press 9 to call the 211 help line, or * to ask again."
          />
        );
      case SCREENS.ERROR:
        return (
          <CenterMessage
            title="Something went wrong"
            subtitle={`${state.error || "Please try again."} Press * to start over.`}
          />
        );
      default:
        return null;
    }
  }

  return (
    <div className="kiosk-root">
      <KioskStatusBar
        title={state.config?.name || "Talk Box"}
        demo={demo}
        mock={Boolean(state.config?.mock_mode)}
        clock={clock}
      />
      {onHome ? <KioskTabs tab={state.tab} onTab={setTab} /> : null}
      <div className="kiosk-screen" key={`${state.screen}-${state.tab}`}>
        {renderScreen()}
      </div>
      {demo && !(onHome && state.tab === TABS.DIAL) ? (
        <div className="kiosk-keypad-tray">
          <SimulatedKeypad onKey={handleKeyWithTone} variant="full" />
        </div>
      ) : null}
      <KioskFooterCommands onKey={handleKeyWithTone} hints={footerHints(state)} />
      {showIntro ? <IntroHeroPanel keystrokes={introKeystrokes} onDismiss={dismissIntro} /> : null}
    </div>
  );
}

function footerHints(state) {
  if (state.screen === SCREENS.CALL_ACTIVE) {
    return [
      { key: "BS", display: "⌫", label: "End call" },
      { key: "0", label: "Phone menu" },
      { key: "*", label: "Phone menu" },
      { key: "#", display: "↵", label: "Phone menu" },
    ];
  }
  if (state.screen === SCREENS.CALL_CONFIRM) {
    return [
      { key: "BS", display: "⌫", label: "Cancel" },
      { key: "#", display: "↵", label: "Call" },
    ];
  }
  if (state.screen === SCREENS.ASK_HOME && state.tab === TABS.ASK) {
    return [
      { key: "CYCLE_TAB", display: "/", label: "Change tab" },
      { key: "*", label: "Talk" },
    ];
  }
  if (state.screen === SCREENS.ASK_HOME && state.tab === TABS.DIAL) {
    return [
      { key: "CYCLE_TAB", display: "/", label: "Change tab" },
      { key: "BS", display: "⌫", label: "Delete" },
      { key: "#", display: "↵", label: "Call" },
    ];
  }
  if (state.screen === SCREENS.ASK_HOME && state.tab === TABS.BROWSE) {
    return [
      { key: "CYCLE_TAB", display: "/", label: "Change tab" },
      { key: "PREV", display: "–", label: "Up" },
      { key: "NEXT", display: "+", label: "Down" },
      { key: "#", display: "↵", label: "Open" },
    ];
  }
  if (state.screen === SCREENS.RESULTS_LIST) {
    return [
      { key: "PREV", display: "–", label: "Up" },
      { key: "NEXT", display: "+", label: "Down" },
      { key: "#", display: "↵", label: "Open" },
      { key: "BS", display: "⌫", label: "Back" },
    ];
  }
  return [
    { key: "BS", display: "⌫", label: "Back" },
    { key: "*", label: "Repeat" },
    { key: "#", display: "↵", label: "Select" },
  ];
}
