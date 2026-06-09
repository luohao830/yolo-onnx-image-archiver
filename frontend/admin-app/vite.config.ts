import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig(() => {
  const base = process.env.VITE_BASE_PATH?.trim() || "/";

  return {
    base,
    plugins: [react()],
    server: {
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true
        }
      }
    },
    test: {
      environment: "jsdom"
    }
  };
});
