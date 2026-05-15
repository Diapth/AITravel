<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { CircleAlert, CopyPlus, Plus, Save, Trash2 } from "lucide-vue-next";
import type { FlatPlanActivity, PlanActivity, PlanDay, TravelPlan } from "../services/planner";

const props = defineProps<{
  plan?: TravelPlan | null;
  busy?: boolean;
  message?: string;
  serverWarnings?: string[];
}>();

const emit = defineEmits<{
  save: [plan: TravelPlan, options?: { validation_override?: boolean }];
}>();

type EditableDay = PlanDay & { activities: PlanActivity[] };

const draft = ref<TravelPlan>({});
const localWarning = ref("");

const validationWarnings = computed(() => {
  const warnings: string[] = [];
  if (!draft.value.target_city && !draft.value.target_cities?.length) warnings.push("请填写目的地。");
  if (!Array.isArray(draft.value.itinerary) || !draft.value.itinerary.length) warnings.push("至少保留 1 天行程。");
  editableDays.value.forEach((day, dayIndex) => {
    if (!day.day) warnings.push(`第 ${dayIndex + 1} 天缺少天数编号。`);
    day.activities.forEach((activity, activityIndex) => {
      if (!activity.type) warnings.push(`第 ${dayIndex + 1} 天第 ${activityIndex + 1} 个活动缺少类型。`);
      if (!activity.title && !activity.position && !activity.description) {
        warnings.push(`第 ${dayIndex + 1} 天第 ${activityIndex + 1} 个活动缺少地点或说明。`);
      }
    });
  });
  return warnings;
});

const visibleWarnings = computed(() => (props.serverWarnings?.length ? props.serverWarnings : validationWarnings.value));

const editableDays = computed<EditableDay[]>(() => normalizeDays(draft.value));

watch(
  () => props.plan,
  (plan) => {
    draft.value = clonePlan(plan);
    localWarning.value = "";
  },
  { immediate: true, deep: true },
);

function clonePlan(plan?: TravelPlan | null): TravelPlan {
  if (!plan) {
    return {
      days: 1,
      people_number: 1,
      itinerary: [{ day: 1, title: "第 1 天", activities: [] }],
    };
  }
  return JSON.parse(JSON.stringify(plan)) as TravelPlan;
}

function normalizeDays(plan: TravelPlan): EditableDay[] {
  const source = Array.isArray(plan.itinerary) ? plan.itinerary : [];
  const grouped = new Map<number, EditableDay>();

  for (const item of source) {
    const maybeDay = item as PlanDay;
    if (Array.isArray(maybeDay.activities)) {
      const dayNumber = Number(maybeDay.day || grouped.size + 1);
      grouped.set(dayNumber, {
        ...maybeDay,
        day: dayNumber,
        activities: maybeDay.activities.map((activity) => ({ ...activity, day: Number(activity.day || dayNumber) })),
      });
      continue;
    }

    const activity = item as FlatPlanActivity;
    const dayNumber = Number(activity.day || 1);
    const day = grouped.get(dayNumber) || { day: dayNumber, title: `第 ${dayNumber} 天`, activities: [] };
    day.activities.push({ ...activity, day: dayNumber });
    grouped.set(dayNumber, day);
  }

  return [...grouped.values()].sort((left, right) => Number(left.day || 0) - Number(right.day || 0));
}

function syncDays(days: EditableDay[]) {
  draft.value = {
    ...draft.value,
    days: days.length || draft.value.days,
    itinerary: days.map((day, index) => ({
      ...day,
      day: Number(day.day || index + 1),
      activities: (day.activities || []).map((activity) => ({
        ...activity,
        day: Number(day.day || index + 1),
      })),
    })),
  };
}

function patchPlan(field: keyof TravelPlan, value: string | number | string[] | undefined) {
  draft.value = { ...draft.value, [field]: value || undefined };
}

function patchDay(dayIndex: number, field: keyof PlanDay, value: string | number | undefined) {
  const days = editableDays.value.map((day) => ({ ...day, activities: [...day.activities] }));
  days[dayIndex] = { ...days[dayIndex], [field]: value || undefined };
  syncDays(days);
}

