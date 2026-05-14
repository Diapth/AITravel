<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Bookmark,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock3,
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
import AmapRoutePanel from "./AmapRoutePanel.vue";
import type { RoutePoint } from "../types/route";
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

const actionMessage = ref("");
const selectedTab = ref<number | "overview">(1);
const activePointId = ref("");

const plan = computed<TravelPlan | undefined>(() => {
  if (props.response?.success) return props.response.plan;
  return undefined;
});

const displayResponse = computed(() => props.response);
const itinerary = computed<PlanDay[]>(() => normalizeItineraryDays(plan.value?.itinerary));
const hasResult = computed(() => Boolean(plan.value));
const hasSubmitted = computed(() => Boolean(props.payload || props.response || props.progressDays.length || props.errorMessage));
const displayStatusLabel = computed(() => props.statusLabel);
const displayStatusMode = computed(() => props.statusMode);
const friendlyError = computed(() => {
  const code = props.response?.error?.code;
  const message = props.errorMessage || props.response?.error?.message || "";

  if (code === "RUNTIME_NOT_READY") {
    return {
      title: "运行环境还没准备好",
      detail: "DeepSeek Key 或本地旅行数据库未配置完整。请先检查顶部服务状态和后端环境。",
    };
  }

  if (code === "REQUEST_FAILED" || message.includes("Unexpected token") || message.includes("404")) {
    return {
      title: "前端暂时连不上后端",
      detail: "开发模式下请同时启动 FastAPI，Vite 会把 /api 请求转发到 127.0.0.1:8000。",
    };
  }

  if (code === "PLANNER_FAILED") {
    return {
      title: "规划器没有生成可用行程",
      detail: "模型链路已响应，但本地数据或城市名称匹配失败。可以换成数据库已有城市，或在原文里写清出发地、目的地和天数后重试。",
    };
  }

  return {
    title: "这次生成失败了",
    detail: message || "请稍后重试，或检查后端日志中的 request_id。",
  };
});

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

const tabDays = computed(() => itinerary.value.map((day, index) => Number(day.day || index + 1)));
const selectedDay = computed(() => {
  if (selectedTab.value === "overview") return itinerary.value[0];
  return itinerary.value.find((day, index) => Number(day.day || index + 1) === selectedTab.value) || itinerary.value[0];
});
const selectedDayIndex = computed(() => Math.max(itinerary.value.findIndex((day) => day === selectedDay.value), 0));
const routePoints = computed<RoutePoint[]>(() => itinerary.value.flatMap((day, dayIndex) => buildDayRoutePoints(day, dayIndex)));
const visibleRoutePoints = computed(() => {
  if (selectedTab.value === "overview") return routePoints.value;
  return routePoints.value.filter((point) => point.day === selectedTab.value);
});
const selectedDayRouteText = computed(() => visibleRoutePoints.value.map((point) => point.name).join(" → "));
const displayedActivityRows = computed(() => {
  const days = selectedTab.value === "overview" ? itinerary.value : selectedDay.value ? [selectedDay.value] : [];
  return days.flatMap((day, dayIndex) => {
    const dayNumber = Number(day.day || dayIndex + 1);
    return (day.activities || []).map((activity, activityIndex) => ({
      activity,
      activityIndex,
      dayNumber,
      key: `${dayNumber}-${activityIndex}`,
    }));
  });
});
const totalBudget = computed(() => {
  const summed = selectedTab.value === "overview" ? itinerary.value.reduce((sum, day) => sum + budgetTotal(day), 0) : selectedDay.value ? budgetTotal(selectedDay.value) : 0;
  const planTotal = Number(plan.value?.total_cost);
  return summed || (Number.isFinite(planTotal) ? planTotal : 0);
});
const budgetChips = computed(() => (selectedTab.value === "overview" ? sumBudgetItems(itinerary.value) : selectedDay.value ? budgetItems(selectedDay.value) : []));
const displayLocationText = computed(() => {
  if (selectedTab.value !== "overview") return selectedDay.value?.location || props.payload?.target_city || "目的地";
  const locations = Array.from(new Set(itinerary.value.map((day) => day.location).filter(Boolean)));
  return locations.join(" / ") || plan.value?.target_city || props.payload?.target_city || "目的地";
});
const accommodationText = computed(() => {
  if (selectedTab.value !== "overview") return selectedDay.value?.accommodation || "推荐商圈附近";
  const accommodations = Array.from(new Set(itinerary.value.map((day) => day.accommodation).filter(Boolean)));
  return accommodations.join(" / ") || "推荐商圈附近";
});

