import { useCallback, useEffect, useReducer, useRef } from "react";
import { kioskApi } from "../lib/kioskApi.js";
import { cancelSpeech, speak } from "../lib/tts.js";
import { useKioskVoiceCall } from "./useKioskVoiceCall.js";

// Deterministic kiosk navigation driven entirely by the 12-key vocabulary
// ("1".."9", "0", "*", "#"). The same machine backs the physical ATM keypad,
// a laptop keyboard, and the on-screen simulated keypad.
//
// The home surface is chat-first (original Pointer style): an open-ended
// "what do you need?" input is the primary screen, with a Browse tab that
// lists the numbered category menu for keypad-only users.
//
// Screens:
//   ASK_HOME        chat-first home; ask tab = free-text input, browse tab = menu
//   LOADING         awaiting backend
//   RESULTS_LIST    numbered resources, press N to select
//   RESOURCE_DETAIL one focused resource, # to call
//   CALL_CONFIRM    confirm before dialing (no arbitrary dialing)
//   CALL_ACTIVE     simulated/active call, 0 to hang up
//   EMPTY           no match, offers 211
//   ERROR           backend/network failure
//
// Safety invariants:
//   - 0 always returns to the previous safe screen (or home).
//   - * always repeats / help-prompts the current screen (aloud).
//   - # never starts a call unless a resource is selected; the backend remains
//     the source of truth for whether a call is actually allowed.

export const SCREENS = {
  ASK_HOME: "ASK_HOME",
  LOADING: "LOADING",
  RESULTS_LIST: "RESULTS_LIST",
  RESOURCE_DETAIL: "RESOURCE_DETAIL",
  CALL_CONFIRM: "CALL_CONFIRM",
  CALL_ACTIVE: "CALL_ACTIVE",
  EMPTY: "EMPTY",
  ERROR: "ERROR",
};

export const TABS = {
  ASK: "ask",
  BROWSE: "browse",
  DIAL: "dial",
};

const MAX_DIAL_DIGITS = 11;

const initialState = {
  screen: SCREENS.ASK_HOME,
  tab: TABS.ASK,
  config: null,
  menu: [],
  query: "",
  lastQuery: "",
  dialNumber: "",
  category: null,
  items: [],
  fallback: null,
  selected: null,
  spokenSummary: "",
  error: null,
  callStatus: "idle", // idle | connecting | connected | ended | failed
  callSimulated: true,
  callReason: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "CONFIG_LOADED":
      return { ...state, config: action.config, menu: action.config.menu || [] };
    case "SET_QUERY":
      return { ...state, query: action.query };
    case "SET_TAB":
      return { ...state, screen: SCREENS.ASK_HOME, tab: action.tab, error: null };
    case "GO_HOME":
      return { ...state, screen: SCREENS.ASK_HOME, callStatus: "idle", error: null };
    case "DIAL_APPEND":
      if (state.dialNumber.length >= MAX_DIAL_DIGITS) return state;
      return { ...state, dialNumber: state.dialNumber + action.digit };
    case "DIAL_DELETE":
      return { ...state, dialNumber: state.dialNumber.slice(0, -1) };
    case "DIAL_CLEAR":
      return { ...state, dialNumber: "" };
    case "LOADING":
      return { ...state, screen: SCREENS.LOADING, error: null };
    case "RESULTS":
      return {
        ...state,
        screen: action.items.length ? SCREENS.RESULTS_LIST : SCREENS.EMPTY,
        lastQuery: action.query || state.lastQuery,
        category: action.category,
        items: action.items,
        fallback: action.fallback,
        spokenSummary: action.spokenSummary,
        selected: null,
        error: null,
      };
    case "SELECT":
      return { ...state, screen: SCREENS.RESOURCE_DETAIL, selected: action.item };
    case "CALL_CONFIRM":
      return { ...state, screen: SCREENS.CALL_CONFIRM, selected: action.item ?? state.selected };
    case "CALL_STATUS":
      return {
        ...state,
        screen: SCREENS.CALL_ACTIVE,
        callStatus: action.status,
        callSimulated: action.simulated ?? state.callSimulated,
        callReason: action.reason ?? null,
      };
    case "BACK_TO_RESULTS":
      // From a dial-pad or 211 call there may be no results to return to.
      return {
        ...state,
        screen: state.items.length ? SCREENS.RESULTS_LIST : SCREENS.ASK_HOME,
        callStatus: "idle",
      };
    case "ERROR":
      return { ...state, screen: SCREENS.ERROR, error: action.error };
    case "RESET":
      return { ...initialState, config: state.config, menu: state.menu };
    default:
      return state;
  }
}

