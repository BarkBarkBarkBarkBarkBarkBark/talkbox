import KioskShell from "../components/kiosk/KioskShell.jsx";

// Public demo surface — identical kiosk UX with an on-screen simulated keypad
// and a DEMO badge, so partners can try it from any browser with no hardware.
// Calling is always simulated here; no real number is ever dialed.
export default function DemoKioskPage() {
  return <KioskShell demo />;
}
