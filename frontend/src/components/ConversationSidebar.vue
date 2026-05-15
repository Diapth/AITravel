<script setup lang="ts">
import { Archive, Clock3, Plus, RotateCcw } from "lucide-vue-next";
import type { ConversationSummary } from "../services/planner";

defineProps<{
  conversations: ConversationSummary[];
  currentConversationId?: string | null;
  loading?: boolean;
}>();

const emit = defineEmits<{
  newConversation: [];
  selectConversation: [conversationId: string];
  archiveConversation: [conversationId: string];
  restoreConversation: [conversationId: string];
}>();

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
</script>

<template>
  <aside class="conversation-sidebar" aria-label="历史规划">
    <div class="panel-heading">
      <div>
        <span>历史规划</span>
        <h2>行程档案</h2>
      </div>
      <button class="icon-button" type="button" aria-label="新建规划" @click="emit('newConversation')">
        <Plus :size="19" />
      </button>
    </div>

    <p v-if="loading" class="panel-muted">正在读取本地会话...</p>
    <div v-else-if="!conversations.length" class="sidebar-empty">
      <Clock3 :size="22" />
      <strong>还没有历史规划</strong>
      <span>从中间的对话框开始，生成后的行程会沉淀到这里。</span>
    </div>

    <div v-else class="conversation-list">
      <article
        v-for="item in conversations"
        :key="item.id"
        class="conversation-item"
        :class="{ active: item.id === currentConversationId, archived: item.status === 'archived' }"
      >
        <button type="button" class="conversation-main" @click="emit('selectConversation', item.id)">
          <strong>{{ item.title }}</strong>
          <span>{{ item.current_plan_summary || "暂无行程摘要" }}</span>
          <small>{{ formatDate(item.updated_at) }}</small>
        </button>
        <button
          v-if="item.status === 'archived'"
          class="mini-icon-button"
          type="button"
          aria-label="恢复规划"
          @click="emit('restoreConversation', item.id)"
        >
          <RotateCcw :size="15" />
        </button>
        <button
          v-else
          class="mini-icon-button"
          type="button"
          aria-label="归档规划"
          @click="emit('archiveConversation', item.id)"
        >
          <Archive :size="15" />
        </button>
      </article>
    </div>
  </aside>
</template>
