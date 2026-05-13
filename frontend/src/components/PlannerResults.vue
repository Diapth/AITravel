<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Bookmark,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
  Copy,
  Download,
  Hotel,
  LoaderCircle,
  MapPin,
  Share2,
  Sparkles,
  Sun,
  TrainFront,
  Trees,
  Utensils,
  Users,
  WalletCards,
} from "lucide-vue-next";
import type { BudgetBreakdown, PlanActivity, PlanDay, PlanRequest, PlanResponse, TravelPlan } from "../services/planner";

interface ProgressDay {
  day: number;
  status: "done" | "active" | "queued";
  title: string;
  detail: string;
}

const props = defineProps<{
  isGenerating: boolean;
  statusLabel: string;
  statusMode: string;
  payload: PlanRequest | null;
  response: PlanResponse | null;
  errorMessage: string;
  progressDays: ProgressDay[];
}>();

const jsonOpen = ref(false);
const actionMessage = ref("");

const plan = computed<TravelPlan | undefined>(() => {
  if (props.response?.success) return props.response.plan;
  return undefined;
});

const displayResponse = computed(() => props.response);
const itinerary = computed<PlanDay[]>(() => normalizeItineraryDays(plan.value?.itinerary));
const hasResult = computed(() => Boolean(plan.value));
const hasSubmitted = computed(() => Boolean(props.payload || props.response || props.progressDays.length || props.errorMessage));
const jsonPayload = computed(() => (displayResponse.value ? JSON.stringify(displayResponse.value, null, 2) : ""));
const displayStatusLabel = computed(() => props.statusLabel);
const displayStatusMode = computed(() => props.statusMode);

const summaryItems = computed(() => {
  const source = plan.value || props.payload;
  const days = source?.days || props.payload?.days;
  const people = source?.people_number || props.payload?.people_number;
  const budget = source?.budget || props.payload?.budget;
  return [
    { label: "出发地", value: source?.start_city, icon: MapPin },
    { label: "目的地", value: source?.target_city, icon: MapPin },
    { label: "天数", value: days ? `${days} 天 ${Math.max(Number(days) - 1, 0)} 晚` : undefined, icon: CalendarDays },
    { label: "人数", value: people ? `${people} 人` : undefined, icon: Users },
    { label: "预算（人均）", value: budget ? `¥${formatMoney(budget)}` : undefined, icon: WalletCards, strong: true },
  ].filter((item) => item.value);
});

const highlights = computed(() => {
  const names = itinerary.value
    .flatMap((day) => day.activities || [])
    .map((activity) => activity.title || activity.position || activity.recommended_food)
    .filter(Boolean)
    .slice(1, 6);
  return names.length ? names : ["漓江山水精华", "遇龙河竹筏体验", "十里画廊骑行", "银子岩溶洞奇观", "阳朔西街夜游"];
});

