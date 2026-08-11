import DemoChrome from "../components/marketing/DemoChrome.jsx";
import KioskShell from "../components/kiosk/KioskShell.jsx";

// Public demo surface — identical kiosk UX with an on-screen simulated keypad
// and a DEMO badge, so partners can try it from any browser with no hardware.
// Calling is always simulated here; no real number is ever dialed.
// Marketing chrome is a thin strip only; KioskShell is unchanged.
export default function DemoKioskPage() {
  return (
    <DemoChrome>
      <KioskShell demo />
    </DemoChrome>
  );
}