export function formatDialed(digits) {
  if (!digits) return "";
  if (digits.length === 11 && digits.startsWith("1"))
    return `+1 (${digits.slice(1, 4)}) ${digits.slice(4, 7)}-${digits.slice(7)}`;
  if (digits.length === 10)
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  if (digits.length === 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return digits;
}

function describeScreen(state) {
  switch (state.screen) {
    case SCREENS.ASK_HOME:
      if (state.tab === TABS.BROWSE)
        return "Browse menu. Press a number to choose a category, or press zero to go back to asking.";
      if (state.tab === TABS.DIAL)
        return "Dial pad. Enter a phone number with the keypad, then press the green Call button or the hash key to call.";
      return "Tell us what you need. Type or speak, then press the hash key to search.";
    case SCREENS.RESULTS_LIST:
      return state.spokenSummary || "Here are your results. Press a number to choose one.";
    case SCREENS.RESOURCE_DETAIL: {
      const s = state.selected;
      if (!s) return "No resource selected.";
      return `${s.name}. ${s.description || ""} Press the hash key to call, or zero to go back.`;
    }
    case SCREENS.CALL_CONFIRM:
      return `Call ${state.selected?.name || "this resource"}? Press the green Call button or hash to confirm, or zero to cancel.`;
    case SCREENS.CALL_ACTIVE:
      return "Call in progress. Use the keypad to answer phone menus. Press the red End Call button to hang up.";
    case SCREENS.EMPTY:
      return state.spokenSummary || "No match found. You can call 211 for help.";
    case SCREENS.ERROR:
      return "Something went wrong. Press zero to return to the menu.";
    default:
      return "";
  }
}

export function useKioskStateMachine({ fakeCall = true } = {}) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const stateRef = useRef(state);
  stateRef.current = state;

  const idleTimer = useRef(null);
  const callTimer = useRef(null);

  // ─── Voice SDK hook (real two-way calls) ─────────────────────────────
  const voiceCall = useKioskVoiceCall({
    onStatus: useCallback((sdkStatus, reason) => {
      // Map SDK status vocabulary → state machine CALL_STATUS dispatch
      const map = {
        requesting:   { status: "connecting", simulated: false },
        connecting:   { status: "connecting", simulated: false },
        ringing:      { status: "connecting", simulated: false },
        "in-progress": { status: "connected",  simulated: false },
        ended:        null,  // handled by hangUp path
        failed:       { status: "failed",    simulated: false, reason },
      };
      const mapped = map[sdkStatus];
      if (mapped) {
        dispatch({ type: "CALL_STATUS", ...mapped });
      } else if (sdkStatus === "ended") {
        dispatch({ type: "BACK_TO_RESULTS" });
      }
    }, []),
  });

  // ─── Config ──────────────────────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    kioskApi
      .config()
      .then((cfg) => {
        if (alive) dispatch({ type: "CONFIG_LOADED", config: cfg });
      })
      .catch(() => {
        // Config is best-effort; a default menu still works offline.
        if (alive) dispatch({ type: "ERROR", error: "Cannot reach kiosk service." });
      });
    return () => {
      alive = false;
    };
  }, []);

  const announce = useCallback((text) => speak(text), []);

  // ─── Inactivity auto-reset ───────────────────────────────────────────
  const armIdleTimer = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    const secs = stateRef.current.config?.idle_reset_seconds || 60;
    idleTimer.current = setTimeout(() => {
      // Never interrupt an active call.
      if (stateRef.current.screen === SCREENS.CALL_ACTIVE) {
        armIdleTimer();
        return;
      }
      cancelSpeech();
      dispatch({ type: "RESET" });
      kioskApi.logEvent({ event_type: "auto_reset", payload: { reason: "inactivity" } });
    }, secs * 1000);
  }, []);

  useEffect(() => {
    armIdleTimer();
    return () => {
      if (idleTimer.current) clearTimeout(idleTimer.current);
    };
  }, [armIdleTimer]);

  // ─── Actions ─────────────────────────────────────────────────────────
  const runQuery = useCallback(
    async (text) => {
      const q = (text || "").trim();
      if (!q) return;
      cancelSpeech();
      armIdleTimer();
      dispatch({ type: "LOADING" });
      kioskApi.logEvent({ event_type: "query", payload: { query: q } });
      try {
        const data = await kioskApi.query(q);
        dispatch({
          type: "RESULTS",
          query: q,
          items: data.items || [],
          category: data.category || null,
          fallback: data.fallback || null,
          spokenSummary: data.spoken_summary || "",
        });
        announce(data.spoken_summary || "");
      } catch (err) {
        dispatch({ type: "ERROR", error: err.message || "Query failed." });
        announce("Something went wrong. Press zero to return to the menu.");
      }
    },
    [announce, armIdleTimer],
  );

  const setTab = useCallback(
    (tab) => {
      armIdleTimer();
      kioskApi.logEvent({ event_type: "tab", payload: { tab } });
      dispatch({ type: "SET_TAB", tab });
    },
    [armIdleTimer],
  );

  // Shared handler for menu entries — used by the Browse tab, the quick
  // chips on the Ask tab, and digit keys when the input is empty.
  const selectMenuEntry = useCallback(
    (entry) => {
      if (!entry) return;
      armIdleTimer();
      if (entry.action === "QUICK_QUERY" && entry.query) {
        runQuery(entry.query);
      } else if (entry.action === "VOICE_INPUT") {
        dispatch({ type: "SET_TAB", tab: TABS.ASK });
        announce("Type or speak what you need, then press hash to search.");
      } else if (entry.action === "CALL_211") {
        const item = stateRef.current.fallback || {
          name: "211 help line",
          phone: "+19164981000",
          phone_display: "211 (help line)",
        };
        dispatch({ type: "CALL_CONFIRM", item });
        announce("Call the 211 help line? Press the green Call button or hash to confirm.");
      }
    },
    [announce, armIdleTimer, runQuery],
  );

  // ─── Dial pad ────────────────────────────────────────────────────────
  const dialDelete = useCallback(() => {
    armIdleTimer();
    dispatch({ type: "DIAL_DELETE" });
  }, [armIdleTimer]);

  const dialClear = useCallback(() => {
    armIdleTimer();
    dispatch({ type: "DIAL_CLEAR" });
  }, [armIdleTimer]);

  const dialCall = useCallback(() => {
    const digits = stateRef.current.dialNumber;
    if (digits.length < 3) return;
    armIdleTimer();
    const item = {
      name: "Dialed number",
      phone: digits,
      phone_display: formatDialed(digits),
    };
    dispatch({ type: "CALL_CONFIRM", item });
    announce(`Call ${formatDialed(digits)}? Press hash to confirm, or zero to cancel.`);
  }, [announce, armIdleTimer]);

  const startCall = useCallback(
    (item) => {
      const target = item || stateRef.current.selected;
      if (!target) return;
      const callingEnabled = Boolean(stateRef.current.config?.calling_enabled);
      const simulated = fakeCall || !callingEnabled || !target.phone;
      kioskApi.logEvent({
        event_type: "call_start",
        payload: { name: target.name, simulated },
      });
      dispatch({ type: "CALL_STATUS", status: "connecting", simulated });
      announce(`Calling ${target.name}.`);
      if (callTimer.current) clearTimeout(callTimer.current);

      if (simulated) {
        callTimer.current = setTimeout(() => {
          dispatch({ type: "CALL_STATUS", status: "connected", simulated });
        }, 1500);
        return;
      }

      // Real two-way call via Twilio Voice Browser SDK.
      // The hook handles token fetch, Device init, and status callbacks.
      voiceCall.startCall(target.phone, target.name);
    },
    [announce, fakeCall],
  );

  const hangUp = useCallback(() => {
    if (callTimer.current) clearTimeout(callTimer.current);
    cancelSpeech();
    voiceCall.hangUp();
    kioskApi.logEvent({ event_type: "call_end" });
    dispatch({ type: "BACK_TO_RESULTS" });
  }, [voiceCall]);

  const reset = useCallback(() => {
    cancelSpeech();
    if (callTimer.current) clearTimeout(callTimer.current);
    dispatch({ type: "RESET" });
  }, []);

  const setQuery = useCallback((q) => dispatch({ type: "SET_QUERY", query: q }), []);

  // ─── Key dispatch ────────────────────────────────────────────────────
  const handleKey = useCallback(
    (key) => {
      armIdleTimer();
      const s = stateRef.current;
      kioskApi.logEvent({ event_type: "keypress", session_id: undefined, payload: { key, screen: s.screen } });

      // Backspace: deletes a digit on the dial pad, otherwise acts as 0.
      if (key === "BS") {
        if (s.screen === SCREENS.ASK_HOME && s.tab === TABS.DIAL) {
          dispatch({ type: "DIAL_DELETE" });
          return;
        }
        if (s.screen === SCREENS.CALL_ACTIVE) return; // never hang up / DTMF via backspace
        key = "0";
      }

      // * = repeat / help on every screen — except during an active call,
      // where it must reach the far end as a DTMF tone.
      if (key === "*" && s.screen !== SCREENS.CALL_ACTIVE) {
        announce(describeScreen(s));
        return;
      }

      switch (s.screen) {
        case SCREENS.ASK_HOME: {
          // Dial tab: every digit (including 0) is part of the number.
          if (s.tab === TABS.DIAL) {
            if (/^[0-9]$/.test(key)) {
              dispatch({ type: "DIAL_APPEND", digit: key });
            } else if (key === "#") {
              dialCall();
            }
            return;
          }
          if (key === "0") {
            if (s.tab === TABS.BROWSE) {
              dispatch({ type: "SET_TAB", tab: TABS.ASK });
            } else if (s.query) {
              dispatch({ type: "SET_QUERY", query: "" });
            }
            return;
          }
          if (key === "#") {
            if (s.tab === TABS.ASK) runQuery(s.query);
            return;
          }
          const n = Number(key);
          if (n >= 1 && n <= 9) {
            // Digits drive the menu on the Browse tab, and act as quick
            // shortcuts on the Ask tab while the input is still empty.
            if (s.tab === TABS.BROWSE || !s.query.trim()) {
              selectMenuEntry(s.menu.find((m) => m.key === n));
            }
          }
          return;
        }

        case SCREENS.RESULTS_LIST: {
          if (key === "0") {
            dispatch({ type: "RESET" });
            return;
          }
          const n = Number(key);
          if (n >= 1 && n <= 9) {
            const item = s.items.find((it) => it.number === n);
            if (item) {
              dispatch({ type: "SELECT", item });
              announce(`${item.name}. ${item.description || ""}`);
            }
          }
          return;
        }

        case SCREENS.RESOURCE_DETAIL: {
          if (key === "0") {
            dispatch({ type: "BACK_TO_RESULTS" });
            return;
          }
          if (key === "#") {
            dispatch({ type: "CALL_CONFIRM", item: s.selected });
            announce(`Call ${s.selected?.name}? Press hash to confirm, or zero to cancel.`);
          }
          return;
        }

        case SCREENS.CALL_CONFIRM: {
          if (key === "0") {
            // Return to the resource detail when the call came from results;
            // otherwise (dial pad / 211 shortcut) go back home.
            if (s.items.some((it) => it === s.selected)) {
              dispatch({ type: "SELECT", item: s.selected });
            } else {
              dispatch({ type: "GO_HOME" });
            }
            return;
          }
          if (key === "#") {
            startCall(s.selected);
          }
          return;
        }

        case SCREENS.CALL_ACTIVE: {
          // During a live call every keypad press (including 0, * and #) is
          // forwarded to the far end as a DTMF tone so users can navigate IVR
          // menus and extensions. Hang-up is only triggered by the explicit
          // red End Call button (onHangUp prop), never by a keypad key.
          const live =
            !s.callSimulated && (s.callStatus === "connected" || s.callStatus === "in-progress");
          if (live) {
            if (/^[0-9*#]$/.test(key)) voiceCall.sendDigits(key);
            return;
          }
          // Not live (simulated, still connecting, failed, or ended): 0 backs
          // out — cancelling a connecting call or leaving a failure screen.
          if (key === "0") hangUp();
          return;
        }

        case SCREENS.EMPTY: {
          if (key === "0") {
            dispatch({ type: "RESET" });
            return;
          }
          if (key === "9" || key === "#") {
            // 211 fallback
            const item = s.fallback;
            if (item) {
              dispatch({ type: "CALL_CONFIRM", item });
              announce("Call the 211 help line? Press hash to confirm, or zero to cancel.");
            }
          }
          return;
        }

        case SCREENS.ERROR:
        case SCREENS.LOADING:
        default: {
          if (key === "0") dispatch({ type: "RESET" });
          return;
        }
      }
    },
    [announce, armIdleTimer, dialCall, hangUp, runQuery, selectMenuEntry, startCall],
  );

  return {
    state,
    handleKey,
    runQuery,
    setQuery,
    setTab,
    selectMenuEntry,
    dialCall,
    dialDelete,
    dialClear,
    startCall,
    hangUp,
    reset,
    describeScreen: () => describeScreen(stateRef.current),
  };
}
