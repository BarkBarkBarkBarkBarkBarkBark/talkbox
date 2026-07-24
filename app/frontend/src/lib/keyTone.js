// Plays a short, pleasant sine-wave beep for each kiosk keypress using the
// Web Audio API. No external assets needed — tones are synthesised on the fly.
//
// Each call creates its own AudioContext node so tones can overlap without
// cutting each other off. The context is closed automatically after the note
// finishes to avoid leaving handles open.

const TONES = {
  "1": 830, "2": 830, "3": 830,
  "4": 830, "5": 830, "6": 830,
  "7": 830, "8": 830, "9": 830,
  "0":  660,  // back / home — lower, softer
  "*":  740,  // voice / help — mid
  "#":  987,  // confirm / submit — bright
  "BS": 554,  // delete — low
  "CALL":   987,
  "HANGUP": 440,
};

const DURATION   = 0.09;   // seconds total note length
const ATTACK     = 0.005;  // fade-in time
const DECAY      = 0.07;   // fade-out time
const PEAK_GAIN  = 0.18;   // keep it subtle, not jarring

export function playKeyTone(key) {
  const freq = TONES[key];
  if (!freq) return;

  let ctx;
  try {
    ctx = new AudioContext();
  } catch {
    return; // browser doesn't support Web Audio
  }

  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();

  osc.type = "sine";
  osc.frequency.setValueAtTime(freq, now);

  // Slight pitch slide down gives a warmer, less harsh feel
  osc.frequency.exponentialRampToValueAtTime(freq * 0.92, now + DURATION);

  gain.gain.setValueAtTime(0, now);
  gain.gain.linearRampToValueAtTime(PEAK_GAIN, now + ATTACK);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + ATTACK + DECAY);

  osc.connect(gain);
  gain.connect(ctx.destination);

  osc.start(now);
  osc.stop(now + DURATION);

  osc.onended = () => ctx.close();
}

// Louder two-note chime for the "are you still there?" call-presence warning.
// Deliberately distinct from keypress beeps so it reads as an alert, and loud
// enough to be heard by someone standing a step away from the kiosk.
export function playAlertTone() {
  let ctx;
  try {
    ctx = new AudioContext();
  } catch {
    return;
  }
  const now = ctx.currentTime;
  [[880, 0], [660, 0.18]].forEach(([freq, at]) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, now + at);
    gain.gain.setValueAtTime(0, now + at);
    gain.gain.linearRampToValueAtTime(0.4, now + at + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.16);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now + at);
    osc.stop(now + at + 0.17);
  });
  setTimeout(() => ctx.close().catch(() => {}), 600);
}
