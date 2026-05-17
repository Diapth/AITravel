<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  BookOpen, BrainCircuit, ChevronDown, Clock3, Compass,
  GitBranch, Landmark, Map, MessageCircle, Moon, Server, Sparkles, Sun,
  Search,
} from "lucide-vue-next";
import ConversationSidebar from "./components/ConversationSidebar.vue";
import PlanVersionTimeline from "./components/PlanVersionTimeline.vue";
import PlanWorkspace from "./components/PlanWorkspace.vue";
import PlannerComposer from "./components/PlannerComposer.vue";
import PlannerResults from "./components/PlannerResults.vue";
import RecommendedPlans from "./components/RecommendedPlans.vue";
import TravelChatPanel from "./components/TravelChatPanel.vue";
import {
  requestConversationDetail,
  requestPlan,
  requestRecommendedPlans,
  openRecommendedPlan,
  type ConversationDetailResponse,
  type PlanRequest,
  type PlanResponse,
  type RecommendationItem,
  type TravelPlan,
} from "./services/planner";
import { useChat } from "./composables/useChat";
import { useConversations } from "./composables/useConversations";
import { useMobilePanel } from "./composables/useMobilePanel";
import { usePlanWorkspace } from "./composables/usePlanWorkspace";
import { useRuntimeHealth } from "./composables/useRuntimeHealth";
import { useTheme } from "./composables/useTheme";

// ── Types ──
type AppMode = "empty_chat" | "plan_workspace";
type MobilePanel = "history" | "chat" | "recommendations" | "versions" | "plan";
interface ProgressDay { day: number; status: "done" | "active" | "queued"; title: string; detail: string; }

// ── App-level state (declare before composables that consume it) ──
const appMode = ref<AppMode>("empty_chat");
const isPanelTransitioning = ref(false);
const isKeyboardOpen = ref(false);
const docsOpen = ref(false);
const selectedCoachMode = ref("旅行规划师");
const coachModes = ["轻松休闲", "高效紧凑", "亲子友好"];
const elementPlusConfig = { button: { autoInsertSpace: true } };
const recommendedPlans = ref<RecommendationItem[]>([]);
const isRecommendationLoading = ref(false);

// ── Composables (names match template) ──
const { isDark: isDarkTheme, applyTheme, toggle: toggleTheme } = useTheme();
const { health: runtimeHealth, status: serviceStatus, serviceType, refresh: refreshHealth } = useRuntimeHealth();
const {
  list: conversations, current: currentConversation, loading: isConversationLoading,
  select: selectConversation, archive: archiveConversation, restore: restoreConversation,
  refreshList: refreshConversationList,
} = useConversations();
const {
  messages, busy: isChatBusy, error: chatErrorMessage,
  checklist: planningChecklist, checklistVisible, checklistReady,
  isChecklistGenerating, generatedCard: generatedPlanCard,
  inferChecklistFromMessages, updateChecklist,
  sendMessage, confirmGenerate, reset: resetChat,
} = useChat();
const {
  plan: currentPlan, versions, notice: workspaceNotice,
  warnings: manualEditServerWarnings, conflict: manualEditConflict, currentVersionId,
  setFromDetail, restoreVersion, saveManualEdit, reset: resetWorkspace,
} = usePlanWorkspace();
const { panel: mobilePanel, tabs: mobileTabs } = useMobilePanel(appMode);

// ── Legacy PlannerComposer state ──
const isGenerating = ref(false);
const response = ref<PlanResponse | null>(null);
const errorMessage = ref("");
const submittedPayload = ref<PlanRequest | null>(null);
const progressDays = ref<ProgressDay[]>([]);
let progressTimer: number | undefined;

