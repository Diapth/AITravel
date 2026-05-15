<script setup lang="ts">
import { CircleAlert, RotateCcw } from "lucide-vue-next";
import type { PlanVersionSummary } from "../services/planner";

defineProps<{
  versions: PlanVersionSummary[];
  currentVersionId?: string | null;
  busy?: boolean;
}>();

const emit = defineEmits<{
  restoreVersion: [versionId: string];
}>();

const sourceLabels: Record<string, string> = {
  ai_generated: "AI生成",
  ai_edit: "AI修改",
  manual_edit: "手动编辑",
  rollback: "回退",
  recommended: "推荐",
};

function sourceLabel(source: string) {
  return sourceLabels[source] || source;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
</script>

<template>
  <aside class="plan-version-timeline" aria-label="版本记录">
    <div class="panel-heading compact">
      <div>
        <span>版本记录</span>
        <h2>快照时间线</h2>
      </div>
    </div>

    <p v-if="!versions.length" class="panel-muted">暂无版本，生成或打开推荐后会出现。</p>
    <div v-else class="version-list">
      <article v-for="version in versions" :key="version.id" class="version-item" :class="{ active: version.id === currentVersionId }">
        <div class="version-dot" />
        <div class="version-copy">
          <strong>第 {{ version.version_number }} 版</strong>
          <span>{{ sourceLabel(version.source) }} · {{ formatDate(version.created_at) }}</span>
          <p>{{ version.summary || "完整行程快照" }}</p>
          <small v-if="version.validation_warnings?.length" class="version-risk">
            <CircleAlert :size="13" /> 风险标记 {{ version.validation_warnings.length }} 项
          </small>
          <small v-if="version.total_cost">预算合计 ¥{{ Math.round(version.total_cost).toLocaleString("zh-CN") }}</small>
        </div>
        <button
          class="mini-icon-button"
          type="button"
          :disabled="busy || version.id === currentVersionId"
          aria-label="回退到此版本"
          @click="emit('restoreVersion', version.id)"
        >
          <RotateCcw :size="15" />
        </button>
      </article>
    </div>
  </aside>
</template>
