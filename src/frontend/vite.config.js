import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { readFileSync } from "fs";

const pkg = JSON.parse(readFileSync("package.json", "utf-8"));

export default defineConfig({
  plugins: [vue()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  base: process.env.VITE_BASE_PATH || "/",
  server: {
    host: true,
    // Uncomment to use Vite dev server with API proxy instead of build-watch workflow:
    // proxy: {
    //   "/api": {
    //     target: "http://localhost:8000",
    //     changeOrigin: true,
    //   },
    // },
  },
  build: {
    outDir: "dist",
  },
});
