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
    <div v-else class="recommendation-list">
      <button
        v-for="item in recommendations"
        :key="item.id"
        class="recommendation-card"
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
