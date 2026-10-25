<script setup lang="ts">
import { computed, ref } from 'vue'
import { ApiError, postJson, type Control } from '../lib/api'
import { duration } from '../lib/format'
import { load, state } from '../lib/store'
import PanelBox from './PanelBox.vue'

const c = computed(() => state.control.env?.data ?? null)
const busy = ref(false)
const error = ref<string | null>(null)

const tone = computed(() => {
  switch (c.value?.view) {
    case 'V2': return 'green'
    case 'V3': case 'V4': return 'yellow'
    case 'V5': return 'blue'
    default: return 'muted'
  }
})

async function send(action: 'pause' | 'resume') {
  busy.value = true
  error.value = null
  try {
    const env = await postJson<Control>(`/control/${action}`)
    state.control.env = env
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : '요청을 보내지 못했습니다.'
    await load('control')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PanelBox title="루프 제어 (FR-005)" :src="state.control" :span="4">
    <template v-if="c">
      <div class="loop-state" :class="tone">{{ c.label }}</div>
      <p v-if="c.hint" class="muted">{{ c.hint }}</p>
      <p v-if="c.ended_message" class="muted">{{ c.ended_message }}</p>
      <dl class="kv">
        <template v-if="c.iterations_total !== null">
          <dt>반복</dt><dd>{{ c.iterations_done ?? 0 }} / {{ c.iterations_total }}</dd>
        </template>
        <template v-if="c.remaining_pause_sec !== null">
          <dt>자동 종료까지</dt><dd>{{ duration(c.remaining_pause_sec) }}</dd>
        </template>
        <template v-if="c.heartbeat_age_sec !== null">
          <dt>세션 신호</dt><dd>{{ duration(c.heartbeat_age_sec) }} 전</dd>
        </template>
      </dl>
      <div class="row gap">
        <button class="btn warn" :disabled="!c.can_pause || busy" @click="send('pause')">⏸ 일시정지</button>
        <button class="btn primary" :disabled="!c.can_resume || busy" @click="send('resume')">▶ 재개</button>
      </div>
      <p class="muted small">일시정지는 현재 Task 를 끝까지 마친 뒤(cascade 포함) 멈춥니다.</p>
      <p v-if="error" class="notice bad">{{ error }}</p>
    </template>
  </PanelBox>
</template>
