<script setup lang="ts">
import { computed, ref } from "vue";
import { CheckCircle2, ClipboardList, LoaderCircle, SendHorizontal, Sparkles } from "lucide-vue-next";
import type { ConversationGenerateRequest, ConversationMessage } from "../services/planner";

const props = defineProps<{
  messages: ConversationMessage[];
  mode: "empty_chat" | "plan_workspace";
  busy?: boolean;
  generatingPlan?: boolean;
  errorMessage?: string;
  planningChecklist?: ConversationGenerateRequest | null;
  checklistVisible?: boolean;
  checklistReady?: boolean;
  generatedCard?: {
    title: string;
    destination: string;
    days?: number | null;
    budget?: number | null;
    versionNumber?: number | null;
  } | null;
}>();

const emit = defineEmits<{
  sendMessage: [message: string];
  updateChecklist: [field: keyof ConversationGenerateRequest, value: string | number | boolean | string[] | null];
  confirmGenerate: [];
  openGeneratedPlan: [];
}>();

const draft = ref("");

const placeholder = computed(() =>
  props.mode === "empty_chat"
    ? "告诉我你想去哪里、想玩什么；预算、时间还不确定也可以先聊..."
    : "继续告诉 AI：想加一天、换酒店、压缩预算或调整节奏...",
);

const examples = [
  "我想找一个 4 天放松的山水目的地",
  "预算中等，想少走路，多吃当地菜",
  "从上海出发，周末想去江南园林和咖啡店",
];

const hasConversationContent = computed(
  () => props.messages.length > 0 || props.checklistVisible || props.generatedCard,
);

function submit() {
  const message = draft.value.trim();
  if (!message || props.busy) return;
  emit("sendMessage", message);
  draft.value = "";
}

function useExample(example: string) {
  draft.value = example;
}

function textValue(event: Event) {
  return (event.target as HTMLInputElement | HTMLTextAreaElement).value;
}

function numberValue(event: Event) {
  const value = Number((event.target as HTMLInputElement).value);
  return Number.isFinite(value) && value > 0 ? value : null;
}
</script>

<template>
  <section class="travel-chat-panel" aria-label="AI 旅行对话">
    <div class="panel-heading">
      <div>
        <span>{{ mode === "empty_chat" ? "第一步" : "继续创作" }}</span>
        <h2>{{ mode === "empty_chat" ? "和 AI 聊想去的地方" : "二次更新旅游攻略" }}</h2>
      </div>
      <Sparkles :size="21" />
    </div>

    <div class="chat-message-list" :class="{ empty: !hasConversationContent }">
      <div v-if="!messages.length" class="chat-empty-copy">
        <strong>先和 AI 把旅行意图聊清楚。</strong>
        <span>可以只说模糊想法，AI 会继续追问目的地、天数、预算、同行人和旅行节奏，信息足够后再给你确认清单。</span>
        <div class="chat-examples">
          <button v-for="item in examples" :key="item" type="button" @click="useExample(item)">
            {{ item }}
          </button>
        </div>
      </div>

      <article v-for="message in messages" :key="message.id" class="chat-message" :class="`is-${message.role}`">
        <span>{{ message.role === "user" ? "你" : "AI" }}</span>
        <p>{{ message.content }}</p>
      </article>

      <article v-if="checklistVisible && planningChecklist" class="planning-checklist-card">
        <div class="checklist-card-head">
          <ClipboardList :size="20" />
          <div>
            <span>规划清单确认</span>
            <strong>{{ checklistReady ? "信息已基本足够，可以生成" : "还可以继续补充，也可以先生成草案" }}</strong>
          </div>
        </div>

        <div class="checklist-grid">
          <label>
            <span>需求摘要</span>
            <textarea
              :value="planningChecklist.query"
              rows="2"
              @input="emit('updateChecklist', 'query', textValue($event))"
            />
          </label>
          <label>
            <span>目的地</span>
            <input
              :value="planningChecklist.target_city || ''"
              placeholder="例如 桂林 / 阳朔"
              @input="emit('updateChecklist', 'target_city', textValue($event))"
            />
          </label>
          <label>
            <span>出发地</span>
            <input
              :value="planningChecklist.start_city || ''"
              placeholder="例如 上海"
              @input="emit('updateChecklist', 'start_city', textValue($event))"
            />
          </label>
          <label>
            <span>天数</span>
            <input
              :value="planningChecklist.days || ''"
              type="number"
              min="1"
              max="30"
              @input="emit('updateChecklist', 'days', numberValue($event))"
            />
          </label>
          <label>
            <span>人数</span>
            <input
              :value="planningChecklist.people_number || ''"
              type="number"
              min="1"
              max="50"
              @input="emit('updateChecklist', 'people_number', numberValue($event))"
            />
          </label>
          <label>
            <span>预算</span>
            <input
              :value="planningChecklist.budget || ''"
              type="number"
              min="1"
              placeholder="总预算，元"
              @input="emit('updateChecklist', 'budget', numberValue($event))"
            />
          </label>
        </div>

        <button
          class="primary-action checklist-confirm"
          type="button"
          :disabled="generatingPlan || busy || !planningChecklist.query.trim()"
          :class="{ 'is-loading': generatingPlan }"
          @click="emit('confirmGenerate')"
        >
          <span class="button-spinner" />
          <LoaderCircle v-if="generatingPlan" :size="18" class="spin-icon" />
          <CheckCircle2 v-else :size="18" />
          确认清单并生成攻略
        </button>
      </article>

      <article v-if="generatedCard" class="generated-plan-card">
        <div class="checklist-card-head">
          <CheckCircle2 :size="21" />
          <div>
            <span>攻略已生成</span>
            <strong>{{ generatedCard.title }}</strong>
          </div>
        </div>
        <div class="generated-card-meta">
          <span>{{ generatedCard.destination }}</span>
          <span v-if="generatedCard.days">{{ generatedCard.days }} 天</span>
          <span v-if="generatedCard.budget">预算 ¥{{ Math.round(generatedCard.budget).toLocaleString("zh-CN") }}</span>
          <span v-if="generatedCard.versionNumber">第 {{ generatedCard.versionNumber }} 版</span>
        </div>
        <button class="secondary-action generated-open-action" type="button" @click="emit('openGeneratedPlan')">
          查看并编辑规划
        </button>
      </article>
    </div>

    <p v-if="errorMessage" class="chat-error" role="alert">{{ errorMessage }}</p>

    <form class="chat-composer" @submit.prevent="submit">
      <textarea v-model="draft" :placeholder="placeholder" :disabled="busy || generatingPlan" rows="3" />
      <button class="primary-action chat-submit" type="submit" :disabled="busy || generatingPlan || !draft.trim()" :class="{ 'is-loading': busy }">
        <span class="button-spinner" />
        <LoaderCircle v-if="busy" :size="18" class="spin-icon" />
        <SendHorizontal v-else :size="18" />
        {{ mode === "empty_chat" ? "发送" : "提交修改" }}
      </button>
    </form>
  </section>
</template>