// ── Derived ──
const mobileTabOptions = computed(() => mobileTabs.value.map((t) => ({ label: t.label, value: t.id })));
const mobileBottomTabs = computed(() =>
  mobileTabs.value.map((t) => {
    const icons: Record<string, typeof Clock3> = {
      history: Clock3, chat: MessageCircle, recommendations: Sparkles, versions: GitBranch, plan: Map,
    };
    return { ...t, icon: icons[t.id] };
  }),
);
const statusLabel = computed(() =>
  isGenerating.value || isChatBusy.value ? "生成中"
    : errorMessage.value || chatErrorMessage.value ? "失败"
    : response.value?.success || currentPlan.value ? "完成"
    : "待输入");
const statusMode = computed(() =>
  isGenerating.value || isChatBusy.value ? "is-loading"
    : errorMessage.value || chatErrorMessage.value ? "is-error"
    : response.value?.success || currentPlan.value ? "is-ok"
    : "");

// ── Progress animation ──
function inferDays(p: PlanRequest) { return Math.min(Math.max(p.days || 3, 1), 8); }
function createProgress(p: PlanRequest): ProgressDay[] {
  const d = p.target_city || "目的地"; const n = inferDays(p);
  return [
    { day: 1, status: "active", title: "解析需求", detail: `正在整理 ${d} ${n} 天游的城市、预算、人数和偏好约束。` },
    { day: 2, status: "queued", title: "检索交通与本地数据", detail: "LLMNeSy 正在匹配车次、景点、餐饮、住宿和预算约束。" },
    { day: 3, status: "queued", title: "生成并校验路线", detail: "DeepSeek 会参考结构化表格和商圈信息，生成更优行程。" },
    { day: 4, status: "queued", title: "等待完整结果", detail: "后端返回完整 plan 后，地图、Tab、预算和时间表会一次性出现。" },
  ];
}
function advanceProgress() {
  const idx = progressDays.value.findIndex((s) => s.status === "active");
  if (idx === -1) return;
  const last = progressDays.value.length - 1;
  progressDays.value = progressDays.value.map((s, i) =>
    i < idx ? { ...s, status: "done" as const }
    : i === idx ? { ...s, status: "done" as const }
    : i === idx + 1 && idx < last ? { ...s, status: "active" as const }
    : s);
}
function startProgress(p: PlanRequest) { window.clearInterval(progressTimer); progressDays.value = createProgress(p); progressTimer = window.setInterval(advanceProgress, 12000); }
function stopProgress() { window.clearInterval(progressTimer); progressTimer = undefined; }

// ── Central detail applicator ──
function applyConversationDetail(detail: ConversationDetailResponse) {
  if (!detail.success) { chatErrorMessage.value = detail.error?.message || "会话读取失败，请稍后重试。"; return; }
  currentConversation.value = detail.conversation || null;
  messages.value = detail.messages || [];
  setFromDetail(detail);
  response.value = detail.current_plan ? { success: true, plan: detail.current_plan } : null;
  submittedPayload.value = detail.current_plan
    ? { query: detail.conversation?.title || "已保存行程", start_city: detail.current_plan.start_city, target_city: detail.current_plan.target_city, target_cities: detail.current_plan.target_cities, departure_date: detail.current_plan.departure_date, return_date: detail.current_plan.return_date, days: detail.current_plan.days, people_number: detail.current_plan.people_number, budget: detail.current_plan.budget }
    : null;
  if (detail.current_plan) { appMode.value = "plan_workspace"; checklistVisible.value = false; generatedPlanCard.value = null; mobilePanel.value = "plan"; }
  else { appMode.value = "empty_chat"; planningChecklist.value = inferChecklistFromMessages(detail.messages || []); mobilePanel.value = "chat"; }
}

// ── App-mode switching ──
function switchAppMode(mode: AppMode) {
  if (isPanelTransitioning.value || mode === appMode.value) return;
  isPanelTransitioning.value = true; appMode.value = mode;
  window.setTimeout(() => { isPanelTransitioning.value = false; }, 280);
}

function selectCoachMode(mode: string | number | object) {
  if (typeof mode !== "string") return;
  selectedCoachMode.value = mode;
  window.localStorage.setItem("chinatravel-coach-mode", mode);
}