function dayCost(day: PlanDay) {
  return (day.activities || []).reduce((sum, activity) => {
    const value = Number(activity.cost);
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);
}

function isGroupedDay(item: PlanDay | PlanActivity): item is PlanDay {
  return Array.isArray((item as PlanDay).activities);
}

function normalizeItineraryDays(items: TravelPlan["itinerary"]): PlanDay[] {
  if (!Array.isArray(items)) return [];

  const grouped = new Map<number, PlanDay>();
  items.forEach((item, index) => {
    if (isGroupedDay(item)) {
      const dayNumber = Number(item.day || index + 1);
      const existing = grouped.get(dayNumber) || { day: dayNumber, activities: [] };
      grouped.set(dayNumber, { ...existing, ...item, day: dayNumber, activities: item.activities || existing.activities || [] });
      return;
    }

    const dayNumber = Number(item.day || 1);
    const existing = grouped.get(dayNumber) || { day: dayNumber, activities: [] };
    grouped.set(dayNumber, { ...existing, activities: [...(existing.activities || []), item] });
  });

  return Array.from(grouped.values()).sort((a, b) => Number(a.day || 0) - Number(b.day || 0));
}

function activityPlace(activity: PlanActivity) {
  if (activity.title) return activity.title;
  if (activity.type === "train" && activity.start && activity.end) return `${activity.start} → ${activity.end}`;
  return activity.position || activity.end || activity.start || "未命名活动";
}

function activityTime(activity: PlanActivity) {
  if (activity.start_time && activity.end_time) return `${activity.start_time} - ${activity.end_time}`;
  return activity.start_time || activity.end_time || "时间待定";
}

function activityMeta(activity: PlanActivity) {
  const parts = [
    activityTypeLabel(activity.type),
    activity.TrainID,
    activity.transportation,
    activity.price !== undefined ? `单价 ¥${activity.price}` : undefined,
    activity.tickets ? `${activity.tickets} 张票` : undefined,
    activity.rooms ? `${activity.rooms} 间房` : undefined,
  ].filter(Boolean);
  return parts.join(" · ") || activity.position || "行程活动";
}

function activityTypeLabel(type?: string) {
  const labels: Record<string, string> = {
    train: "交通",
    attraction: "游览",
    restaurant: "餐饮",
    accommodation: "住宿",
  };
  return type ? labels[type] || type : undefined;
}

function activityIcon(type?: string) {
  if (type === "restaurant") return Utensils;
  if (type === "train") return TrainFront;
  if (type === "accommodation") return Hotel;
  if (type === "attraction") return Trees;
  return MapPin;
}

function dayTitle(day: PlanDay, index: number) {
  return day.title || day.activities?.[0]?.position || `第 ${day.day || index + 1} 天行程`;
}

function daySummary(day: PlanDay) {
  return day.summary || day.activities?.[0]?.description || "根据交通、景点、餐饮与住宿约束生成的紧凑行程。";
}

function dayImage(day: PlanDay) {
  return day.image;
}

function budgetItems(day: PlanDay): BudgetBreakdown[] {
  if (day.budget?.length) return day.budget;

  const categories: Record<string, number> = { 交通: 0, 门票: 0, 餐饮: 0, 住宿: 0, 其他: 0 };
  (day.activities || []).forEach((activity) => {
    const cost = Number(activity.cost);
    if (!Number.isFinite(cost)) return;
    if (activity.type === "train") categories["交通"] += cost;
    else if (activity.type === "restaurant") categories["餐饮"] += cost;
    else if (activity.type === "accommodation") categories["住宿"] += cost;
    else if (activity.type === "attraction") categories["门票"] += cost;
    else categories["其他"] += cost;
  });

  return Object.entries(categories)
    .filter(([, amount]) => amount > 0)
    .map(([label, amount]) => ({ label, amount }));
}

function budgetIcon(label: string) {
  if (label.includes("交通")) return TrainFront;
  if (label.includes("门票")) return Trees;
  if (label.includes("餐饮")) return Utensils;
  if (label.includes("住宿")) return Hotel;
  return WalletCards;
}

function budgetTotal(day: PlanDay) {
  const items = budgetItems(day);
  const total = items.reduce((sum, item) => {
    const value = Number(item.amount);
    return Number.isFinite(value) ? sum + value : sum;
  }, 0);
  return total || dayCost(day);
}

function formatMoney(value?: number | string) {
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) return value || "0";
  return numberValue.toLocaleString("zh-CN");
}

function notifyAction(message: string) {
  actionMessage.value = message;
  window.setTimeout(() => {
    if (actionMessage.value === message) actionMessage.value = "";
  }, 2200);
}

function buildShareText() {
  const destination = plan.value?.target_city || props.payload?.target_city || "旅行目的地";
  const days = plan.value?.days || props.payload?.days;
  const people = plan.value?.people_number || props.payload?.people_number;
  return `ChinaTravel Planner 已生成 ${destination}${days ? ` ${days} 天` : ""}${people ? `，${people} 人` : ""}行程。`;
}

