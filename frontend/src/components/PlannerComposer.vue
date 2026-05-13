<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import {
  Binoculars,
  Building2,
  Camera,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  Home,
  MapPin,
  Minus,
  Mountain,
  Plus,
  Send,
  Sparkles,
  WandSparkles,
  Trash2,
  Utensils,
  Users,
  Waves,
} from "lucide-vue-next";
import type { PlanRequest } from "../services/planner";
import { requestFieldExtraction } from "../services/planner";

defineProps<{
  disabled: boolean;
}>();

const emit = defineEmits<{
  "submit-plan": [payload: PlanRequest];
}>();

const form = reactive({
  query:
    "我想去桂林阳朔玩 4 天 3 晚，2 个人，想体验漓江竹筏、遇龙河骑行和当地美食，预算中等，帮我规划一个轻松休闲的行程。",
  start_city: "上海",
  target_city: "桂林, 阳朔",
  days: 4,
  people_number: 2,
  budget: 3400,
  budgetLabel: "中等预算（¥2,000 - ¥3,500 / 人）",
});

const budgetOptions = [
  { label: "经济预算（¥800 - ¥2,000 / 人）", budget: 2000 },
  { label: "中等预算（¥2,000 - ¥3,500 / 人）", budget: 3400 },
  { label: "舒适预算（¥3,500 - ¥5,500 / 人）", budget: 5200 },
];

const samples = [
  {
    label: "成都 3 天 2 晚 美食之旅",
    query: "从上海出发去成都 3 天 2 晚，2 个人，重点体验川菜、茶馆和宽窄巷子，预算中等。",
    start_city: "上海",
    target_city: "成都",
    days: 3,
    people_number: 2,
    budget: 3000,
    budgetLabel: "中等预算（¥2,000 - ¥3,500 / 人）",
  },
  {
    label: "云南大理 丽江 5 天 4 晚",
    query: "从上海出发去云南大理和丽江 5 天 4 晚，想看古城、洱海和雪山，节奏不要太赶。",
    start_city: "上海",
    target_city: "大理, 丽江",
    days: 5,
    people_number: 2,
    budget: 5200,
    budgetLabel: "舒适预算（¥3,500 - ¥5,500 / 人）",
  },
  {
    label: "厦门 4 天 3 晚 文艺之旅",
    query: "从上海去厦门 4 天 3 晚，2 个人，想去鼓浪屿、沙坡尾、环岛路，也想安排拍照打卡。",
    start_city: "上海",
    target_city: "厦门",
    days: 4,
    people_number: 2,
    budget: 4000,
    budgetLabel: "中等预算（¥2,000 - ¥3,500 / 人）",
  },
  {
    label: "西安 3 天 2 晚 历史文化之旅",
    query: "从上海去西安 3 天 2 晚，2 个人，想看兵马俑、城墙和博物馆，喜欢历史文化。",
    start_city: "上海",
    target_city: "西安",
    days: 3,
    people_number: 2,
    budget: 3200,
    budgetLabel: "中等预算（¥2,000 - ¥3,500 / 人）",
  },
];

const preferences = reactive([
  { label: "自然风光", icon: Mountain, active: true },
  { label: "休闲度假", icon: Home, active: false },
  { label: "美食体验", icon: Utensils, active: false },
  { label: "文化体验", icon: Building2, active: false },
  { label: "户外活动", icon: Waves, active: false },
  { label: "拍照打卡", icon: Camera, active: false },
  { label: "亲子家庭", icon: Users, active: false },
  { label: "当地生活", icon: Binoculars, active: false },
]);

const queryCount = computed(() => form.query.length);
const budgetMenuOpen = ref(false);
const isExtracting = ref(false);
const extractionMessage = ref("");

function applySample(sample: typeof samples[number]) {
  Object.assign(form, sample);
}

function clearForm() {
  form.query = "";
  form.start_city = "";
  form.target_city = "";
  form.days = 4;
  form.people_number = 2;
  form.budget = 3400;
  form.budgetLabel = "中等预算（¥2,000 - ¥3,500 / 人）";
  preferences.forEach((item, index) => {
    item.active = index === 0;
  });
}

function adjust(field: "days" | "people_number", amount: number) {
  const max = field === "days" ? 30 : 50;
  form[field] = Math.min(Math.max(form[field] + amount, 1), max);
}

function togglePreference(item: typeof preferences[number]) {
  item.active = !item.active;
}

function selectBudget(option: typeof budgetOptions[number]) {
  form.budget = option.budget;
  form.budgetLabel = option.label;
  budgetMenuOpen.value = false;
}

function budgetLabelForAmount(amount: number) {
  const matched = budgetOptions.find((option) => amount <= option.budget);
  return matched?.label || budgetOptions[budgetOptions.length - 1].label;
}

async function extractFields() {
  const query = form.query.trim();
  if (!query || isExtracting.value) return;

  isExtracting.value = true;
  extractionMessage.value = "";
  try {
    const data = await requestFieldExtraction(query);
    if (!data.success || !data.fields) {
      extractionMessage.value = data.error?.message || "智能填表失败，请稍后重试。";
      return;
    }

    const fields = data.fields;
    if (fields.start_city) form.start_city = fields.start_city;
    if (fields.target_city) form.target_city = fields.target_city;
    if (fields.days) form.days = fields.days;
    if (fields.people_number) form.people_number = fields.people_number;
    if (fields.budget) {
      form.budget = fields.budget;
      form.budgetLabel = budgetLabelForAmount(fields.budget);
    }
    if (fields.preferences?.length) {
      preferences.forEach((item) => {
        item.active = fields.preferences?.includes(item.label) ?? false;
      });
    }
    extractionMessage.value = "已根据自然语言更新下方字段";
  } catch (error) {
    extractionMessage.value = error instanceof Error ? error.message : "智能填表失败，请稍后重试。";
  } finally {
    isExtracting.value = false;
  }
}