watch(
  itinerary,
  (days) => {
    if (!days.length) {
      selectedTab.value = 1;
      activePointId.value = "";
      return;
    }
    const firstDay = Number(days[0].day || 1);
    const dayExists = selectedTab.value === "overview" || days.some((day, index) => Number(day.day || index + 1) === selectedTab.value);
    if (!dayExists) selectedTab.value = firstDay;
  },
  { immediate: true },
);

watch(
  visibleRoutePoints,
  (points) => {
    activePointId.value = points[0]?.id || "";
  },
  { immediate: true },
);

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

function sumBudgetItems(days: PlanDay[]): BudgetBreakdown[] {
  const totals = new Map<string, number>();
  days.forEach((day) => {
    budgetItems(day).forEach((item) => {
      const value = Number(item.amount);
      if (!Number.isFinite(value)) return;
      totals.set(item.label, (totals.get(item.label) || 0) + value);
    });
  });
  return Array.from(totals.entries()).map(([label, amount]) => ({ label, amount }));
}

function tabLabel(tab: number | "overview") {
  return tab === "overview" ? "总览" : `第 ${tab} 天`;
}

function selectTab(tab: number | "overview") {
  selectedTab.value = tab;
}

function routePointId(dayNumber: number, activityIndex: number, suffix = "main") {
  return `day-${dayNumber}-activity-${activityIndex}-${suffix}`;
}

function buildDayRoutePoints(day: PlanDay, dayIndex: number): RoutePoint[] {
  const dayNumber = Number(day.day || dayIndex + 1);
  const city = day.location || plan.value?.target_city || props.payload?.target_city;
  const points: RoutePoint[] = [];
  const seen = new Set<string>();

  (day.activities || []).forEach((activity, activityIndex) => {
    const names =
      activity.type === "train"
        ? [activity.start, activity.end].filter(Boolean)
        : [activity.position || activity.title || activity.end || activity.start].filter(Boolean);
    names.forEach((name, nameIndex) => {
      const trimmed = String(name).trim();
      const dedupeKey = `${dayNumber}-${trimmed}`;
      if (!trimmed || seen.has(dedupeKey)) return;
      seen.add(dedupeKey);
      points.push({
        id: routePointId(dayNumber, activityIndex, String(nameIndex)),
        day: dayNumber,
        order: points.length + 1,
        name: trimmed,
        type: activity.type,
        city,
        time: activityTime(activity),
        meta: activityMeta(activity),
      });
    });
  });

  return points;
}

function pointForActivity(dayNumber: number, activityIndex: number) {
  const candidates = visibleRoutePoints.value.filter((point) => point.id.startsWith(`day-${dayNumber}-activity-${activityIndex}-`));
  return candidates[candidates.length - 1];
}

