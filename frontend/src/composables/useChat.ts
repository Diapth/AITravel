import { computed, ref } from "vue";
import {
  createConversation,
  generateConversationPlan,
  requestConversationDetail,
  requestTripIntentReadiness,
  sendConversationMessage,
  type ConversationDetailResponse,
  type ConversationGenerateRequest,
  type ConversationMessage,
  type ConversationSummary,
} from "../services/planner";

export function useChat() {
  const messages = ref<ConversationMessage[]>([]);
  const busy = ref(false);
  const error = ref("");
  const checklist = ref<ConversationGenerateRequest>({ query: "" });
  const checklistVisible = ref(false);
  const generatedCard = ref<{
    title: string;
    destination: string;
    days?: number | null;
    budget?: number | null;
    versionNumber?: number | null;
  } | null>(null);
  const isChecklistGenerating = ref(false);

  const checklistReady = computed(() => {
    const c = checklist.value;
    return Boolean((c.target_city || c.target_cities?.length) && c.days && (c.budget || c.people_number));
  });

  function inferChecklistFromMessages(items: ConversationMessage[]): ConversationGenerateRequest {
    const text = items.map((item) => item.content).join(" ");
    const daysMatch = text.match(/(\d+)\s*(天|日)/);
    const peopleMatch = text.match(/(\d+)\s*(个人|人|位)/);
    const budgetMatch = text.match(/(?:预算|人均|总预算)[^\d]*(\d{3,6})|(\d{3,6})\s*(元|块)/);
    const knownCities = [
      "北京", "上海", "苏州", "杭州", "成都", "重庆", "桂林", "阳朔",
      "广州", "深圳", "西安", "南京", "厦门", "青岛", "大理", "丽江",
    ];
    const targetCities = knownCities.filter((city) => text.includes(city));
    const target_city = targetCities.length ? targetCities.join("、") : checklist.value.target_city;

    return {
      ...checklist.value,
      query: checklist.value.query || items.find((item) => item.role === "user")?.content || text || "",
      target_city,
      target_cities: targetCities.length ? targetCities : checklist.value.target_cities,
      days: checklist.value.days || (daysMatch ? Number(daysMatch[1]) : undefined),
      people_number: checklist.value.people_number || (peopleMatch ? Number(peopleMatch[1]) : undefined),
      budget: checklist.value.budget || (budgetMatch ? Number(budgetMatch[1] || budgetMatch[2]) : undefined),
    };
  }

  function shouldShowChecklist(message: string, items: ConversationMessage[]) {
    const text = `${items.map((item) => item.content).join(" ")} ${message}`;
    const wantsGenerate = /生成|做一版|出一版|安排一下|规划一下|给我一份|确认生成/.test(message);
    const hasDestination = /北京|上海|苏州|杭州|成都|重庆|桂林|阳朔|广州|深圳|西安|南京|厦门|青岛|大理|丽江/.test(text);
    const hasDays = /\d+\s*(天|日)/.test(text);
    const hasBudgetOrPeople = /预算|人均|总预算|\d+\s*(个人|人|位)/.test(text);
    return (wantsGenerate && hasDestination && hasDays) || (hasDestination && hasDays && hasBudgetOrPeople);
  }

  function updateChecklist(field: keyof ConversationGenerateRequest, value: string | number | boolean | string[] | null) {
    checklist.value = {
      ...checklist.value,
      [field]: value || undefined,
    };
  }

  function completionCard(conversation: ConversationSummary | null, plan: { target_city?: string; target_cities?: string[]; days?: number; budget?: number; total_cost?: number } | null | undefined, versionNumber?: number | null) {
    if (!conversation || !plan) return null;
    return {
      title: conversation.title,
      destination: plan.target_city || plan.target_cities?.join("、") || "待确认目的地",
      days: plan.days,
      budget: plan.budget || plan.total_cost,
      versionNumber,
    };
  }

  async function sendMessage(
    message: string,
    currentConversation: ConversationSummary | null,
    onDetailReady: (detail: ConversationDetailResponse) => void,
  ) {
    error.value = "";
    generatedCard.value = null;

    const optimisticId = `temp-${Date.now()}`;
    const optimisticMessage: ConversationMessage = {
      id: optimisticId,
      conversation_id: currentConversation?.id || "",
      sequence: -1,
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };
    messages.value = [...messages.value, optimisticMessage];

    busy.value = true;
    try {
      const detail = currentConversation
        ? await sendConversationMessage(currentConversation.id, message, { base_version_id: currentConversation.current_version_id })
        : await createConversation(message);

      if (!detail.success) {
        error.value = detail.error?.message || "发送失败，请稍后重试。";
        messages.value = messages.value.filter((m) => m.id !== optimisticId);
        if ("message" in detail && detail.message) messages.value = [...messages.value, detail.message];
        return null;
      }

      if ("versions" in detail) {
        onDetailReady(detail);
      } else if (currentConversation) {
        const refreshed = await requestConversationDetail(currentConversation.id);
        onDetailReady(refreshed);
      }

      const inferredChecklist = inferChecklistFromMessages(messages.value);
      checklist.value = inferredChecklist;
      try {
        const readiness = await requestTripIntentReadiness({
          latest_message: message,
          messages: messages.value,
          current_fields: inferredChecklist,
        });
        if (readiness.success && readiness.readiness) {
          checklist.value = {
            ...inferredChecklist,
            ...readiness.readiness.fields,
            query: readiness.readiness.fields?.query || inferredChecklist.query || message,
          };
          checklistVisible.value = readiness.readiness.should_show_checklist;
        } else {
          checklistVisible.value = shouldShowChecklist(message, messages.value);
        }
      } catch {
        checklistVisible.value = shouldShowChecklist(message, messages.value);
      }
      return detail;
    } catch {
      messages.value = messages.value.filter((m) => m.id !== optimisticId);
      error.value = "发送失败，请稍后重试。";
      return null;
    } finally {
      busy.value = false;
    }
  }

  async function confirmGenerate(
    currentConversation: ConversationSummary,
    onDetailReady: (detail: ConversationDetailResponse) => void,
    onProgress: (isRunning: boolean) => void,
    currentPlanGetter: () => any,
  ) {
    error.value = "";
    generatedCard.value = null;
    isChecklistGenerating.value = true;
    const payload = {
      ...checklist.value,
      query: checklist.value.query || currentConversation.title,
    };
    onProgress(true);
    try {
      const data = await generateConversationPlan(currentConversation.id, payload);
      if (!data.success) {
        error.value = data.error?.message || "生成攻略失败，请稍后重试。";
        return;
      }
      const refreshed = await requestConversationDetail(currentConversation.id);
      onDetailReady(refreshed);
      generatedCard.value = completionCard(currentConversation, refreshed.current_plan, data.version?.version_number);
      checklistVisible.value = false;
    } finally {
      isChecklistGenerating.value = false;
      onProgress(false);
    }
  }

  function reset() {
    messages.value = [];
    error.value = "";
    checklist.value = { query: "" };
    checklistVisible.value = false;
    generatedCard.value = null;
    isChecklistGenerating.value = false;
  }

  return {
    messages,
    busy,
    error,
    checklist,
    checklistVisible,
    checklistReady,
    isChecklistGenerating,
    generatedCard,
    inferChecklistFromMessages,
    shouldShowChecklist,
    updateChecklist,
    sendMessage,
    confirmGenerate,
    reset,
  };
}
