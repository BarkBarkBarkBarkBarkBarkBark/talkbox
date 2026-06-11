import { Outlet } from "react-router-dom";
import { AppHeader } from "./components/AppHeader.jsx";

export default function App() {
  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      <AppHeader />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