// ── Handlers ──
async function handleSubmit(payload: PlanRequest) {
  submittedPayload.value = payload; response.value = null; errorMessage.value = ""; isGenerating.value = true;
  startProgress(payload);
  try {
    const data = await requestPlan(payload); response.value = data;
    if (!data.success) errorMessage.value = data.error?.message || "生成失败，请检查后端配置。";
  } catch (e) {
    errorMessage.value = e instanceof Error ? e.message : "请求失败，请稍后重试。";
    response.value = { success: false, error: { code: "REQUEST_FAILED", message: errorMessage.value } };
  } finally {
    isGenerating.value = false; stopProgress();
    progressDays.value = progressDays.value.map((d) => ({ ...d, status: response.value?.success ? "done" as const : d.status, title: response.value?.success && d.title === "等待完整结果" ? "结果已返回" : d.title }));
  }
}

async function handleChatMessage(message: string) {
  await sendMessage(message, currentConversation.value, applyConversationDetail);
  if (currentPlan.value) {
    appMode.value = "plan_workspace";
    mobilePanel.value = "chat";
  } else {
    appMode.value = "empty_chat";
    mobilePanel.value = "chat";
  }
  await refreshConversationList();
}

async function handleConfirmGenerate() {
  if (!currentConversation.value) return;
  const payload = { ...planningChecklist.value, query: planningChecklist.value.query || currentConversation.value.title };
  startProgress(payload);
  try {
    await confirmGenerate(currentConversation.value, applyConversationDetail, () => {}, () => currentPlan.value);
  } finally {
    stopProgress();
    progressDays.value = progressDays.value.map((d) => ({ ...d, status: currentPlan.value ? "done" as const : d.status, title: currentPlan.value && d.title === "等待完整结果" ? "结果已返回" : d.title }));
  }
  appMode.value = "empty_chat"; mobilePanel.value = "chat";
  await refreshConversationList();
}

function handleOpenGeneratedPlan() { if (currentPlan.value) { appMode.value = "plan_workspace"; mobilePanel.value = "plan"; } }

async function handleSelectConversation(conversationId: string) {
  chatErrorMessage.value = ""; isConversationLoading.value = true;
  try { applyConversationDetail(await requestConversationDetail(conversationId)); }
  finally { isConversationLoading.value = false; }
}

async function handleOpenRecommendation(recommendationId: string) {
  chatErrorMessage.value = ""; isChatBusy.value = true;
  try { applyConversationDetail(await openRecommendedPlan(recommendationId)); await refreshConversationList(); }
  finally { isChatBusy.value = false; }
}

async function handleArchiveConversation(conversationId: string) { await archiveConversation(conversationId); }
async function handleRestoreConversation(conversationId: string) { applyConversationDetail(await restoreConversation(conversationId)); }

async function handleRestoreVersion(versionId: string) {
  if (!currentConversation.value) return;
  isChatBusy.value = true;
  try { await restoreVersion(currentConversation.value.id, versionId, applyConversationDetail); await refreshConversationList(); }
  finally { isChatBusy.value = false; }
}

async function handleSaveManualEdit(plan: TravelPlan, options: { validation_override?: boolean; conflict_override?: boolean } = {}) {
  if (!currentConversation.value) return;
  isChatBusy.value = true;
  try { await saveManualEdit(currentConversation.value.id, plan, currentVersionId.value, applyConversationDetail, options); await refreshConversationList(); }
  finally { isChatBusy.value = false; }
}

async function handleRefreshLatestPlan() {
  if (!currentConversation.value) return;
  await handleSelectConversation(currentConversation.value.id);
}

function handleBackToChat() {
  appMode.value = "empty_chat";
  mobilePanel.value = "chat";
}

function startNewConversation() {
  appMode.value = "empty_chat";
  currentConversation.value = null;
  resetChat(); resetWorkspace();
  response.value = null; errorMessage.value = "";
}

