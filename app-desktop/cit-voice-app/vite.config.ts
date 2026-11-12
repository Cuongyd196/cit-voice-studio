import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],

  // `npm run dev` luôn ở cổng 1420: máy chủ cho phép gốc localhost:1420 (CORS và
  // kiểm tra Origin), đổi cổng thì giao diện dev không gọi được API.
  server: {
    port: 1420,
    strictPort: true,
  },

  // Shadcn UI
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
});
