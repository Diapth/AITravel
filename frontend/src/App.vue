<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  BookOpen,
  BrainCircuit,
  ChevronDown,
  Compass,
  Landmark,
  Moon,
  Server,
  Sun,
} from "lucide-vue-next";
import PlannerComposer from "./components/PlannerComposer.vue";
import PlannerResults from "./components/PlannerResults.vue";
import { requestPlan, requestRuntimeHealth, type PlanRequest, type PlanResponse, type RuntimeHealth } from "./services/planner";

interface ProgressDay {
  day: number;
  status: "done" | "active" | "queued";
  title: string;
  detail: string;
}

const isGenerating = ref(false);
const response = ref<PlanResponse | null>(null);
const errorMessage = ref("");
const submittedPayload = ref<PlanRequest | null>(null);
const progressDays = ref<ProgressDay[]>([]);
const runtimeHealth = ref<RuntimeHealth | null>(null);
const healthError = ref("");
const isDarkTheme = ref(false);
const coachMenuOpen = ref(false);
const docsOpen = ref(false);
const selectedCoachMode = ref("旅行规划师");
const coachModes = ["轻松休闲", "高效紧凑", "亲子友好"];
let progressTimer: number | undefined;

const statusLabel = computed(() => {
  if (isGenerating.value) return "生成中";
  if (errorMessage.value) return "失败";
  if (response.value?.success) return "完成";
  return "待输入";
});

const statusMode = computed(() => {
  if (isGenerating.value) return "is-loading";
  if (errorMessage.value) return "is-error";
  if (response.value?.success) return "is-ok";
  return "";
});

const serviceStatus = computed(() => {
  if (healthError.value) {
    return {
      fastapi: "未连接",
      deepseek: "未配置",
      llmnesy: "未就绪",
    };
  }

  if (!runtimeHealth.value) {
    return {
      fastapi: "检测中",
      deepseek: "检测中",
      llmnesy: "检测中",
    };
  }

  return {
    fastapi: "运行中",
    deepseek: runtimeHealth.value.deepseek_key_configured ? "运行中" : "未配置",
    llmnesy: runtimeHealth.value.database_ready ? "运行中" : "未就绪",
  };
});

function serviceClass(label: string) {
  if (label === "运行中") return "is-running";
  if (label === "检测中") return "is-checking";
  return "is-offline";
}

function toggleTheme() {
  isDarkTheme.value = !isDarkTheme.value;
  document.documentElement.dataset.theme = isDarkTheme.value ? "dark" : "light";
  window.localStorage.setItem("chinatravel-theme", isDarkTheme.value ? "dark" : "light");
}

function openDocs() {
  docsOpen.value = !docsOpen.value;
}

function toggleCoachMenu() {
  coachMenuOpen.value = !coachMenuOpen.value;
}

function selectCoachMode(mode: string) {
  selectedCoachMode.value = mode;
  coachMenuOpen.value = false;
  window.localStorage.setItem("chinatravel-coach-mode", mode);
}

function inferDays(payload: PlanRequest) {
  return Math.min(Math.max(payload.days || 3, 1), 8);
}

function createProgress(payload: PlanRequest): ProgressDay[] {
  const totalDays = inferDays(payload);
  const destination = payload.target_city || "目的地";
  return [
    {
      day: 1,
      status: "active",
      title: "解析需求",
      detail: `正在整理 ${destination} ${totalDays} 天游的城市、预算、人数和偏好约束。`,
    },
    {
      day: 2,
      status: "queued",
      title: "检索交通与本地数据",
      detail: "LLMNeSy 正在匹配车次、景点、餐饮、住宿和预算约束。",
    },
    {
      day: 3,
      status: "queued",
      title: "生成并校验路线",
      detail: "DeepSeek 会参考结构化表格和商圈信息，生成更优行程。",
    },
    {
      day: 4,
      status: "queued",
      title: "等待完整结果",
      detail: "后端返回完整 plan 后，地图、Tab、预算和时间表会一次性出现。",
    },
  ];
}

function advanceProgress() {
  const currentIndex = progressDays.value.findIndex((stage) => stage.status === "active");
  if (currentIndex === -1) return;
  const lastIndex = progressDays.value.length - 1;

  progressDays.value = progressDays.value.map((stage, index) => {
    if (index < currentIndex) return { ...stage, status: "done" };
    if (index === currentIndex) {
      return {
        ...stage,
        status: "done",
      };
    }
    if (index === currentIndex + 1 && currentIndex < lastIndex) {
      return {
        ...stage,
        status: "active",
      };
    }
    return stage;
  });
}

