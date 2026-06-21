/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// A separate, minimal Vite config just for the test runner. We deliberately
// don't reuse vite.config.ts here: the main config pulls in TanStack Start
// SSR and nitro plugins which are unnecessary — and partly incompatible —
// with jsdom-based component tests. Tests mock @tanstack/react-router
// directly (see src/test/setup.ts) rather than exercising the real
// router/SSR pipeline.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