function patchActivity(dayIndex: number, activityIndex: number, field: keyof PlanActivity, value: string | number | undefined) {
  const days = editableDays.value.map((day) => ({ ...day, activities: day.activities.map((activity) => ({ ...activity })) }));
  days[dayIndex].activities[activityIndex] = {
    ...days[dayIndex].activities[activityIndex],
    [field]: value || undefined,
  };
  syncDays(days);
}

function addDay() {
  const days = editableDays.value.map((day) => ({ ...day, activities: [...day.activities] }));
  const nextDay = days.length + 1;
  days.push({ day: nextDay, title: `第 ${nextDay} 天`, summary: "", activities: [] });
  syncDays(days);
}

function removeDay(dayIndex: number) {
  const days = editableDays.value.filter((_, index) => index !== dayIndex).map((day, index) => ({
    ...day,
    day: index + 1,
    activities: day.activities.map((activity) => ({ ...activity, day: index + 1 })),
  }));
  syncDays(days.length ? days : [{ day: 1, title: "第 1 天", activities: [] }]);
}

function addActivity(dayIndex: number) {
  const days = editableDays.value.map((day) => ({ ...day, activities: day.activities.map((activity) => ({ ...activity })) }));
  const dayNumber = Number(days[dayIndex].day || dayIndex + 1);
  days[dayIndex].activities.push({
    day: dayNumber,
    type: "activity",
    title: "新活动",
    start_time: "09:30",
    end_time: "11:00",
    cost: 0,
  });
  syncDays(days);
}

function duplicateActivity(dayIndex: number, activityIndex: number) {
  const days = editableDays.value.map((day) => ({ ...day, activities: day.activities.map((activity) => ({ ...activity })) }));
  days[dayIndex].activities.splice(activityIndex + 1, 0, { ...days[dayIndex].activities[activityIndex] });
  syncDays(days);
}

function removeActivity(dayIndex: number, activityIndex: number) {
  const days = editableDays.value.map((day) => ({ ...day, activities: day.activities.map((activity) => ({ ...activity })) }));
  days[dayIndex].activities.splice(activityIndex, 1);
  syncDays(days);
}

function numericValue(event: Event) {
  const value = Number((event.target as HTMLInputElement).value);
  return Number.isFinite(value) ? value : undefined;
}

function textValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
}

function save(force = false) {
  if (validationWarnings.value.length && !force) {
    localWarning.value = "表单内容还不完整，请根据提示补齐；也可以选择仍然保存为带风险标记的新版本。";
    return;
  }
  localWarning.value = "";
  emit("save", clonePlan(draft.value), { validation_override: force });
}
</script>