function compactPayload(): PlanRequest {
  const selectedPreferences = preferences.filter((item) => item.active).map((item) => item.label);
  const queryWithPreferences =
    selectedPreferences.length > 0 ? `${form.query.trim()} 兴趣偏好：${selectedPreferences.join("、")}。` : form.query.trim();
  return Object.fromEntries(
    Object.entries({ ...form, query: queryWithPreferences })
      .filter(([key]) => key !== "budgetLabel")
      .map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])
      .filter(([, value]) => value !== "" && value !== null && value !== undefined),
  ) as unknown as PlanRequest;
}

function submit() {
  emit("submit-plan", compactPayload());
}
</script>

<template>
  <aside class="composer-card" aria-labelledby="composer-title">
    <div class="section-topline">
      <h2 id="composer-title">旅行需求</h2>
      <button class="ghost-action" type="button" :disabled="disabled" @click="clearForm">
        <Trash2 :size="16" />
        清空
      </button>
    </div>

    <el-form class="plan-form" label-position="top" @submit.prevent="submit">
      <el-form-item label="自然语言描述" required>
        <div class="prompt-box">
          <el-input
            v-model="form.query"
            type="textarea"
            :autosize="{ minRows: 8, maxRows: 12 }"
            resize="none"
            maxlength="500"
            placeholder="例如：我想去桂林阳朔玩 4 天 3 晚，2 个人，想体验漓江竹筏、遇龙河骑行和当地美食。"
            :disabled="disabled"
          />
          <div class="prompt-tools">
            <span class="magic-dot"><Sparkles :size="16" /></span>
            <span>{{ queryCount }}/500</span>
          </div>
        </div>
      </el-form-item>

      <button class="ai-fill-action" type="button" :disabled="disabled || isExtracting || !form.query.trim()" @click="extractFields">
        <span class="button-spinner" aria-hidden="true" />
        <WandSparkles :size="17" />
        <span>{{ isExtracting ? "正在整理字段" : "一键整理下方字段" }}</span>
      </button>
      <p v-if="extractionMessage" class="composer-inline-feedback" role="status">{{ extractionMessage }}</p>

      <div class="control-stack compact-control-grid">
        <el-form-item label="出发城市">
          <el-input v-model="form.start_city" :prefix-icon="MapPin" placeholder="上海" :disabled="disabled" clearable />
        </el-form-item>

        <el-form-item label="目的城市（可多选）">
          <el-input v-model="form.target_city" :prefix-icon="MapPin" placeholder="桂林, 阳朔" :disabled="disabled" clearable />
        </el-form-item>

        <el-form-item label="天数">
          <div class="stepper-field">
            <CalendarDays :size="19" />
            <span>{{ form.days }} 天 {{ Math.max(form.days - 1, 0) }} 晚</span>
            <button type="button" :disabled="disabled" @click="adjust('days', -1)"><Minus :size="15" /></button>
            <button type="button" :disabled="disabled" @click="adjust('days', 1)"><Plus :size="15" /></button>
          </div>
        </el-form-item>

        <el-form-item label="出行人数">
          <div class="stepper-field">
            <Users :size="19" />
            <span>{{ form.people_number }} 人</span>
            <button type="button" :disabled="disabled" @click="adjust('people_number', -1)"><Minus :size="15" /></button>
            <button type="button" :disabled="disabled" @click="adjust('people_number', 1)"><Plus :size="15" /></button>
          </div>
        </el-form-item>
      </div>

      <div class="control-stack">
        <el-form-item label="预算范围（人均）">
          <div class="budget-picker">
            <button class="select-like-field" type="button" :disabled="disabled" @click="budgetMenuOpen = !budgetMenuOpen">
              <CircleDollarSign :size="18" />
              <span>{{ form.budgetLabel }}</span>
              <ChevronRight :size="16" :class="{ rotated: budgetMenuOpen }" />
            </button>
            <div v-if="budgetMenuOpen" class="budget-menu">
              <button
                v-for="option in budgetOptions"
                :key="option.label"
                type="button"
                :class="{ active: option.label === form.budgetLabel }"
                @click="selectBudget(option)"
              >
                {{ option.label }}
              </button>
            </div>
          </div>
        </el-form-item>
      </div>

      <div class="preference-block" aria-label="兴趣偏好">
        <p>兴趣偏好（可多选）</p>
        <div class="preference-grid">
          <button
            v-for="item in preferences"
            :key="item.label"
            class="preference-chip"
            :class="{ active: item.active }"
            type="button"
            :disabled="disabled"
            @click="togglePreference(item)"
          >
            <component :is="item.icon" :size="15" />
            {{ item.label }}
          </button>
        </div>
      </div>

      <div class="sample-block" aria-label="推荐路线示例">
        <p>推荐路线示例</p>
        <div class="sample-grid">
          <button
            v-for="sample in samples"
            :key="sample.label"
            class="sample-button"
            type="button"
            :disabled="disabled"
            @click="applySample(sample)"
          >
            <span>{{ sample.label }}</span>
            <ChevronRight :size="16" />
          </button>
        </div>
      </div>

      <button class="primary-action" type="submit" :disabled="disabled || !form.query.trim()">
        <span class="button-spinner" aria-hidden="true" />
        <Sparkles :size="20" />
        <span>{{ disabled ? "模型生成中" : "生成行程" }}</span>
      </button>

      <div class="composer-footnote">
        <Send :size="15" />
        <span>由 DeepSeek-V2 提供智能生成</span>
      </div>
    </el-form>
  </aside>
</template>