async function refreshRecommendations() {
  isRecommendationLoading.value = true;
  try { const data = await requestRecommendedPlans(); if (data.success) recommendedPlans.value = data.recommendations; }
  finally { isRecommendationLoading.value = false; }
}

// ── Lifecycle ──
onMounted(() => {
  const storedTheme = window.localStorage.getItem("chinatravel-theme");
  const storedCoachMode = window.localStorage.getItem("chinatravel-coach-mode");
  applyTheme(storedTheme === "dark" ? "dark" : "light");
  if (storedCoachMode) selectedCoachMode.value = storedCoachMode;
  void refreshHealth(); void refreshConversationList(); void refreshRecommendations();
  if (window.visualViewport) {
    const onResize = () => { isKeyboardOpen.value = window.visualViewport!.height < window.innerHeight * 0.8; };
    window.visualViewport.addEventListener("resize", onResize);
    onBeforeUnmount(() => window.visualViewport?.removeEventListener("resize", onResize));
  }
});
onBeforeUnmount(stopProgress);
</script>

<template>
  <el-config-provider :button="elementPlusConfig.button">
    <main class="app-shell" :class="{ 'is-plan-mode': appMode === 'plan_workspace' }">
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
          <el-tag class="service-tag" :type="serviceType(serviceStatus.fastapi)" effect="light" round disable-transitions>
            <Server :size="15" /> <span>FastAPI</span> <b>{{ serviceStatus.fastapi }}</b>
          </el-tag>
          <el-tag class="service-tag" :type="serviceType(serviceStatus.deepseek)" effect="light" round disable-transitions>
            <BrainCircuit :size="15" /> <span>DeepSeek</span> <b>{{ serviceStatus.deepseek }}</b>
          </el-tag>
          <el-tag class="service-tag" :type="serviceType(serviceStatus.llmnesy)" effect="light" round disable-transitions>
            <Compass :size="15" /> <span>LLMNeSy</span> <b>{{ serviceStatus.llmnesy }}</b>
          </el-tag>
          <el-tag class="service-tag" :type="serviceType(serviceStatus.tavily)" effect="light" round disable-transitions>
            <Search :size="15" /> <span>Tavily</span> <b>{{ serviceStatus.tavily }}</b>
          </el-tag>
        </div>
        <el-button class="header-icon-button" circle type="default" aria-label="切换主题" @click="toggleTheme">
          <span class="theme-icon">
            <Sun v-if="!isDarkTheme" :size="20" />
            <Moon v-else :size="20" />
          </span>
        </el-button>
        <el-popover
          v-model:visible="docsOpen"
          placement="bottom-end"
          trigger="click"
          :width="268"
          popper-class="docs-popover-v2"
          aria-label="接口说明"
        >
          <template #reference>
            <el-button class="header-icon-button" circle type="default" aria-label="查看手册">
              <BookOpen :size="20" />
            </el-button>
          </template>
          <div class="docs-popover-content">
            <b>接口说明</b>
            <span>页面由 Vue 构建，FastAPI 负责静态托管。</span>
            <code>POST /api/plan</code>
            <code>GET /api/health</code>
            <code>GET /api/conversations</code>
            <code>GET /api/recommended-plans</code>
          </div>
        </el-popover>
        <el-dropdown trigger="click" placement="bottom-end" @command="selectCoachMode">
          <el-button class="coach-button" type="default">
            <Moon :size="18" />
            <span>{{ selectedCoachMode }}</span>
            <ChevronDown :size="15" />
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="mode in coachModes" :key="mode" :command="mode">
                {{ mode }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
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

    <!-- <el-segmented
      v-model="mobilePanel"
      class="mobile-workbench-tabs"
      :options="mobileTabOptions"
      block
      aria-label="移动端工作台切换"
    /> -->

    <Transition name="panel-switch" mode="out-in">
    <section v-if="appMode === 'empty_chat'" key="empty-chat" class="conversation-workbench empty-chat" aria-label="empty_chat">
      <ConversationSidebar
        class="mobile-panel mobile-panel-history"
        :class="{ active: mobilePanel === 'history' }"
        :conversations="conversations"
        :current-conversation-id="currentConversation?.id"
        :loading="isConversationLoading"
        @new-conversation="startNewConversation"
        @select-conversation="handleSelectConversation"
        @archive-conversation="handleArchiveConversation"
        @restore-conversation="handleRestoreConversation"
      />
      <TravelChatPanel
        class="mobile-panel mobile-panel-chat"
        :class="{ active: mobilePanel === 'chat' }"
        mode="empty_chat"
        :messages="messages"
        :busy="isChatBusy"
        :generating-plan="isChecklistGenerating"
        :error-message="chatErrorMessage"
        :planning-checklist="planningChecklist"
        :checklist-visible="checklistVisible"
        :checklist-ready="checklistReady"
        :generated-card="generatedPlanCard"
        @send-message="handleChatMessage"
        @update-checklist="updateChecklist"
        @confirm-generate="handleConfirmGenerate"
        @open-generated-plan="handleOpenGeneratedPlan"
      />
      <RecommendedPlans
        class="mobile-panel mobile-panel-recommendations"
        :class="{ active: mobilePanel === 'recommendations' }"
        :recommendations="recommendedPlans"
        :loading="isRecommendationLoading"
        @open-recommendation="handleOpenRecommendation"
      />
    </section>

    <section v-else key="plan-workspace" class="conversation-workbench plan-workspace-grid" aria-label="plan_workspace">
      <div
        class="workspace-left-rail mobile-workspace-left"
        :class="{ active: mobilePanel === 'history' || mobilePanel === 'chat' || mobilePanel === 'versions' }"
      >
        <ConversationSidebar
          class="mobile-panel mobile-panel-history"
          :class="{ active: mobilePanel === 'history' }"
          :conversations="conversations"
          :current-conversation-id="currentConversation?.id"
          :loading="isConversationLoading"
          @new-conversation="startNewConversation"
          @select-conversation="handleSelectConversation"
          @archive-conversation="handleArchiveConversation"
          @restore-conversation="handleRestoreConversation"
        />
        <TravelChatPanel
          class="mobile-panel mobile-panel-chat"
          :class="{ active: mobilePanel === 'chat' }"
          mode="plan_workspace"
          :messages="messages"
          :busy="isChatBusy"
          :error-message="chatErrorMessage"
          @send-message="handleChatMessage"
        />
        <PlanVersionTimeline
          class="mobile-panel mobile-panel-versions"
          :class="{ active: mobilePanel === 'versions' }"
          :versions="versions"
          :current-version-id="currentVersionId"
          :busy="isChatBusy"
          @restore-version="handleRestoreVersion"
        />
      </div>
      <PlanWorkspace
        class="mobile-panel mobile-panel-plan"
        :class="{ active: mobilePanel === 'plan' }"
        :conversation="currentConversation"
        :current-plan="currentPlan"
        :save-message="workspaceNotice"
        :server-warnings="manualEditServerWarnings"
        :conflict="manualEditConflict"
        :busy="isChatBusy"
        @save-manual-edit="handleSaveManualEdit"
        @refresh-latest="handleRefreshLatestPlan"
        @back-to-chat="handleBackToChat"
      />
    </section>
    </Transition>

    <nav class="mobile-bottom-bar" :class="{ 'keyboard-open': isKeyboardOpen }" aria-label="移动端导航" @click.prevent>
      <button
        v-for="tab in mobileBottomTabs"
        :key="tab.id"
        class="mobile-bottom-tab"
        :class="{ active: mobilePanel === tab.id }"
        type="button"
        @click="mobilePanel = tab.id"
      >
        <component :is="tab.icon" :size="20" />
        <span>{{ tab.label }}</span>
      </button>
    </nav>
    </main>
  </el-config-provider>
</template>
