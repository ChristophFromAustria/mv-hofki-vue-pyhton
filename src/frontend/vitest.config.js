import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";

const nm = resolve(__dirname, "node_modules");

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@vue/test-utils": resolve(nm, "@vue/test-utils"),
      "vue-router": resolve(nm, "vue-router"),
      vue: resolve(nm, "vue"),
      vitest: resolve(nm, "vitest"),
    },
  },
  server: {
    fs: {
      allow: [resolve(__dirname, "../.."), resolve(__dirname)],
    },
  },
  test: {
    environment: "jsdom",
    root: resolve(__dirname, "../.."),
    include: ["tests/frontend/**/*.{test,spec}.{js,ts}"],
  },
});
