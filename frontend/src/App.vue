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
import ConversationSidebar from "./components/ConversationSidebar.vue";
import PlanVersionTimeline from "./components/PlanVersionTimeline.vue";
import PlanWorkspace from "./components/PlanWorkspace.vue";
import PlannerComposer from "./components/PlannerComposer.vue";
import PlannerResults from "./components/PlannerResults.vue";
import RecommendedPlans from "./components/RecommendedPlans.vue";
import TravelChatPanel from "./components/TravelChatPanel.vue";
import {
  archiveConversation,
  createConversation,
  openRecommendedPlan,
  requestConversationDetail,
  requestConversations,
  requestPlan,
  requestRecommendedPlans,
  requestRuntimeHealth,
  restoreConversation,
  restorePlanVersion,
  saveManualPlanEdit,
  sendConversationMessage,
  type ConversationDetailResponse,
  type ConversationMessage,
  type ConversationSummary,
  type PlanRequest,
  type PlanResponse,
  type PlanVersionSummary,
  type RecommendationItem,
  type RuntimeHealth,
  type TravelPlan,
} from "./services/planner";

type AppMode = "empty_chat" | "plan_workspace";

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
const appMode = ref<AppMode>("empty_chat");
const conversations = ref<ConversationSummary[]>([]);
const recommendedPlans = ref<RecommendationItem[]>([]);
const messages = ref<ConversationMessage[]>([]);
const versions = ref<PlanVersionSummary[]>([]);
const currentConversation = ref<ConversationSummary | null>(null);
const currentPlan = ref<TravelPlan | null>(null);
const isConversationLoading = ref(false);
const isRecommendationLoading = ref(false);
const isChatBusy = ref(false);
const chatErrorMessage = ref("");
const workspaceNotice = ref("");
let progressTimer: number | undefined;

const currentVersionId = computed(() => currentConversation.value?.current_version_id || null);

const statusLabel = computed(() => {
  if (isGenerating.value || isChatBusy.value) return "生成中";
  if (errorMessage.value || chatErrorMessage.value) return "失败";
  if (response.value?.success || currentPlan.value) return "完成";
  return "待输入";
});

