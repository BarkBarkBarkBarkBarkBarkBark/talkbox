import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        // Default to the compose backend (127.0.0.1:8085). Port 8000 is a
        // common collision on dev machines (other Docker stacks).
        target: process.env.VITE_API_URL || "http://127.0.0.1:8085",
        changeOrigin: true,
      },
    },
  },
});
