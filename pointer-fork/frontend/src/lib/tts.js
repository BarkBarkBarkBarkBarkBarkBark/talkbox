// Minimal text-to-speech helper built on the Web Speech API. Used by the kiosk
// for the "* = repeat / help" command and short spoken confirmations. Safe to
// call in any browser: when speechSynthesis is unavailable it no-ops.
//
// M5 (text-to-speech milestone) expands this with volume control and a richer
// queue; for now it supports speak / cancel with a single utterance at a time.

function synth() {
  if (typeof window === "undefined") return null;
  return window.speechSynthesis || null;
}

export function speak(text) {
  const s = synth();
  if (!s || !text) return;
  try {
    s.cancel(); // never overlap utterances
    const u = new SpeechSynthesisUtterance(String(text));
    u.rate = 1.0;
    u.pitch = 1.0;
    u.lang = "en-US";
    s.speak(u);
  } catch {
    // ignore — speech is an enhancement, never required
  }
}

export function cancelSpeech() {
  const s = synth();
  if (!s) return;
  try {
    s.cancel();
  } catch {
    // ignore
  }
}

export function speechSupported() {
  return Boolean(synth());
}
