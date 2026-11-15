import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  // Same-origin API calls in development: the browser talks only to Vite, which forwards
  // /api and /health to FastAPI. This lets the SameSite=Strict refresh cookie work.
  const target = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      proxy: {
        "/api": { target, changeOrigin: false },
        "/health": { target, changeOrigin: false },
      },
    },
  };
});
