/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Vitest owns unit/component tests under src/; Playwright owns e2e/.
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
  },
});
