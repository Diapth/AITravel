<script setup lang="ts">
import { computed, ref } from "vue";
import { Edit3, Eye } from "lucide-vue-next";
import DailyItineraryEditor from "./DailyItineraryEditor.vue";
import PlannerResults from "./PlannerResults.vue";
import type { ConversationSummary, PlanResponse, TravelPlan } from "../services/planner";

const props = defineProps<{
  conversation?: ConversationSummary | null;
  currentPlan?: TravelPlan | null;
  saveMessage?: string;
  serverWarnings?: string[];
  busy?: boolean;
}>();

const emit = defineEmits<{
  saveManualEdit: [plan: TravelPlan, options?: { validation_override?: boolean }];
}>();

const mode = ref<"readonly" | "edit">("readonly");

const readonlyResponse = computed<PlanResponse | null>(() =>
  props.currentPlan
    ? {
        success: true,
        plan: props.currentPlan,
      }
    : null,
);

const payload = computed(() => ({
  query: props.conversation?.title || "已保存行程",
  start_city: props.currentPlan?.start_city,
  target_city: props.currentPlan?.target_city,
  target_cities: props.currentPlan?.target_cities,
  departure_date: props.currentPlan?.departure_date,
  return_date: props.currentPlan?.return_date,
  days: props.currentPlan?.days,
  people_number: props.currentPlan?.people_number,
  budget: props.currentPlan?.budget,
}));
</script>

<template>
  <section class="plan-workspace" aria-label="行程工作区">
    <div class="workspace-toolbar">
      <div>
        <span>行程工作区</span>
        <h2>{{ conversation?.title || "未选择行程" }}</h2>
      </div>
      <div class="segmented-control" role="tablist" aria-label="工作区模式">
        <button type="button" :class="{ active: mode === 'readonly' }" @click="mode = 'readonly'">
          <Eye :size="16" /> 只读
        </button>
        <button type="button" :class="{ active: mode === 'edit' }" @click="mode = 'edit'">
          <Edit3 :size="16" /> 编辑
        </button>
      </div>
    </div>

    <DailyItineraryEditor
      v-if="mode === 'edit'"
      :plan="currentPlan"
      :busy="busy"
      :message="saveMessage"
      :server-warnings="serverWarnings"
      @save="(plan, options) => emit('saveManualEdit', plan, options)"
    />

    <PlannerResults
      v-else
      :is-generating="false"
      status-label="已打开"
      status-mode="is-ok"
      :payload="payload"
      :response="readonlyResponse"
      error-message=""
      :progress-days="[]"
    />
  </section>
</template>
