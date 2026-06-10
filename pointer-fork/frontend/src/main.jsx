import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";

import App from "./App.jsx";
import { ThemeProvider } from "./lib/theme.jsx";
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
          {/* Kiosk surfaces: no desktop chrome (kiosk principle). */}
          <Route path="/kiosk" element={<KioskPage />} />
          <Route path="/demo" element={<DemoKioskPage />} />
          <Route path="/" element={<App />}>
            <Route index element={<ChatPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>,
);