function activateActivity(dayNumber: number, activityIndex: number) {
  const point = pointForActivity(dayNumber, activityIndex);
  activePointId.value = point?.id || "";
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
  await navigator.clipboard.writeText(text);
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

    <div class="result-scroll-area" :class="{ 'is-map-mode': hasResult }">
      <div v-if="summaryItems.length" id="summary-strip" class="summary-strip route-summary-strip">
        <div v-for="item in summaryItems" :key="item.label" class="summary-item" :class="{ strong: item.strong }">
          <component :is="item.icon" :size="24" />
          <div>
            <p class="summary-label">{{ item.label }}</p>
            <p class="summary-value">{{ item.value }}</p>
          </div>
        </div>
      </div>

      <p v-if="plan?.llm_summary" class="plan-summary route-plan-summary">{{ plan.llm_summary }}</p>

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
              <p>{{ day.title }}</p>
              <span>{{ day.detail }}</span>
            </div>
          </article>
        </div>
        <p v-else class="message is-muted">提交旅行需求后，这里会显示真实请求阶段。完整结果返回后再展示地图、预算和时间表。</p>
      </div>

      <div v-if="errorMessage" class="message is-error error-card">
        <strong>{{ friendlyError.title }}</strong>
        <span>{{ friendlyError.detail }}</span>
        <small v-if="response?.meta?.request_id">request_id: {{ response.meta.request_id }}</small>
      </div>
      <p v-else-if="isGenerating" class="message is-loading">当前生成中的天数会显示骨架内容，已完成天数会先保留给你阅读。</p>

      <section v-if="!hasSubmitted" class="empty-state">
        <div class="empty-state-icon">
          <Sparkles :size="28" />
        </div>
        <h3>等待生成行程</h3>
        <p>填写左侧旅行需求并点击生成后，前端会调用后端 <code>/api/plan</code>，这里会展示真实返回的地图路线、行程和预算。</p>
      </section>

      <section v-if="hasResult" class="route-planner-layout" aria-label="地图行程详情">
        <AmapRoutePanel
          :points="routePoints"
          :selected-day="selectedTab"
          :active-point-id="activePointId"
          @select-point="activePointId = $event"
        />

        <aside class="route-detail-panel">
          <div class="route-tabs" role="tablist" aria-label="行程天数切换">
            <button type="button" role="tab" :class="{ active: selectedTab === 'overview' }" @click="selectTab('overview')">总览</button>
            <button v-for="day in tabDays" :key="day" type="button" role="tab" :class="{ active: selectedTab === day }" @click="selectTab(day)">
              第 {{ day }} 天
            </button>
          </div>

          <div v-if="selectedDay" class="route-day-detail">
            <section class="route-highlight-panel" aria-label="行程亮点">
              <h3>行程亮点</h3>
              <div class="highlight-chips compact">
                <span v-for="item in highlights" :key="item"><Sparkles :size="13" /> {{ item }}</span>
              </div>
            </section>

            <div class="route-day-head">
              <div>
                <span class="day-badge">{{ tabLabel(selectedTab) }}</span>
                <h3>{{ selectedTab === "overview" ? "全部路线总览" : dayTitle(selectedDay, selectedDayIndex) }}</h3>
                <p>{{ selectedTab === "overview" ? "所有天数的地标会同时显示在左侧地图，预算按全部天数汇总。" : selectedDayRouteText || daySummary(selectedDay) }}</p>
              </div>
              <div class="route-total-card">
                <span>合计</span>
                <b>¥{{ formatMoney(totalBudget) }}</b>
              </div>
            </div>

            <div class="budget-chip-row" aria-label="预算分类">
              <span v-for="item in budgetChips" :key="item.label">
                <component :is="budgetIcon(item.label)" :size="14" /> {{ item.label }} ¥{{ formatMoney(item.amount) }}
              </span>
            </div>

            <div class="route-meta-grid">
              <span><MapPin :size="15" /> {{ displayLocationText }}</span>
              <span><Hotel :size="15" /> 住宿：{{ accommodationText }}</span>
            </div>

            <div class="route-table" :class="{ 'is-overview': selectedTab === 'overview' }" role="table" :aria-label="selectedTab === 'overview' ? '全部行程表' : '当天行程表'">
              <div class="route-table-head" role="row">
                <span v-if="selectedTab === 'overview'">天数</span>
                <span>时间</span>
                <span>类型</span>
                <span>地点与活动</span>
                <span>费用</span>
              </div>
              <button
                v-for="row in displayedActivityRows"
                :key="row.key"
                class="route-table-row"
                :class="{ active: pointForActivity(row.dayNumber, row.activityIndex)?.id === activePointId, 'is-overview-row': selectedTab === 'overview' }"
                type="button"
                role="row"
                @click="activateActivity(row.dayNumber, row.activityIndex)"
              >
                <span v-if="selectedTab === 'overview'" class="route-day-index">D{{ row.dayNumber }}</span>
                <time>{{ activityTime(row.activity) }}</time>
                <span><component :is="activityIcon(row.activity.type)" :size="15" /> {{ activityTypeLabel(row.activity.type) || "活动" }}</span>
                <strong>{{ activityPlace(row.activity) }}<small>{{ activityMeta(row.activity) }}</small><small v-if="row.activity.recommended_food">推荐：{{ row.activity.recommended_food }}</small></strong>
                <b>{{ row.activity.cost !== undefined ? `¥${formatMoney(row.activity.cost)}` : "-" }}</b>
              </button>
            </div>

            <section class="route-tip-panel">
              <Sun :size="18" />
              <div>
                <h3>住宿与提示</h3>
                <p>{{ accommodationText }}；预算充足时可加入购物、茶馆或夜游体验。</p>
              </div>
            </section>
          </div>
        </aside>
      </section>
    </div>
  </section>
</template>
