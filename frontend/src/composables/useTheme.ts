import { ref } from "vue";

type AppTheme = "light" | "dark";

export function useTheme() {
  const isDark = ref(false);

  function applyTheme(theme: AppTheme) {
    isDark.value = theme === "dark";
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle("dark", isDark.value);
  }

  function toggle() {
    const nextTheme = isDark.value ? "light" : "dark";
    applyTheme(nextTheme);
    window.localStorage.setItem("chinatravel-theme", nextTheme);
  }

  function restore() {
    const storedTheme = window.localStorage.getItem("chinatravel-theme");
    applyTheme(storedTheme === "dark" ? "dark" : "light");
  }

  return { isDark, applyTheme, toggle, restore };
}
