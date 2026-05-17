import { computed, ref, type Ref } from "vue";

type MobilePanel = "history" | "chat" | "recommendations" | "versions" | "plan";
type AppMode = "empty_chat" | "plan_workspace";

export function useMobilePanel(appMode: Ref<AppMode>) {
  const panel = ref<MobilePanel>("chat");

  const tabs = computed(() => mobileTabsForMode(appMode.value));

  function switchPanel(p: MobilePanel) {
    panel.value = p;
  }

  return { panel, tabs, switchPanel };
}

export function mobileTabsForMode(appMode: AppMode): Array<{ id: MobilePanel; label: string }> {
  if (appMode === "empty_chat") {
    return [
      { id: "history", label: "历史" },
      { id: "chat", label: "聊天" },
      { id: "recommendations", label: "推荐" },
    ];
  }
  return [
    { id: "history", label: "历史" },
    { id: "chat", label: "聊天" },
    { id: "versions", label: "版本" },
    { id: "plan", label: "行程" },
  ];
}

export type { MobilePanel };
