import { computed, ref } from "vue";
import { requestRuntimeHealth, type RuntimeHealth } from "../services/planner";

type ServiceTagType = "success" | "warning" | "danger";
type RuntimeServiceStatus = {
  fastapi: string;
  deepseek: string;
  llmnesy: string;
  tavily: string;
};

export function useRuntimeHealth() {
  const health = ref<RuntimeHealth | null>(null);
  const error = ref("");
  const llmnesyReady = computed(() => Boolean(health.value?.database_ready || health.value?.sqlite_database_ready));

  const status = computed<RuntimeServiceStatus>(() => {
    if (error.value) {
      return {
        fastapi: "未连接",
        deepseek: "未配置",
        llmnesy: "未就绪",
        tavily: "关闭",
      };
    }
    if (!health.value) {
      return {
        fastapi: "检测中",
        deepseek: "检测中",
        llmnesy: "检测中",
        tavily: "检测中",
      };
    }
    return {
      fastapi: "运行中",
      deepseek: health.value.deepseek_key_configured ? "运行中" : "未配置",
      llmnesy: llmnesyReady.value ? "运行中" : "未就绪",
      tavily: health.value.tavily_real_time_enabled
        ? health.value.tavily_key_configured
          ? "运行中"
          : "未配置"
        : "关闭",
    };
  });

  function serviceType(label: string): ServiceTagType {
    if (label === "运行中") return "success";
    if (label === "检测中" || label === "关闭") return "warning";
    return "danger";
  }

  async function refresh() {
    error.value = "";
    try {
      health.value = await requestRuntimeHealth();
    } catch (err) {
      error.value = err instanceof Error ? err.message : "无法连接后端运行状态接口。";
    }
  }

  return { health, error, status, serviceType, refresh };
}
