import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // Stylesheets are blanked in tests, except the app's own, which styles.test.ts reads as text.
    css: { include: /src\/styles\.css/ },
  },
});
