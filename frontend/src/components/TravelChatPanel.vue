<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { BubbleList, Thinking, XSender } from "vue-element-plus-x";
import { ArrowRight, CheckCircle2, ClipboardList, LoaderCircle, Sparkles } from "lucide-vue-next";
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

const fieldMissing = computed(() => {
  const c = props.planningChecklist;
  if (!c) return { destination: true, days: true, budgetOrPeople: true };
  return {
    destination: !(c.target_city || c.target_cities?.length),
    days: !c.days,
    budgetOrPeople: !(c.budget || c.people_number),
  };
});

interface XSenderInstance {
  clear: () => void;
  getModelValue: () => { text: string; html: string };
  setText: (value: string) => void;
}

type ChatListItemType = "message" | "thinking" | "checklist" | "generated-plan";
type PublicThinkingStatus = "thinking" | "end";

interface PublicThinkingRecord {
  id: string;
  status: PublicThinkingStatus;
  anchorMessageId?: string;
  startedAt: number;
}

interface ChatListItem {
  id: string;
  itemType: ChatListItemType;
  content: string;
  thinkingStatus?: PublicThinkingStatus;
  placement?: "start" | "end";
  variant?: "filled" | "outlined";
  shape?: "round";
  maxWidth?: string;
  avatarSize?: string;
  avatarGap?: string;
  avatarAlt?: string;
  role?: string;
}

const senderRef = ref<XSenderInstance | null>(null);
const inputText = ref("");
const activeThinking = ref<PublicThinkingRecord | null>(null);
const completedThinkingRecords = ref<PublicThinkingRecord[]>([]);

function onInputChange(value: string) {
  inputText.value = value;
}

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

const hasConversationContent = computed(() => props.messages.length > 0 || props.checklistVisible || props.generatedCard);
const senderDisabled = computed(() => Boolean(props.busy || props.generatingPlan));
const senderLoading = computed(() => Boolean(props.busy || props.generatingPlan));

const activeThinkingText = computed(() =>
  [
    "AI 正在整理你的旅行意图...",
    "- 理解你刚补充的目的地、时间和偏好",
    "- 检查是否已经足够生成确认清单",
    "- 组织一段更清楚的下一步回复",
  ].join("\n"),
);

function completedThinkingText() {
  return [
    "已完成本轮整理。",
    "- 提取了可用的旅行要素",
    "- 判断是否需要继续追问或展示确认清单",
    "- 将整理结果用于下面的回复",
  ].join("\n");
}

function thinkingContent(item: ChatListItem) {
  return item.thinkingStatus === "end" ? completedThinkingText() : activeThinkingText.value;
}

function lastAssistantMessage() {
  return [...props.messages].reverse().find((message) => message.role === "assistant");
}

function hasCompletedThinkingFor(messageId: string) {
  return completedThinkingRecords.value.some((record) => record.anchorMessageId === messageId);
}

function attachCompletedThinking(anchorMessageId?: string) {
  if (!activeThinking.value || !anchorMessageId || hasCompletedThinkingFor(anchorMessageId)) {
    activeThinking.value = null;
    return;
  }
  completedThinkingRecords.value = [
    ...completedThinkingRecords.value,
    {
      ...activeThinking.value,
      id: `thinking-complete-${anchorMessageId}`,
      status: "end" as const,
      anchorMessageId,
    },
  ].slice(-8);
  activeThinking.value = null;
}

watch(
  () => props.busy,
  (isBusy, wasBusy) => {
    if (isBusy && !wasBusy) {
      activeThinking.value = {
        id: `thinking-active-${Date.now()}`,
        status: "thinking",
        startedAt: Date.now(),
      };
      return;
    }
    if (!isBusy && wasBusy) {
      attachCompletedThinking(lastAssistantMessage()?.id);
    }
  },
);

watch(
  () => props.messages.map((message) => `${message.id}:${message.role}`).join("|"),
  () => {
    const validMessageIds = new Set(props.messages.map((message) => message.id));
    completedThinkingRecords.value = completedThinkingRecords.value.filter(
      (record) => record.anchorMessageId && validMessageIds.has(record.anchorMessageId),
    );
    if (activeThinking.value && !props.busy) {
      attachCompletedThinking(lastAssistantMessage()?.id);
    }
  },
);

