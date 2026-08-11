import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import App from "./App.jsx";
import MarketingLayout from "./components/marketing/MarketingLayout.jsx";
import { ThemeProvider } from "./lib/theme.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import DemoKioskPage from "./pages/DemoKioskPage.jsx";
import DonatePage from "./pages/DonatePage.jsx";
import KioskPage from "./pages/KioskPage.jsx";
import MarketingSitePage from "./pages/MarketingSitePage.jsx";
import RootPage from "./pages/RootPage.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton theme="system" />
        <Routes>
          {/* Public web → marketing; local/appliance → production kiosk (no marketing chrome). */}
          <Route path="/" element={<RootPage />} />
          {/* Local preview of the public site while `/` stays kiosk on localhost. */}
          <Route element={<MarketingLayout />}>
            <Route path="/site" element={<MarketingSitePage />} />
            <Route path="/donate" element={<DonatePage />} />
          </Route>
          {/* Hardware-stable production kiosk (Pi Chromium default). */}
          <Route path="/kiosk" element={<KioskPage />} />
          {/* Simulated kiosk + thin marketing chrome; calls are never real. */}
          <Route path="/demo" element={<DemoKioskPage />} />
          {/* Secondary, superuser-only resource operations console. */}
          <Route path="/admin" element={<AdminPage />} />
          {/* Desktop routing console (admin / partner use). */}
          <Route path="/chat" element={<App />}>
            <Route index element={<ChatPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