<template>
  <div class="daily-itinerary-editor">
    <div class="editor-save-bar">
      <div>
        <span>表单化编辑</span>
        <strong>保存会创建新的手动编辑版本</strong>
      </div>
      <div class="editor-actions">
        <button class="secondary-action compact-editor-action" type="button" :disabled="busy" @click="addDay">
          <Plus :size="16" /> 添加天数
        </button>
        <button class="primary-action compact-editor-action" type="button" :disabled="busy" @click="save(false)">
          <Save :size="16" /> 保存新版
        </button>
      </div>
    </div>

    <p v-if="message" class="editor-message">{{ message }}</p>
    <div v-if="localWarning || visibleWarnings.length" class="editor-warning">
      <CircleAlert :size="18" />
      <div>
        <strong>{{ localWarning || "仍有字段需要确认" }}</strong>
        <span v-for="warning in visibleWarnings.slice(0, 4)" :key="warning">{{ warning }}</span>
        <button type="button" :disabled="busy" @click="save(true)">仍然保存为风险版本</button>
      </div>
    </div>

    <section class="editor-section">
      <h3>基础信息</h3>
      <div class="editor-field-grid">
        <label>
          <span>出发地</span>
          <input :value="draft.start_city || ''" @input="patchPlan('start_city', textValue($event))" />
        </label>
        <label>
          <span>目的地</span>
          <input :value="draft.target_city || ''" @input="patchPlan('target_city', textValue($event))" />
        </label>
        <label>
          <span>天数</span>
          <input :value="draft.days || editableDays.length" type="number" min="1" @input="patchPlan('days', numericValue($event))" />
        </label>
        <label>
          <span>人数</span>
          <input :value="draft.people_number || ''" type="number" min="1" @input="patchPlan('people_number', numericValue($event))" />
        </label>
        <label>
          <span>预算</span>
          <input :value="draft.budget || ''" type="number" min="0" @input="patchPlan('budget', numericValue($event))" />
        </label>
        <label>
          <span>总费用</span>
          <input :value="draft.total_cost || ''" type="number" min="0" @input="patchPlan('total_cost', numericValue($event))" />
        </label>
        <label class="editor-wide-field">
          <span>行程摘要</span>
          <textarea :value="draft.llm_summary || ''" rows="3" @input="patchPlan('llm_summary', textValue($event))" />
        </label>
      </div>
    </section>

    <section class="editor-section editor-days">
      <article v-for="(day, dayIndex) in editableDays" :key="`${day.day}-${dayIndex}`" class="editor-day-card">
        <div class="editor-day-head">
          <div>
            <span>第 {{ day.day || dayIndex + 1 }} 天</span>
            <input :value="day.title || ''" placeholder="当天标题" @input="patchDay(dayIndex, 'title', textValue($event))" />
          </div>
          <button class="mini-icon-button" type="button" :disabled="busy" aria-label="删除当天" @click="removeDay(dayIndex)">
            <Trash2 :size="15" />
          </button>
        </div>

        <div class="editor-field-grid">
          <label class="editor-wide-field">
            <span>当天摘要</span>
            <textarea :value="day.summary || ''" rows="2" @input="patchDay(dayIndex, 'summary', textValue($event))" />
          </label>
          <label>
            <span>住宿</span>
            <input :value="day.accommodation || ''" @input="patchDay(dayIndex, 'accommodation', textValue($event))" />
          </label>
          <label>
            <span>地点</span>
            <input :value="day.location || ''" @input="patchDay(dayIndex, 'location', textValue($event))" />
          </label>
        </div>

        <div class="activity-editor-list">
          <div class="activity-editor-head">
            <strong>活动安排</strong>
            <button class="secondary-action compact-editor-action" type="button" :disabled="busy" @click="addActivity(dayIndex)">
              <Plus :size="15" /> 添加活动
            </button>
          </div>

          <article v-for="(activity, activityIndex) in day.activities" :key="activityIndex" class="activity-editor-row">
            <select :value="activity.type || 'activity'" @change="patchActivity(dayIndex, activityIndex, 'type', textValue($event))">
              <option value="attraction">景点</option>
              <option value="restaurant">餐饮</option>
              <option value="accommodation">住宿</option>
              <option value="train">交通</option>
              <option value="activity">活动</option>
            </select>
            <input :value="activity.start_time || ''" placeholder="开始" @input="patchActivity(dayIndex, activityIndex, 'start_time', textValue($event))" />
            <input :value="activity.end_time || ''" placeholder="结束" @input="patchActivity(dayIndex, activityIndex, 'end_time', textValue($event))" />
            <input
              :value="activity.title || activity.position || ''"
              placeholder="地点或活动"
              @input="patchActivity(dayIndex, activityIndex, 'title', textValue($event))"
            />
            <input :value="activity.cost || ''" type="number" min="0" placeholder="费用" @input="patchActivity(dayIndex, activityIndex, 'cost', numericValue($event))" />
            <textarea
              :value="activity.description || activity.recommended_food || ''"
              rows="2"
              placeholder="说明 / 推荐菜 / 注意事项"
              @input="patchActivity(dayIndex, activityIndex, 'description', textValue($event))"
            />
            <div class="activity-row-actions">
              <button class="mini-icon-button" type="button" :disabled="busy" aria-label="复制活动" @click="duplicateActivity(dayIndex, activityIndex)">
                <CopyPlus :size="15" />
              </button>
              <button class="mini-icon-button" type="button" :disabled="busy" aria-label="删除活动" @click="removeActivity(dayIndex, activityIndex)">
                <Trash2 :size="15" />
              </button>
            </div>
          </article>
        </div>
      </article>
    </section>
  </div>
</template>
