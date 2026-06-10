import KioskShell from "../components/kiosk/KioskShell.jsx";

// Production kiosk surface. Keypad/keyboard-driven, no on-screen keypad, no
// login wall. Mounted at /kiosk outside the desktop App shell.
export default function KioskPage() {
  return <KioskShell demo={false} />;
}
