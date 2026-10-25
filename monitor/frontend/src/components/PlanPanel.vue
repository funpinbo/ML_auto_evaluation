<script setup lang="ts">
import { computed } from 'vue'
import { state } from '../lib/store'
import PanelBox from './PanelBox.vue'

const plan = computed(() => state.plan.env?.data ?? null)
</script>

<template>
  <PanelBox title="Plan · Phase 진행률 (FR-002)" :src="state.plan" :span="6">
    <div v-if="plan" class="phases">
      <div v-for="ph in plan.phases" :key="ph.phase" class="phase" :class="{ current: ph.current }">
        <div class="row">
          <strong>{{ ph.phase }}</strong>
          <span class="muted">{{ ph.title }}</span>
          <span class="spacer"></span>
          <span>{{ ph.checked }} / {{ ph.total }}</span>
          <span class="pct">{{ ph.percent }}%</span>
        </div>
        <div class="bar big"><div :style="{ width: `${ph.percent}%`, background: ph.completed ? 'var(--green)' : 'var(--blue)' }"></div></div>
      </div>
    </div>
  </PanelBox>
</template>