function downloadItinerary() {
  if (!displayResponse.value) return;
  const blob = new Blob([JSON.stringify(displayResponse.value, null, 2)], { type: "application/json;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `chinatravel-itinerary-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
  notifyAction("行程 JSON 已导出");
}

async function shareItinerary() {
  if (!displayResponse.value) return;
  const text = buildShareText();
  if (navigator.share) {
    await navigator.share({ title: "ChinaTravel Planner 行程", text });
    notifyAction("分享面板已打开");
    return;
  }
  await navigator.clipboard.writeText(`${text}\n${jsonPayload.value}`);
  notifyAction("分享内容已复制");
}

function saveItinerary() {
  if (!displayResponse.value) return;
  window.localStorage.setItem(
    "chinatravel-saved-itinerary",
    JSON.stringify({
      savedAt: new Date().toISOString(),
      payload: props.payload,
      response: displayResponse.value,
    }),
  );
  notifyAction("行程已保存到本地浏览器");
}

async function copyJson() {
  if (!jsonPayload.value) return;
  await navigator.clipboard.writeText(jsonPayload.value);
  notifyAction("JSON 已复制");
}
</script>

<template>
  <section class="result-workspace" aria-live="polite">
    <div class="section-topline result-topline">
      <div class="result-heading">
        <h2>规划结果 <span id="status-pill" class="status-pill" :class="displayStatusMode" role="status">{{ displayStatusLabel }}</span></h2>
      </div>
      <div class="result-actions" aria-label="结果操作">
        <button class="secondary-action" type="button" :disabled="!displayResponse" @click="downloadItinerary">
          <Download :size="17" /> 导出行程 <ChevronDown :size="15" />
        </button>
        <button class="secondary-action" type="button" :disabled="!displayResponse" @click="shareItinerary">
          <Share2 :size="17" /> 分享
        </button>
        <button class="secondary-action" type="button" :disabled="!displayResponse" @click="saveItinerary">
          <Bookmark :size="17" /> 保存行程
        </button>
      </div>
    </div>

    <p v-if="actionMessage" class="action-feedback" role="status">{{ actionMessage }}</p>

    <div v-if="summaryItems.length" id="summary-strip" class="summary-strip">
      <div v-for="item in summaryItems" :key="item.label" class="summary-item" :class="{ strong: item.strong }">
        <component :is="item.icon" :size="29" />
        <div>
          <p class="summary-label">{{ item.label }}</p>
          <p class="summary-value">{{ item.value }}</p>
        </div>
      </div>
    </div>

    <p v-if="plan?.llm_summary" class="plan-summary">{{ plan.llm_summary }}</p>

    <div v-if="isGenerating || (progressDays.length && !hasResult)" class="generation-panel">
      <div class="generation-head">
        <div class="generation-title">
          <Sparkles :size="19" />
          <div>
            <p>模型生成过程</p>
            <span>DeepSeek 负责生成，LLMNeSy 负责约束校验与路线修正。</span>
          </div>
        </div>
        <span class="generation-pulse" :class="{ active: isGenerating }">
          {{ isGenerating ? "运行中" : hasResult ? "已完成" : "待开始" }}
        </span>
      </div>

      <div v-if="progressDays.length" class="progress-days">
        <article v-for="day in progressDays" :key="day.day" class="progress-day" :class="`is-${day.status}`">
          <div class="progress-icon">
            <CheckCircle2 v-if="day.status === 'done'" :size="18" />
            <LoaderCircle v-else-if="day.status === 'active'" :size="18" class="spin-icon" />
            <Clock3 v-else :size="18" />
          </div>
          <div>
            <p>第 {{ day.day }} 天 · {{ day.title }}</p>
            <span>{{ day.status === "queued" ? "等待生成" : day.detail }}</span>
          </div>
        </article>
      </div>
      <p v-else class="message is-muted">提交旅行需求后，这里会显示当前生成与等待生成的按天状态。</p>
    </div>

    <p v-if="errorMessage" class="message is-error">{{ errorMessage }}</p>
    <p v-else-if="isGenerating" class="message is-loading">当前生成中的天数会显示骨架内容，已完成天数会先保留给你阅读。</p>

    <section v-if="!hasSubmitted" class="empty-state">
      <div class="empty-state-icon">
        <Sparkles :size="28" />
      </div>
      <h3>等待生成行程</h3>
      <p>填写左侧旅行需求并点击生成后，前端会调用后端 <code>/api/plan</code>，这里会展示真实返回的行程、预算和 JSON 原文。</p>
    </section>

    <div class="timeline-list" aria-label="结构化行程">
      <article v-for="(day, index) in itinerary" :key="index" class="timeline-item">
        <div class="timeline-rail">
          <span>第 {{ day.day || index + 1 }} 天</span>
          <i />
        </div>

        <section class="itinerary-card">
          <img v-if="dayImage(day)" class="day-photo" :src="dayImage(day)" :alt="dayTitle(day, index)" />
          <div v-else class="day-photo scenic-photo" aria-hidden="true">
            <span />
          </div>
          <div class="day-copy">
            <h3>{{ dayTitle(day, index) }}</h3>
            <p>{{ daySummary(day) }}</p>
            <div class="day-meta">
              <span><MapPin :size="16" /> {{ day.location || payload?.target_city || "目的地" }}</span>
              <span><Hotel :size="16" /> 住宿：{{ day.accommodation || "推荐商圈附近" }}</span>
            </div>
          </div>
          <div class="schedule-list">
            <div v-for="(activity, activityIndex) in day.activities || []" :key="activityIndex" class="schedule-item">
              <component :is="activityIcon(activity.type)" :size="17" />
              <time>{{ activityTime(activity) }}</time>
              <span>{{ activityPlace(activity) }}</span>
              <small v-if="activityMeta(activity)">{{ activityMeta(activity) }}</small>
              <small v-if="activity.recommended_food">推荐：{{ activity.recommended_food }}</small>
            </div>
          </div>
        </section>

        <aside class="budget-card">
          <h3>预算（{{ payload?.people_number || plan?.people_number || 2 }} 人）</h3>
          <div v-for="item in budgetItems(day)" :key="item.label" class="budget-row">
            <span><component :is="budgetIcon(item.label)" :size="16" /> {{ item.label }}</span>
            <b>¥{{ formatMoney(item.amount) }}</b>
          </div>
          <div class="budget-total">
            <span>合计</span>
            <b>¥{{ formatMoney(budgetTotal(day)) }}</b>
          </div>
        </aside>
      </article>
    </div>

    <section v-if="hasResult" class="insight-strip" aria-label="行程亮点与提示">
      <div>
        <h3>行程亮点</h3>
        <div class="highlight-chips">
          <span v-for="item in highlights" :key="item"><Sparkles :size="14" /> {{ item }}</span>
        </div>
      </div>
      <div class="warm-tip">
        <Sun :size="22" />
        <div>
          <h3>温馨提示</h3>
          <p>桂林天气多变，建议携带雨具；防晒防蚊注意。</p>
        </div>
      </div>
    </section>

    <section class="json-panel">
      <div class="json-toolbar">
        <button class="json-toggle" type="button" :disabled="!displayResponse" @click="jsonOpen = !jsonOpen">
          <ChevronDown :size="18" :class="{ rotated: jsonOpen }" />
          原文（JSON）
        </button>
        <button class="copy-badge" type="button" :disabled="!displayResponse" @click="copyJson">
          <Copy :size="15" /> 复制
        </button>
      </div>
      <pre v-if="jsonOpen && displayResponse" id="json-output" class="json-output">{{ jsonPayload }}</pre>
    </section>
  </section>
</template>