const statusMode = computed(() => {
  if (isGenerating.value || isChatBusy.value) return "is-loading";
  if (errorMessage.value || chatErrorMessage.value) return "is-error";
  if (response.value?.success || currentPlan.value) return "is-ok";
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

function applyConversationDetail(detail: ConversationDetailResponse) {
  if (!detail.success) {
    chatErrorMessage.value = detail.error?.message || "会话读取失败，请稍后重试。";
    return;
  }
  currentConversation.value = detail.conversation || null;
  messages.value = detail.messages || [];
  versions.value = detail.versions || [];
  currentPlan.value = detail.current_plan || null;
  response.value = detail.current_plan ? { success: true, plan: detail.current_plan } : null;
  submittedPayload.value = detail.current_plan
    ? {
        query: detail.conversation?.title || "已保存行程",
        start_city: detail.current_plan.start_city,
        target_city: detail.current_plan.target_city,
        target_cities: detail.current_plan.target_cities,
        departure_date: detail.current_plan.departure_date,
        return_date: detail.current_plan.return_date,
        days: detail.current_plan.days,
        people_number: detail.current_plan.people_number,
        budget: detail.current_plan.budget,
      }
    : null;
  appMode.value = detail.current_plan ? "plan_workspace" : "empty_chat";
}

async function refreshConversationList() {
  isConversationLoading.value = true;
  try {
    const data = await requestConversations();
    if (data.success) conversations.value = data.conversations;
  } finally {
    isConversationLoading.value = false;
  }
}

async function refreshRecommendations() {
  isRecommendationLoading.value = true;
  try {
    const data = await requestRecommendedPlans();
    if (data.success) recommendedPlans.value = data.recommendations;
  } finally {
    isRecommendationLoading.value = false;
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

async function handleChatMessage(message: string) {
  chatErrorMessage.value = "";
  workspaceNotice.value = "";
  isChatBusy.value = true;
  startProgress({ query: message });
  try {
    const detail = currentConversation.value
      ? await sendConversationMessage(currentConversation.value.id, message, { base_version_id: currentConversation.value.current_version_id })
      : await createConversation(message);

    if (!detail.success) {
      chatErrorMessage.value = detail.error?.message || "发送失败，请稍后重试。";
      if ("message" in detail && detail.message) messages.value = [...messages.value, detail.message];
      return;
    }

    if ("versions" in detail) {
      applyConversationDetail(detail);
    } else if (currentConversation.value) {
      const refreshed = await requestConversationDetail(currentConversation.value.id);
      applyConversationDetail(refreshed);
    }
    await refreshConversationList();
  } finally {
    isChatBusy.value = false;
    stopProgress();
    progressDays.value = progressDays.value.map((day) => ({
      ...day,
      status: currentPlan.value ? "done" : day.status,
      title: currentPlan.value && day.title === "等待完整结果" ? "结果已返回" : day.title,
    }));
  }
}

async function handleSelectConversation(conversationId: string) {
  chatErrorMessage.value = "";
  isConversationLoading.value = true;
  try {
    applyConversationDetail(await requestConversationDetail(conversationId));
  } finally {
    isConversationLoading.value = false;
  }
}

async function handleOpenRecommendation(recommendationId: string) {
  chatErrorMessage.value = "";
  isChatBusy.value = true;
  try {
    applyConversationDetail(await openRecommendedPlan(recommendationId));
    await refreshConversationList();
  } finally {
    isChatBusy.value = false;
  }
}

async function handleArchiveConversation(conversationId: string) {
  const detail = await archiveConversation(conversationId);
  if (currentConversation.value?.id === conversationId) {
    applyConversationDetail(detail);
  }
  await refreshConversationList();
}

async function handleRestoreConversation(conversationId: string) {
  const detail = await restoreConversation(conversationId);
  applyConversationDetail(detail);
  await refreshConversationList();
}

async function handleRestoreVersion(versionId: string) {
  if (!currentConversation.value) return;
  workspaceNotice.value = "";
  isChatBusy.value = true;
  try {
    const data = await restorePlanVersion(currentConversation.value.id, versionId);
    if (!data.success) {
      workspaceNotice.value = data.error?.message || "版本回退失败。";
      return;
    }
    applyConversationDetail(await requestConversationDetail(currentConversation.value.id));
    await refreshConversationList();
  } finally {
    isChatBusy.value = false;
  }
}

async function handleSaveManualEdit() {
  const data = await saveManualPlanEdit();
  workspaceNotice.value = data.error?.message || "手动编辑暂未开放。";
}

function startNewConversation() {
  appMode.value = "empty_chat";
  currentConversation.value = null;
  currentPlan.value = null;
  messages.value = [];
  versions.value = [];
  response.value = null;
  errorMessage.value = "";
  chatErrorMessage.value = "";
  workspaceNotice.value = "";
}

onMounted(() => {
  const storedTheme = window.localStorage.getItem("chinatravel-theme");
  const storedCoachMode = window.localStorage.getItem("chinatravel-coach-mode");
  isDarkTheme.value = storedTheme === "dark";
  if (storedCoachMode) selectedCoachMode.value = storedCoachMode;
  document.documentElement.dataset.theme = isDarkTheme.value ? "dark" : "light";
  void refreshRuntimeHealth();
  void refreshConversationList();
  void refreshRecommendations();
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
            <code>GET /api/conversations</code>
            <code>GET /api/recommended-plans</code>
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

    <section v-if="false" class="workspace-grid legacy-plan-panel" aria-label="兼容旧规划表单">
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

    <section v-if="appMode === 'empty_chat'" class="conversation-workbench empty-chat" aria-label="empty_chat">
      <ConversationSidebar
        :conversations="conversations"
        :current-conversation-id="currentConversation?.id"
        :loading="isConversationLoading"
        @new-conversation="startNewConversation"
        @select-conversation="handleSelectConversation"
        @archive-conversation="handleArchiveConversation"
        @restore-conversation="handleRestoreConversation"
      />
      <TravelChatPanel
        mode="empty_chat"
        :messages="messages"
        :busy="isChatBusy"
        :error-message="chatErrorMessage"
        @send-message="handleChatMessage"
      />
      <RecommendedPlans
        :recommendations="recommendedPlans"
        :loading="isRecommendationLoading"
        @open-recommendation="handleOpenRecommendation"
      />
    </section>

    <section v-else class="conversation-workbench plan-workspace-grid" aria-label="plan_workspace">
      <div class="workspace-left-rail">
        <ConversationSidebar
          :conversations="conversations"
          :current-conversation-id="currentConversation?.id"
          :loading="isConversationLoading"
          @new-conversation="startNewConversation"
          @select-conversation="handleSelectConversation"
          @archive-conversation="handleArchiveConversation"
          @restore-conversation="handleRestoreConversation"
        />
        <TravelChatPanel
          mode="plan_workspace"
          :messages="messages"
          :busy="isChatBusy"
          :error-message="chatErrorMessage"
          @send-message="handleChatMessage"
        />
        <PlanVersionTimeline
          :versions="versions"
          :current-version-id="currentVersionId"
          :busy="isChatBusy"
          @restore-version="handleRestoreVersion"
        />
      </div>
      <PlanWorkspace
        :conversation="currentConversation"
        :current-plan="currentPlan"
        :save-message="workspaceNotice"
        @save-manual-edit="handleSaveManualEdit"
      />
    </section>
  </main>
</template>