const conversationItems = computed<ChatListItem[]>(() => {
  const completedByAnchor = new Map(
    completedThinkingRecords.value
      .filter((record) => record.anchorMessageId)
      .map((record) => [record.anchorMessageId, record]),
  );
  const items: ChatListItem[] = [];

  for (const message of props.messages) {
    const isUser = message.role === "user";

    if (!isUser) {
      const completedThinking = completedByAnchor.get(message.id);
      if (completedThinking) {
        items.push({
          id: completedThinking.id,
          itemType: "thinking",
          content: completedThinkingText(),
          thinkingStatus: "end",
        });
      }
    }

    items.push({
      id: message.id,
      itemType: "message" as const,
      content: message.content,
      placement: isUser ? ("end" as const) : ("start" as const),
      variant: isUser ? ("filled" as const) : ("outlined" as const),
      shape: "round" as const,
      maxWidth: "78%",
      avatarSize: "32px",
      avatarGap: "10px",
      avatarAlt: isUser ? "用户头像" : "AI 头像",
      role: message.role,
    });
  }

  if (props.busy && activeThinking.value) {
    items.push({
      id: activeThinking.value.id,
      itemType: "thinking",
      content: activeThinkingText.value,
      thinkingStatus: "thinking",
    });
  }

  if (props.checklistVisible && props.planningChecklist) {
    items.push({
      id: "planning-checklist",
      itemType: "checklist",
      content: "规划清单确认",
    });
  }

  if (props.generatedCard) {
    items.push({
      id: "generated-plan",
      itemType: "generated-plan",
      content: props.generatedCard.title,
    });
  }

  return items;
});

const bottomStatus = computed(() => {
  if (props.generatingPlan) {
    return { type: "loading" as const, text: "正在生成攻略..." };
  }
  return null;
});

function submit() {
  const message = senderRef.value?.getModelValue().text.trim() ?? "";
  if (!message || senderDisabled.value) return;
  emit("sendMessage", message);
  senderRef.value?.clear();
}

function useExample(example: string) {
  senderRef.value?.setText(example);
}

function bubbleLabel(item: ChatListItem) {
  return item.role === "user" ? "你" : "AI 旅行助手";
}

function bubbleAvatar(item: ChatListItem) {
  return item.role === "user" ? "你" : "AI";
}

function updateChecklistText(field: keyof ConversationGenerateRequest, value: string) {
  emit("updateChecklist", field, value);
}

function updateChecklistNumber(field: keyof ConversationGenerateRequest, value: number | null | undefined) {
  emit("updateChecklist", field, optionalNumberValue(value));
}

function optionalNumberValue(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : null;
}

