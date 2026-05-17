import { computed, ref } from "vue";
import {
  requestConversationDetail,
  requestPlan,
  restorePlanVersion,
  saveManualPlanEdit,
  type ConversationDetailResponse,
  type PlanVersionSummary,
  type TravelPlan,
} from "../services/planner";

export function usePlanWorkspace() {
  const plan = ref<TravelPlan | null>(null);
  const versions = ref<PlanVersionSummary[]>([]);
  const notice = ref("");
  const warnings = ref<string[]>([]);
  const conflict = ref<{ currentVersionId: string; baseVersionId: string } | null>(null);
  const busy = ref(false);

  const currentVersionId = computed(() => versions.value[0]?.id || null);

  function setFromDetail(detail: ConversationDetailResponse) {
    plan.value = detail.current_plan || null;
    versions.value = detail.versions || [];
    conflict.value = null;
  }

  async function restoreVersion(
    conversationId: string,
    versionId: string,
    onDetailReady: (detail: ConversationDetailResponse) => void,
  ) {
    notice.value = "";
    busy.value = true;
    try {
      const data = await restorePlanVersion(conversationId, versionId);
      if (!data.success) {
        notice.value = data.error?.message || "版本回退失败。";
        return;
      }
      const detail = await requestConversationDetail(conversationId);
      onDetailReady(detail);
    } finally {
      busy.value = false;
    }
  }

  async function saveManualEdit(
    conversationId: string,
    editPlan: TravelPlan,
    currentVersionId: string | null,
    onDetailReady: (detail: ConversationDetailResponse) => void,
    options: { validation_override?: boolean; conflict_override?: boolean } = {},
  ) {
    notice.value = "";
    warnings.value = [];
    busy.value = true;
    try {
      const data = await saveManualPlanEdit(conversationId, {
        plan: editPlan,
        base_version_id: currentVersionId,
        conflict_override: options.conflict_override || false,
        validation_override: options.validation_override || false,
      });
      if (!data.success) {
        notice.value = data.error?.message || "保存手动编辑失败。";
        if (data.error?.code === "PLAN_VALIDATION_FAILED" && Array.isArray(data.error.details?.warnings)) {
          warnings.value = data.error.details.warnings.filter((w): w is string => typeof w === "string");
        }
        if (data.error?.code === "VERSION_CONFLICT") {
          const details = data.error.details || {};
          conflict.value = {
            currentVersionId: String(details.current_version_id || ""),
            baseVersionId: String(details.base_version_id || currentVersionId || ""),
          };
          if (data.current_plan) plan.value = data.current_plan;
        }
        return;
      }
      const detail = await requestConversationDetail(conversationId);
      onDetailReady(detail);
      notice.value = `已保存第 ${data.version?.version_number || ""} 版手动编辑。`;
    } finally {
      busy.value = false;
    }
  }

  function reset() {
    plan.value = null;
    versions.value = [];
    notice.value = "";
    warnings.value = [];
    conflict.value = null;
  }

  return { plan, versions, notice, warnings, conflict, currentVersionId, setFromDetail, restoreVersion, saveManualEdit, reset };
}
