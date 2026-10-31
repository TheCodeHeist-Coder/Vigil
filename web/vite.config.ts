import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Browsers allow the camera on http://localhost, so the laptop needs no certificate.
// A phone reaches this laptop by IP address, which needs HTTPS: run with VIGIL_HTTPS=1.
const gateway = process.env.VIGIL_GATEWAY ?? "http://localhost:8100";
const https = process.env.VIGIL_HTTPS === "1";

export default defineConfig({
  plugins: https ? [react(), basicSsl()] : [react()],
  server: {
    host: true,
    port: https ? 5174 : 5173,
    strictPort: true,
    proxy: {
      "/api": gateway,
      "/video": gateway,
      "/ws": { target: gateway, ws: true },
      "/webrtc": "http://localhost:8101",
    },
  },
});
