<script setup lang="ts">
import { computed } from 'vue'
import type { Slot } from '../lib/store'

const props = defineProps<{ title: string; src?: Slot<unknown>; span?: number }>()
const meta = computed(() => props.src?.env?.meta ?? null)
const badge = computed(() => {
  if (props.src?.failed) return { text: '연결 실패', cls: 'bad' }
  switch (meta.value?.status) {
    case 'partial': return { text: '일부', cls: 'warn' }
    case 'empty': return { text: '데이터 없음', cls: 'muted' }
    case 'error': return { text: '오류', cls: 'bad' }
    default: return null
  }
})
</script>

<template>
  <section class="panel" :style="{ gridColumn: `span ${span ?? 12}` }">
    <header>
      <h2>{{ title }}</h2>
      <span v-if="badge" class="badge" :class="badge.cls">{{ badge.text }}</span>
      <span v-if="src?.loading" class="spin" aria-label="불러오는 중"></span>
      <slot name="tools"></slot>
    </header>
    <div class="body">
      <p v-if="src?.failed" class="notice bad">{{ src.failed }}</p>
      <template v-else-if="src && !src.env">
        <p class="notice muted">불러오는 중…</p>
      </template>
      <template v-else>
        <p v-if="meta?.error && meta.status === 'error'" class="notice bad">{{ meta.error.message }}</p>
        <slot></slot>
        <ul v-if="meta?.warnings?.length" class="warnings">
          <li v-for="w in meta.warnings" :key="w">⚠ {{ w }}</li>
        </ul>
      </template>
    </div>
  </section>
</template>
