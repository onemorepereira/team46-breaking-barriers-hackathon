import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  build: { outDir: "../harness/web/static/workspace", emptyOutDir: true },
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": "http://127.0.0.1:8787",
      "/static": "http://127.0.0.1:8787",
      "/tiles": "http://127.0.0.1:8787",
      "/reports": "http://127.0.0.1:8787",
    },
  },
});
