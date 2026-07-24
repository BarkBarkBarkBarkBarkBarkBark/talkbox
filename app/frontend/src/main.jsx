import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import App from "./App.jsx";
import { ThemeProvider } from "./lib/theme.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import DemoKioskPage from "./pages/DemoKioskPage.jsx";
import KioskPage from "./pages/KioskPage.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton theme="system" />
        <Routes>
          {/* Canonical public entrypoint: production kiosk surface, no desktop chrome. */}
          <Route path="/" element={<KioskPage />} />
          {/* Backward-compatible hardware/docs alias. It is the same production kiosk. */}
          <Route path="/kiosk" element={<KioskPage />} />
          {/* /demo → same kiosk with on-screen simulated keypad for browser demos. */}
          <Route path="/demo" element={<DemoKioskPage />} />
          {/* Secondary, superuser-only resource operations console. */}
          <Route path="/admin" element={<AdminPage />} />
          {/* /chat → desktop routing console (admin / partner use). */}
          <Route path="/chat" element={<App />}>
            <Route index element={<ChatPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
