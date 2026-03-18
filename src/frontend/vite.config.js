import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
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
