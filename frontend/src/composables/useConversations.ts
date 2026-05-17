import { ref } from "vue";
import {
  archiveConversation,
  requestConversationDetail,
  requestConversations,
  restoreConversation,
  type ConversationDetailResponse,
  type ConversationSummary,
} from "../services/planner";

export function useConversations() {
  const list = ref<ConversationSummary[]>([]);
  const current = ref<ConversationSummary | null>(null);
  const loading = ref(false);

  function applyDetail(detail: ConversationDetailResponse) {
    if (!detail.success) {
      return;
    }
    current.value = detail.conversation || null;
  }

  async function refreshList() {
    loading.value = true;
    try {
      const data = await requestConversations();
      if (data.success) list.value = data.conversations;
    } finally {
      loading.value = false;
    }
  }

  async function select(conversationId: string) {
    loading.value = true;
    try {
      const detail = await requestConversationDetail(conversationId);
      return detail;
    } finally {
      loading.value = false;
    }
  }

  async function archive(conversationId: string) {
    const detail = await archiveConversation(conversationId);
    if (current.value?.id === conversationId) {
      current.value = detail.conversation || null;
    }
    await refreshList();
    return detail;
  }

  async function restore(conversationId: string) {
    const detail = await restoreConversation(conversationId);
    current.value = detail.conversation || null;
    await refreshList();
    return detail;
  }

  return { list, current, loading, select, archive, restore, refreshList, applyDetail };
}
