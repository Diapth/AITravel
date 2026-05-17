<script setup lang="ts">
import { MapPin, Sparkles } from "lucide-vue-next";
import type { RecommendationItem } from "../services/planner";

defineProps<{
  recommendations: RecommendationItem[];
  loading?: boolean;
}>();

const emit = defineEmits<{
  openRecommendation: [recommendationId: string];
}>();

function destinationLabel(item: RecommendationItem) {
  return item.plan.target_city || item.plan.target_cities?.join(" / ") || "精选路线";
}

function cardTheme(item: RecommendationItem) {
  const text = `${item.title} ${item.summary}`.toLowerCase();
  if (/山|水|湖|瀑|峡|溪|林|岳|峰|泉/.test(text)) return "nature";
  if (/城|街|楼|塔|桥|港|滩|都|市/.test(text)) return "city";
  if (/寺|庙|古|文|遗|迹|祠|院|陵|故/.test(text)) return "culture";
  return "nature";
}
</script>

<template>
  <aside class="recommended-plans" aria-label="推荐行程">
    <div class="panel-heading">
      <div>
        <span>灵感池</span>
        <h2>推荐行程</h2>
      </div>
      <Sparkles :size="21" />
    </div>

    <p v-if="loading" class="panel-muted">正在读取推荐行程...</p>
    <div v-else-if="!recommendations.length" class="recommendation-empty">
      <Sparkles :size="22" />
      <strong>暂无推荐</strong>
      <span>开始聊天后，这里会根据你的兴趣自动推荐相似行程。</span>
    </div>
    <div v-else class="recommendation-list">
      <button
        v-for="item in recommendations"
        :key="item.id"
        class="recommendation-card"
        :class="`card-theme-${cardTheme(item)}`"
        type="button"
        @click="emit('openRecommendation', item.id)"
      >
        <span class="recommendation-source">{{ item.source }}</span>
        <strong>{{ item.title }}</strong>
        <p>{{ item.summary }}</p>
        <small><MapPin :size="14" /> {{ destinationLabel(item) }}</small>
      </button>
    </div>
  </aside>
</template>
