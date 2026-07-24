import { useCallback, useEffect, useReducer, useRef } from "react";
import { kioskApi } from "../lib/kioskApi.js";
import { playAlertTone } from "../lib/keyTone.js";
import { cancelSpeech, speak } from "../lib/tts.js";
import { useKioskVoiceCall } from "./useKioskVoiceCall.js";
import { useVoiceSearch } from "./useVoiceSearch.js";

// Deterministic kiosk navigation driven entirely by the 12-key vocabulary
// ("1".."9", "0", "*", "#"). The same machine backs the physical ATM keypad,
// a laptop keyboard, and the on-screen simulated keypad.
//
// The home surface is chat-first (chat-first): an open-ended
// "what do you need?" input is the primary screen, with a Browse tab that
// lists the numbered category menu for keypad-only users.
//
// Screens:
//   ASK_HOME        chat-first home; ask tab = free-text input, browse tab = menu
//   LOADING         awaiting backend
//   RESULTS_LIST    numbered resources, press N to select
//   RESOURCE_DETAIL one focused resource, # to call
//   CALL_CONFIRM    confirm before dialing (no arbitrary dialing)
//   CALL_ACTIVE     simulated/active call, Backspace to hang up
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

const TAB_ORDER = [TABS.ASK, TABS.BROWSE, TABS.DIAL];

function nextTab(tab) {
  const i = TAB_ORDER.indexOf(tab);
  return TAB_ORDER[(i + 1) % TAB_ORDER.length];
}

function describeTab(tab) {
  if (tab === TABS.BROWSE)
    return "Browse menu. Use minus and plus to move, Enter to open.";
  if (tab === TABS.DIAL)
    return "Dial pad. Enter a phone number, then press Enter to call.";
  return "Ask. Press star to speak, or press 9 to call 211.";
}

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
  cursor: 0,
  items: [],
  fallback: null,
  selected: null,
  spokenSummary: "",
  error: null,
  callStatus: "idle", // idle | connecting | connected | ended | failed
  callSimulated: true,
  callReason: null,
  // "Are you still there?" warning level during a live call: 0 (none), 1, 2.
  callAttention: 0,
};

