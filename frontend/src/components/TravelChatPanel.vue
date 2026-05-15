<script setup lang="ts">
import { computed, ref } from "vue";
import { LoaderCircle, SendHorizontal, Sparkles } from "lucide-vue-next";
import type { ConversationMessage } from "../services/planner";

const props = defineProps<{
  messages: ConversationMessage[];
  mode: "empty_chat" | "plan_workspace";
  busy?: boolean;
  errorMessage?: string;
}>();

const emit = defineEmits<{
  sendMessage: [message: string];
}>();

const draft = ref("");

const placeholder = computed(() =>
  props.mode === "empty_chat" ? "告诉我你想去哪里、几天、预算和偏好..." : "继续告诉 AI：想加一天、换酒店、压缩预算或调整节奏...",
);

const examples = ["桂林阳朔 4 天 3 晚，两个人，想轻松一点", "成都三日美食游，预算人均 2500", "上海出发去苏州周末游，想要园林和咖啡"];

function submit() {
  const message = draft.value.trim();
  if (!message || props.busy) return;
  emit("sendMessage", message);
  draft.value = "";
}

function useExample(example: string) {
  draft.value = example;
}
</script>

<template>
  <section class="travel-chat-panel" aria-label="AI 旅行对话">
    <div class="panel-heading">
      <div>
        <span>{{ mode === "empty_chat" ? "第一步" : "继续创作" }}</span>
        <h2>{{ mode === "empty_chat" ? "和 AI 聊想去的地方" : "二次更新旅行攻略" }}</h2>
      </div>
      <Sparkles :size="21" />
    </div>

    <div class="chat-message-list" :class="{ empty: !messages.length }">
      <div v-if="!messages.length" class="chat-empty-copy">
        <strong>先用自然语言描述你的旅行。</strong>
        <span>不用填满表单，系统会把目的地、天数、预算和偏好整理成可版本化的行程。</span>
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
    </div>

    <p v-if="errorMessage" class="chat-error" role="alert">{{ errorMessage }}</p>

    <form class="chat-composer" @submit.prevent="submit">
      <textarea v-model="draft" :placeholder="placeholder" :disabled="busy" rows="3" />
      <button class="primary-action chat-submit" type="submit" :disabled="busy || !draft.trim()" :class="{ 'is-loading': busy }">
        <span class="button-spinner" />
        <LoaderCircle v-if="busy" :size="18" class="spin-icon" />
        <SendHorizontal v-else :size="18" />
        {{ mode === "empty_chat" ? "生成行程" : "提交修改" }}
      </button>
    </form>
  </section>
</template>
