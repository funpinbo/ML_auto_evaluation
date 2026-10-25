<script setup lang="ts">
defineProps<{ label: string; value: string; sub?: string; color?: string; percent?: number | null }>()
</script>

<template>
  <div class="stat">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value" :style="{ color: color ?? 'var(--text)' }">{{ value }}</div>
    <div v-if="percent !== undefined && percent !== null" class="bar"><div :style="{ width: `${Math.min(100, percent)}%`, background: color ?? 'var(--blue)' }"></div></div>
    <div v-if="sub" class="stat-sub">{{ sub }}</div>
  </div>
</template>