function renderMarkdown(content: string) {
  const escaped = content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  const withInline = escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
  const lines = withInline.split(/\n+/);
  const html: string[] = [];
  let inList = false;
  for (const line of lines) {
    const listMatch = line.match(/^\s*[-*]\s+(.+)$/);
    if (listMatch) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${listMatch[1]}</li>`);
      continue;
    }
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
    if (line.trim()) html.push(`<p>${line}</p>`);
  }
  if (inList) html.push("</ul>");
  return html.join("");
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
      <div v-if="!hasConversationContent" class="chat-empty-copy">
        <el-empty description="先和 AI 把旅行意图聊清楚">
          <template #image>
            <Sparkles :size="42" />
          </template>
          <p>可以只说模糊想法，AI 会继续追问目的地、天数、预算、同行人和旅行节奏，信息足够后再给你确认清单。</p>
        </el-empty>
        <el-space class="chat-examples" wrap alignment="center">
          <el-button v-for="item in examples" :key="item" type="primary" plain round size="small" @click="useExample(item)">
            {{ item }}
          </el-button>
        </el-space>
      </div>

      <BubbleList
        v-else
        class="epx-chat-list"
        :list="conversationItems"
        item-key="id"
        item-type="itemType"
        :auto-scroll="true"
        :smooth-scroll="true"
        :always-show-scrollbar="true"
        :show-back-button="true"
        :bottom-status="bottomStatus"
        btn-color="var(--jade)"
        :btn-icon-size="18"
      >
        <template #avatar="{ item }">
          <span class="chat-avatar" :class="{ 'is-user': item.role === 'user' }">
            {{ bubbleAvatar(item) }}
          </span>
        </template>

        <template #header="{ item }">
          <span class="chat-bubble-label">{{ bubbleLabel(item) }}</span>
        </template>

        <template #content="{ item }">
          <div v-if="item.role === 'assistant'" class="chat-bubble-content markdown-body" v-html="renderMarkdown(item.content)" />
          <p v-else class="chat-bubble-content">{{ item.content }}</p>
        </template>

        <template #item="{ item }">
          <div
            v-if="item.itemType === 'thinking'"
            class="thinking-progress-wrapper"
            :class="{ 'is-complete': item.thinkingStatus === 'end' }"
          >
            <span class="chat-avatar" aria-hidden="true">AI</span>
            <div class="thinking-progress-bubble">
              <Thinking
                :content="thinkingContent(item)"
                :status="item.thinkingStatus || 'thinking'"
                :model-value="true"
                :auto-collapse="false"
                button-width="100%"
                max-width="420px"
              >
                <template #label>
                  <span>{{ item.thinkingStatus === "end" ? "思考完成" : "思考中..." }}</span>
                </template>
                <template #content>
                  <div class="thinking-progress-content markdown-body" v-html="renderMarkdown(thinkingContent(item))" />
                </template>
              </Thinking>
            </div>
          </div>
          <el-card v-else-if="item.itemType === 'checklist' && planningChecklist" class="planning-checklist-card chat-business-item" shadow="never">
            <template #header>
              <div class="checklist-card-head">
                <ClipboardList :size="20" />
                <div>
                  <span>规划清单确认</span>
                  <strong>{{ checklistReady ? "信息已基本足够，可以生成" : "还可以继续补充，也可以先生成草案" }}</strong>
                </div>
              </div>
            </template>

            <el-form class="checklist-grid" label-position="top">
              <el-form-item class="checklist-wide-field" label="需求摘要">
                <el-input
                  :model-value="planningChecklist.query"
                  type="textarea"
                  :autosize="{ minRows: 1, maxRows: 3 }"
                  resize="none"
                  @update:model-value="updateChecklistText('query', $event)"
                />
              </el-form-item>
              <el-form-item label="目的地">
                <template #label>
                  <span class="checklist-label-row">
                    目的地
                    <span v-if="fieldMissing.destination" class="checklist-required-dot" aria-label="必填项未填写" />
                  </span>
                </template>
                <el-input
                  :model-value="planningChecklist.target_city || ''"
                  placeholder="例如 桂林 / 阳朔"
                  clearable
                  @update:model-value="updateChecklistText('target_city', $event)"
                />
              </el-form-item>
              <el-form-item label="出发地">
                <el-input
                  :model-value="planningChecklist.start_city || ''"
                  placeholder="例如 上海"
                  clearable
                  @update:model-value="updateChecklistText('start_city', $event)"
                />
              </el-form-item>
              <el-form-item label="天数">
                <template #label>
                  <span class="checklist-label-row">
                    天数
                    <span v-if="fieldMissing.days" class="checklist-required-dot" aria-label="必填项未填写" />
                  </span>
                </template>
                <el-input-number
                  :model-value="planningChecklist.days"
                  :min="1"
                  :max="30"
                  controls-position="right"
                  @update:model-value="updateChecklistNumber('days', $event)"
                />
              </el-form-item>
              <el-form-item label="人数">
                <el-input-number
                  :model-value="planningChecklist.people_number"
                  :min="1"
                  :max="50"
                  controls-position="right"
                  @update:model-value="updateChecklistNumber('people_number', $event)"
                />
              </el-form-item>
              <el-form-item label="预算">
                <template #label>
                  <span class="checklist-label-row">
                    预算
                    <span v-if="fieldMissing.budgetOrPeople" class="checklist-required-dot" aria-label="必填项未填写（预算或人数）" />
                  </span>
                </template>
                <el-input-number
                  :model-value="planningChecklist.budget"
                  :min="1"
                  placeholder="总预算，元"
                  controls-position="right"
                  @update:model-value="updateChecklistNumber('budget', $event)"
                />
              </el-form-item>
            </el-form>

            <div class="checklist-actions">
              <el-button
                class="checklist-confirm"
                :class="{ 'checklist-confirm--ready': checklistReady }"
                type="primary"
                :disabled="generatingPlan || busy || !checklistReady"
                :loading="generatingPlan"
                :loading-icon="LoaderCircle"
                @click="emit('confirmGenerate')"
              >
                <CheckCircle2 v-if="!generatingPlan" :size="18" />
                确认清单并生成攻略
              </el-button>
              <button
                v-if="!checklistReady"
                class="checklist-skip-link"
                type="button"
                :disabled="generatingPlan || busy"
                @click="emit('confirmGenerate')"
              >
                跳过，直接生成 <ArrowRight :size="14" />
              </button>
            </div>
          </el-card>

          <el-card v-else-if="item.itemType === 'generated-plan' && generatedCard" class="generated-plan-card chat-business-item" shadow="never">
            <template #header>
              <div class="checklist-card-head">
                <CheckCircle2 :size="21" />
                <div>
                  <span>攻略已生成</span>
                  <strong>{{ generatedCard.title }}</strong>
                </div>
              </div>
            </template>
            <el-space class="generated-card-meta" wrap>
              <el-tag type="primary" effect="light" round disable-transitions>{{ generatedCard.destination }}</el-tag>
              <el-tag v-if="generatedCard.days" type="success" effect="light" round disable-transitions>{{ generatedCard.days }} 天</el-tag>
              <el-tag v-if="generatedCard.budget" type="warning" effect="light" round disable-transitions>
                预算 ¥{{ Math.round(generatedCard.budget).toLocaleString("zh-CN") }}
              </el-tag>
              <el-tag v-if="generatedCard.versionNumber" type="info" effect="light" round disable-transitions>
                第 {{ generatedCard.versionNumber }} 版
              </el-tag>
            </el-space>
            <el-button class="generated-open-action" type="primary" plain @click="emit('openGeneratedPlan')">
              查看并编辑规划
            </el-button>
          </el-card>
        </template>
      </BubbleList>
    </div>

    <el-alert v-if="errorMessage" class="chat-error" type="error" :title="errorMessage" show-icon :closable="false" />

    <div class="chat-composer">
      <XSender
        ref="senderRef"
        class="epx-sender"
        :placeholder="placeholder"
        device="auto"
        variant="updown"
        submit-type="enter"
        :max-length="900"
        :loading="senderLoading"
        :disabled="senderDisabled"
        clearable
        @submit="submit"
      />
    </div>
  </section>
</template>
