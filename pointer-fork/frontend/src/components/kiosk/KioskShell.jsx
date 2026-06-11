import { useEffect, useState } from "react";
import "./kiosk.css";
import { useKeypadInput } from "../../hooks/useKeypadInput.js";
import { SCREENS, TABS, useKioskStateMachine } from "../../hooks/useKioskStateMachine.js";
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

// The shared kiosk surface. `demo` adds the on-screen keypad + demo badge; the
// physical kiosk passes demo={false} and relies on the real keypad / keyboard.
export default function KioskShell({ demo = false }) {
  // /demo always simulates; /kiosk places real (allowlisted) calls when the
  // backend reports calling_enabled.
  const machine = useKioskStateMachine({ fakeCall: demo });
  const { state, handleKey, setQuery, setTab, selectMenuEntry, runQuery, dialDelete, dialClear } =
    machine;
  const [clock, setClock] = useState("");

  useKeypadInput(handleKey, { enabled: true });

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
          return <KioskMenu menu={state.menu} onMenuEntry={selectMenuEntry} />;
        }
        if (state.tab === TABS.DIAL) {
          return (
            <KioskDialPad
              number={state.dialNumber}
              onKey={handleKey}
              onDelete={dialDelete}
              onClear={dialClear}
            />
          );
        }
        return (
          <KioskAskHome
            query={state.query}
            menu={state.menu}
            onChange={setQuery}
            onSubmit={() => runQuery(state.query)}
            onMenuEntry={selectMenuEntry}
          />
        );
      case SCREENS.LOADING:
        return <CenterMessage title="Searching…" spinner />;
      case SCREENS.RESULTS_LIST:
        return (
          <KioskResourceList
            category={state.category}
            items={state.items}
            lastQuery={state.lastQuery}
            onKey={handleKey}
          />
        );
      case SCREENS.RESOURCE_DETAIL:
        return <KioskResourceDetail item={state.selected} onKey={handleKey} />;
      case SCREENS.CALL_CONFIRM:
        return <KioskCallConfirm item={state.selected} onKey={handleKey} />;
      case SCREENS.CALL_ACTIVE:
        return (
          <KioskCallActive
            item={state.selected}
            status={state.callStatus}
            simulated={state.callSimulated}
            reason={state.callReason}
            onKey={handleKey}
            onHangUp={hangUp}
          />
        );
      case SCREENS.EMPTY:
        return (
          <CenterMessage
            title="No match found"
            subtitle="Press 9 to call the 211 help line, or 0 to ask again."
          />
        );
      case SCREENS.ERROR:
        return (
          <CenterMessage
            title="Something went wrong"
            subtitle={`${state.error || "Please try again."} Press 0 to start over.`}
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
          <SimulatedKeypad onKey={handleKey} />
        </div>
      ) : null}
      <KioskFooterCommands onKey={handleKey} />
    </div>
  );
}
