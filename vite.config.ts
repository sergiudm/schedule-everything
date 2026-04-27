import { defineConfig } from "vitest/config";

export default defineConfig({
  root: "desktop",
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true
  },
  build: {
    outDir: "../dist",
    emptyOutDir: true
  },
  test: {
    environment: "jsdom",
    include: ["desktop/src/**/*.test.ts"]
  }
});
