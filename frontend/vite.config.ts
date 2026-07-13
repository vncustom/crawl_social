import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8000" } },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.indexOf("node_modules/recharts") !== -1) return "charts";
          if (id.indexOf("node_modules/react") !== -1) return "react-vendor";
        },
      },
    },
  },
});
