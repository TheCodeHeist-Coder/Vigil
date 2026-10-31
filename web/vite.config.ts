import basicSsl from "@vitejs/plugin-basic-ssl";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// A phone's camera needs HTTPS, so the dev server uses a self-signed certificate.
const gateway = process.env.VIGIL_GATEWAY ?? "http://localhost:8100";

export default defineConfig({
  plugins: [react(), basicSsl()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": gateway,
      "/video": gateway,
      "/ws": { target: gateway, ws: true },
      "/webrtc": "http://localhost:8101",
    },
  },
});
