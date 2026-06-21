import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import tsconfigPaths from "vite-tsconfig-paths";

// Standard TanStack Start vite config.
// tanstackStart() internally includes TanStackRouterVite (file-based routing),
// the nitro server bundler, SSR transforms, and VITE_* env injection —
// so those do NOT need to be added separately.
export default defineConfig({
  plugins: [
    tanstackStart({
      // Points to src/server.ts — the SSR error-wrapper entry that was
      // previously configured via the tanstackStart.server.entry option
      // passed to the Lovable defineConfig wrapper.
      server: { entry: "server" },
    }),
    react(),
    tailwindcss(),
    tsconfigPaths(),
  ],
  server: {
    port: 5173,
    host: true, // expose to Docker host
  },
});
