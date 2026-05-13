import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: "frontend",
    emptyOutDir: false,
    assetsDir: "assets",
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ["vue"],
          element: ["element-plus", "@element-plus/icons-vue"],
          lucide: ["lucide-vue-next"],
        },
      },
    },
  },
});