function reducer(state, action) {
  switch (action.type) {
    case "CONFIG_LOADED":
      return { ...state, config: action.config, menu: action.config.menu || [] };
    case "SET_QUERY":
      return { ...state, query: action.query };
    case "SET_TAB":
      return { ...state, screen: SCREENS.ASK_HOME, tab: action.tab, cursor: 0, error: null };
    case "MOVE_CURSOR": {
      const len = action.length;
      if (!len || len <= 0) return state;
      let next = state.cursor + action.delta;
      if (next < 0) next = 0;
      if (next > len - 1) next = len - 1;
      if (next === state.cursor) return state;
      return { ...state, cursor: next };
    }
    case "GO_HOME":
      return { ...state, screen: SCREENS.ASK_HOME, callStatus: "idle", callAttention: 0, error: null };
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
        cursor: 0,
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
    case "CALL_ATTENTION":
      return { ...state, callAttention: action.level };
    case "BACK_TO_RESULTS":
      // From a dial-pad or 211 call there may be no results to return to.
      return {
        ...state,
        screen: state.items.length ? SCREENS.RESULTS_LIST : SCREENS.ASK_HOME,
        callStatus: "idle",
        callAttention: 0,
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
        return describeTab(TABS.BROWSE);
      if (state.tab === TABS.DIAL)
        return describeTab(TABS.DIAL);
      return describeTab(TABS.ASK);
    case SCREENS.RESULTS_LIST:
      return (
        state.spokenSummary ||
        "Here are your results. Press a number to choose one, or use minus and plus to move and Enter to open."
      );
    case SCREENS.RESOURCE_DETAIL: {
      const s = state.selected;
      if (!s) return "No resource selected.";
      return `${s.name}. ${s.description || ""} Press Enter to call, or Backspace to go back.`;
    }
    case SCREENS.CALL_CONFIRM:
      return `Call ${state.selected?.name || "this resource"}? Press Enter to confirm, or Backspace to cancel.`;
    case SCREENS.CALL_ACTIVE:
      return "Call in progress. Use the keypad for phone menus. Press Backspace to end the call.";
    case SCREENS.EMPTY:
      return state.spokenSummary || "No match found. You can call 211 for help.";
    case SCREENS.ERROR:
      return "Something went wrong. Press Back to return to the menu.";
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
  const pendingDtmf = useRef("");

  const speechEnabled = state.config?.speech_enabled ?? true;
  const voice = useVoiceSearch({
    enabled: speechEnabled,
    maxSeconds: state.config?.speech_max_seconds || 6,
  });

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
        if (sdkStatus === "failed") {
          kioskApi.logEvent({
            event_type: "call_error",
            payload: { reason: reason || "unknown" },
          });
        }
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

  // If a caller starts entering extension digits before the call is fully
  // connected, hold them briefly and send once Twilio reports a live call.
  useEffect(() => {
    const live =
      state.screen === SCREENS.CALL_ACTIVE &&
      !state.callSimulated &&
      (state.callStatus === "connected" || state.callStatus === "in-progress");
    if (!live || !pendingDtmf.current) return;
    voiceCall.sendDigits(pendingDtmf.current);
    pendingDtmf.current = "";
  }, [state.screen, state.callSimulated, state.callStatus, voiceCall]);

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
        announce("Something went wrong. Press Back to return to the menu.");
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
        announce("Call the 211 help line? Press Enter to confirm.");
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
    announce(`Call ${formatDialed(digits)}? Press Enter to confirm, or Backspace to cancel.`);
  }, [announce, armIdleTimer]);

  const startCall = useCallback(
    (item) => {
      const target = item || stateRef.current.selected;
      if (!target) return;
      const callingDisabled = stateRef.current.config?.calling_enabled === false;
      const simulated = fakeCall || callingDisabled || !target.phone;
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
    pendingDtmf.current = "";
    cancelSpeech();
    voiceCall.hangUp();
    kioskApi.logEvent({ event_type: "call_end" });
    dispatch({ type: "BACK_TO_RESULTS" });
  }, [voiceCall]);

  // ─── In-call presence watchdog ("are you still there?") ─────────────
  // A caller who walks away mid-hold would otherwise tie up the kiosk (and
  // the far-end line) indefinitely. After a period with no keypad activity
  // during a live call, beep + show a warning; a second warning follows, and
  // then the call is ended. Tab (STILL_HERE) or any key confirms presence.
  const presenceTimer = useRef(null);

  const clearPresenceTimer = useCallback(() => {
    if (presenceTimer.current) {
      clearTimeout(presenceTimer.current);
      presenceTimer.current = null;
    }
  }, []);

  const raisePresenceWarning = useCallback(
    (level) => {
      if (stateRef.current.screen !== SCREENS.CALL_ACTIVE) return;
      if (level > 2) {
        kioskApi.logEvent({
          event_type: "call_auto_hangup",
          payload: { reason: "unattended" },
        });
        hangUp();
        dispatch({ type: "RESET" });
        return;
      }
      playAlertTone();
      dispatch({ type: "CALL_ATTENTION", level });
      kioskApi.logEvent({ event_type: "call_presence_warning", payload: { level } });
      presenceTimer.current = setTimeout(() => raisePresenceWarning(level + 1), 45_000);
    },
    [hangUp],
  );

  const armPresenceTimer = useCallback(() => {
    clearPresenceTimer();
    if (stateRef.current.screen !== SCREENS.CALL_ACTIVE) return;
    if (stateRef.current.callAttention) dispatch({ type: "CALL_ATTENTION", level: 0 });
    const warnSecs = stateRef.current.config?.call_idle_warn_seconds || 300;
    presenceTimer.current = setTimeout(() => raisePresenceWarning(1), warnSecs * 1000);
  }, [clearPresenceTimer, raisePresenceWarning]);

  useEffect(() => {
    if (state.screen === SCREENS.CALL_ACTIVE) armPresenceTimer();
    else clearPresenceTimer();
    return clearPresenceTimer;
  }, [state.screen, armPresenceTimer, clearPresenceTimer]);

  const reset = useCallback(() => {
    cancelSpeech();
    if (callTimer.current) clearTimeout(callTimer.current);
    dispatch({ type: "RESET" });
  }, []);

  const setQuery = useCallback((q) => dispatch({ type: "SET_QUERY", query: q }), []);

  const runVoiceSearch = useCallback(async () => {
    if (!speechEnabled) {
      announce("Speech search is not available.");
      return;
    }
    cancelSpeech();
    armIdleTimer();
    announce("Listening.");
    const transcript = await voice.startVoiceSearch();
    if (!transcript) {
      announce("I couldn't hear that. Press star and try again.");
      return;
    }
    dispatch({ type: "SET_QUERY", query: transcript });
    announce("Searching.");
    runQuery(transcript);
  }, [announce, armIdleTimer, runQuery, speechEnabled, voice]);

  // ─── Key dispatch ────────────────────────────────────────────────────
  const handleKey = useCallback(
    (key) => {
      armIdleTimer();
      const s = stateRef.current;
      // Any key during a live call proves someone is present.
      if (s.screen === SCREENS.CALL_ACTIVE) armPresenceTimer();
      kioskApi.logEvent({ event_type: "keypress", session_id: undefined, payload: { key, screen: s.screen } });

      // STILL_HERE (Tab / screen tap): exists only to answer the "are you
      // still there?" prompt — it must never dial, navigate, or send DTMF.
      if (key === "STILL_HERE") return;

      // Backspace: on the dial pad deletes a digit; during a call ends the call;
      // otherwise steps back one screen. 0 is always just the number 0.
      if (key === "BS") {
        if (s.screen === SCREENS.ASK_HOME && s.tab === TABS.DIAL) {
          dispatch({ type: "DIAL_DELETE" });
          return;
        }
        if (s.screen === SCREENS.CALL_ACTIVE) {
          hangUp();
          return;
        }
        // Fall through: each screen below handles "BS" as a safe step-back.
      }

      // HANGUP: the dedicated red button (touch today, physical later). The
      // only way to end a live call — keypad keys never hang up.
      if (key === "HANGUP") {
        if (s.screen === SCREENS.CALL_ACTIVE) {
          hangUp();
        } else if (s.screen === SCREENS.CALL_CONFIRM) {
          handleKey("BS"); // cancel the pending call
        }
        return;
      }

      // CALL_211: the dedicated physical "Call 211" button. One press reaches
      // the 211 help line from any screen, except an already-active call (so it
      // can never interrupt a call in progress). 211 is a fixed, safe number,
      // so it dials directly without a separate confirm step.
      if (key === "CALL_211") {
        if (s.screen === SCREENS.CALL_ACTIVE) return;
        const item = s.fallback || {
          name: "211 help line",
          phone: "+19164981000",
          phone_display: "211 (help line)",
        };
        startCall(item);
        return;
      }

      // CALL: the dedicated green button. Context-aware: confirms a pending
      // call, dials the entered number, calls the focused resource, or — from
      // the home screen — starts the Call 211 flow.
      if (key === "CALL") {
        switch (s.screen) {
          case SCREENS.CALL_CONFIRM:
            startCall(s.selected);
            return;
          case SCREENS.RESOURCE_DETAIL:
            dispatch({ type: "CALL_CONFIRM", item: s.selected });
            announce(`Call ${s.selected?.name}? Press Enter to confirm.`);
            return;
          case SCREENS.EMPTY:
            handleKey("9"); // 211 fallback confirm
            return;
          case SCREENS.ASK_HOME:
            if (s.tab === TABS.DIAL) {
              dialCall();
            } else {
              selectMenuEntry(
                s.menu.find((m) => m.action === "CALL_211") || {
                  action: "CALL_211",
                },
              );
            }
            return;
          default:
            return;
        }
      }

      // CYCLE_TAB / DIAL: "/" cycles home tabs (Ask → Browse → Dial); "."
      // jumps straight to Dial. Inert during a live call.
      if (key === "CYCLE_TAB" && s.screen !== SCREENS.CALL_ACTIVE) {
        if (s.screen !== SCREENS.ASK_HOME) {
          dispatch({ type: "RESET" });
          announce(describeTab(TABS.ASK));
          return;
        }
        const tab = nextTab(s.tab);
        setTab(tab);
        announce(describeTab(tab));
        return;
      }
      if (key === "DIAL" && s.screen !== SCREENS.CALL_ACTIVE) {
        if (s.screen !== SCREENS.ASK_HOME) dispatch({ type: "GO_HOME" });
        setTab(TABS.DIAL);
        announce(describeTab(TABS.DIAL));
        return;
      }

      // PREV / NEXT (numpad "-" / "+"): move the highlight through whatever
      // list is on screen. Inert when there's nothing to scroll.
      if (key === "PREV" || key === "NEXT") {
        const delta = key === "NEXT" ? 1 : -1;
        let list = null;
        if (s.screen === SCREENS.ASK_HOME && s.tab === TABS.BROWSE) list = s.menu;
        else if (s.screen === SCREENS.RESULTS_LIST) list = s.items;
        if (list && list.length) {
          dispatch({ type: "MOVE_CURSOR", delta, length: list.length });
          let idx = s.cursor + delta;
          if (idx < 0) idx = 0;
          if (idx > list.length - 1) idx = list.length - 1;
          const item = list[idx];
          if (item) announce(item.label || item.name || "");
        }
        return;
      }

      // * = Talk: only on the Ask tab (never starts recording when browsing
      // other tabs). Everywhere else on non-call screens it reads aloud.
      if (
        key === "*" &&
        s.screen === SCREENS.ASK_HOME &&
        s.tab === TABS.ASK &&
        voice.voiceStatus !== "requesting-permission" &&
        voice.voiceStatus !== "listening" &&
        voice.voiceStatus !== "transcribing"
      ) {
        runVoiceSearch();
        return;
      }
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
          if (key === "BS") {
            if (s.tab === TABS.BROWSE) {
              dispatch({ type: "SET_TAB", tab: TABS.ASK });
            }
            return;
          }
          if (key === "#") {
            // OK / Enter on the Browse tab opens the highlighted category.
            if (s.tab === TABS.BROWSE) selectMenuEntry(s.menu[s.cursor]);
            return;
          }
          const n = Number(key);
          if (n >= 1 && n <= 9) {
            if (n === 9) {
              // 9 always reaches 211 — even if the menu config failed to load,
              // selectMenuEntry falls back to the built-in 211 help line.
              selectMenuEntry(
                s.menu.find((m) => m.action === "CALL_211") || { action: "CALL_211" },
              );
              return;
            }
            // Digits jump straight to a numbered menu entry. This keeps the
            // beloved "press 9 to call 211" shortcut working on the Ask tab,
            // and drives the numbered categories on the Browse tab.
            selectMenuEntry(
              s.menu.find((m) => Number(m.key) === n || String(m.key) === String(n)),
            );
          }
          return;
        }

        case SCREENS.RESULTS_LIST: {
          if (key === "BS") {
            dispatch({ type: "RESET" });
            return;
          }
          if (key === "#") {
            // OK / Enter opens the highlighted resource.
            const item = s.items[s.cursor];
            if (item) {
              dispatch({ type: "SELECT", item });
              announce(`${item.name}. ${item.description || ""}`);
            }
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
          if (key === "BS") {
            dispatch({ type: "BACK_TO_RESULTS" });
            return;
          }
          if (key === "#") {
            dispatch({ type: "CALL_CONFIRM", item: s.selected });
            announce(`Call ${s.selected?.name}? Press Enter to confirm, or Backspace to cancel.`);
          }
          return;
        }

        case SCREENS.CALL_CONFIRM: {
          if (key === "BS") {
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
          // Live call: digits, * and # go to the far end as DTMF. End call via
          // Backspace only (handled above) — Enter stays available for IVR menus.
          if (!/^[0-9*#]$/.test(key) || s.callSimulated) return;
          const live = s.callStatus === "connected" || s.callStatus === "in-progress";
          if (live) {
            voiceCall.sendDigits(key);
          } else {
            pendingDtmf.current += key;
          }
          return;
        }

        case SCREENS.EMPTY: {
          if (key === "BS") {
            dispatch({ type: "RESET" });
            return;
          }
          if (key === "9" || key === "#") {
            // 211 fallback
            const item = s.fallback;
            if (item) {
              dispatch({ type: "CALL_CONFIRM", item });
              announce("Call the 211 help line? Press Enter to confirm.");
            }
          }
          return;
        }

        case SCREENS.ERROR:
        case SCREENS.LOADING:
        default: {
          if (key === "BS") dispatch({ type: "RESET" });
          return;
        }
      }
    },
    [
      announce,
      armIdleTimer,
      armPresenceTimer,
      dialCall,
      hangUp,
      runQuery,
      runVoiceSearch,
      selectMenuEntry,
      setTab,
      startCall,
      voice.voiceStatus,
    ],
  );

  return {
    state: {
      ...state,
      voiceStatus: voice.voiceStatus,
      voiceError: voice.voiceError,
      lastTranscript: voice.lastTranscript,
      speechEnabled,
    },
    handleKey,
    runQuery,
    runVoiceSearch,
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
