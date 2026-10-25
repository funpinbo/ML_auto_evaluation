<script setup lang="ts">
import { computed } from 'vue'
import { duration, time } from '../lib/format'
import { state } from '../lib/store'
import PanelBox from './PanelBox.vue'

const m = computed(() => state.memory.env?.data ?? null)
const CASCADE: Record<string, string> = {
  none: '없음',
  unknown: '판정 불가',
  ltm: '1/3 LTM 갱신 필요',
  tasks: '2/3 Task 갱신 필요',
  plan: '3/3 Plan 갱신 필요',
}
const active = computed(() => m.value?.stm.status === 'active')
const val = (v: string | undefined) => (!v || v === 'none' ? '—' : v)
</script>

<template>
  <PanelBox title="메모리 상태 (FR-003)" :src="state.memory" :span="6">
    <dl v-if="m" class="kv two">
      <dt>STM</dt>
      <dd><span class="chip" :class="active ? 'ok' : 'muted'">{{ m.stm.status }}</span></dd>
      <dt>Task</dt><dd>{{ val(m.stm.task) }} <span v-if="m.stm.team !== 'none'" class="muted">[{{ m.stm.team }}]</span></dd>
      <dt>시작</dt><dd>{{ active ? time(m.stm.opened_at) : '—' }}</dd>
      <dt>경과</dt><dd>{{ duration(m.stm.elapsed_sec) }}</dd>
      <dt>LTM rev</dt><dd>{{ m.ltm_rev ?? '—' }} <span class="muted">(STM {{ m.last_merged_stm ?? '—' }} 까지 병합)</span></dd>
      <dt>Tasks rev</dt><dd>{{ m.tasks_rev ?? '—' }} <span class="muted">(LTM {{ m.synced_ltm_rev ?? '—' }} 반영)</span></dd>
      <dt>아카이브</dt><dd>{{ m.archive_count }}건</dd>
      <dt>미처리 cascade</dt>
      <dd><span class="chip" :class="m.pending_cascade === 'none' ? 'ok' : 'warn'">{{ CASCADE[m.pending_cascade] ?? m.pending_cascade }}</span></dd>
    </dl>
  </PanelBox>
</template>