function startProgress(payload: PlanRequest) {
  window.clearInterval(progressTimer);
  progressDays.value = createProgress(payload);
  progressTimer = window.setInterval(advanceProgress, 12000);
}

function stopProgress() {
  window.clearInterval(progressTimer);
  progressTimer = undefined;
}

async function handleSubmit(payload: PlanRequest) {
  submittedPayload.value = payload;
  response.value = null;
  errorMessage.value = "";
  isGenerating.value = true;
  startProgress(payload);

  try {
    const data = await requestPlan(payload);
    response.value = data;
    if (!data.success) {
      errorMessage.value = data.error?.message || "生成失败，请检查后端配置。";
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "请求失败，请稍后重试。";
    response.value = {
      success: false,
      error: {
        code: "REQUEST_FAILED",
        message: errorMessage.value,
      },
    };
  } finally {
    isGenerating.value = false;
    stopProgress();
    progressDays.value = progressDays.value.map((day) => ({
      ...day,
      status: response.value?.success ? "done" : day.status,
      title: response.value?.success && day.title === "等待完整结果" ? "结果已返回" : day.title,
    }));
  }
}

async function refreshRuntimeHealth() {
  healthError.value = "";
  try {
    runtimeHealth.value = await requestRuntimeHealth();
  } catch (error) {
    healthError.value = error instanceof Error ? error.message : "无法连接后端运行状态接口。";
  }
}

onMounted(() => {
  const storedTheme = window.localStorage.getItem("chinatravel-theme");
  const storedCoachMode = window.localStorage.getItem("chinatravel-coach-mode");
  isDarkTheme.value = storedTheme === "dark";
  if (storedCoachMode) selectedCoachMode.value = storedCoachMode;
  document.documentElement.dataset.theme = isDarkTheme.value ? "dark" : "light";
  void refreshRuntimeHealth();
});
onBeforeUnmount(stopProgress);
</script>

<template>
  <main class="app-shell">
    <header class="app-header">
      <div class="brand-lockup">
        <div class="brand-mark" aria-hidden="true">
          <Landmark :size="34" stroke-width="2.1" />
        </div>
        <div>
          <h1><span>ChinaTravel</span> Planner</h1>
          <p>旅行规划工作台</p>
        </div>
      </div>

      <div class="header-meta" aria-label="运行组件">
        <div class="service-strip">
          <span class="status-chip" :class="serviceClass(serviceStatus.fastapi)">
            <i /> <Server :size="15" /> FastAPI <b>{{ serviceStatus.fastapi }}</b>
          </span>
          <span class="status-chip" :class="serviceClass(serviceStatus.deepseek)">
            <i /> <BrainCircuit :size="15" /> DeepSeek <b>{{ serviceStatus.deepseek }}</b>
          </span>
          <span class="status-chip" :class="serviceClass(serviceStatus.llmnesy)">
            <i /> <Compass :size="15" /> LLMNeSy <b>{{ serviceStatus.llmnesy }}</b>
          </span>
        </div>
        <button class="icon-button" type="button" aria-label="切换主题" @click="toggleTheme">
          <Sun v-if="!isDarkTheme" :size="20" />
          <Moon v-else :size="20" />
        </button>
        <div class="docs-wrap">
          <button class="icon-button" type="button" aria-label="查看手册" @click="openDocs"><BookOpen :size="20" /></button>
          <div v-if="docsOpen" class="docs-popover" role="dialog" aria-label="接口说明">
            <b>接口说明</b>
            <span>页面由 Vue 构建，FastAPI 负责静态托管。</span>
            <code>POST /api/plan</code>
            <code>GET /api/health</code>
          </div>
        </div>
        <div class="coach-menu-wrap">
          <button class="coach-button" type="button" @click="toggleCoachMenu">
            <Moon :size="18" />
            <span>{{ selectedCoachMode }}</span>
            <ChevronDown :size="15" :class="{ rotated: coachMenuOpen }" />
          </button>
          <div v-if="coachMenuOpen" class="coach-menu" role="menu">
            <button v-for="mode in coachModes" :key="mode" type="button" role="menuitem" @click="selectCoachMode(mode)">
              {{ mode }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <section class="workspace-grid">
      <PlannerComposer :disabled="isGenerating" :runtime-health="runtimeHealth" @submit-plan="handleSubmit" />
      <PlannerResults
        :is-generating="isGenerating"
        :status-label="statusLabel"
        :status-mode="statusMode"
        :payload="submittedPayload"
        :response="response"
        :error-message="errorMessage"
        :progress-days="progressDays"
      />
    </section>
  </main>
</template>
