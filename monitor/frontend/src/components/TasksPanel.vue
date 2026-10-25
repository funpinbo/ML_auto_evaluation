<script setup lang="ts">
import { computed, ref } from 'vue'
import { state } from '../lib/store'
import PanelBox from './PanelBox.vue'

const items = computed(() => state.tasks.env?.data?.items ?? [])
const team = ref('')
const status = ref('')
const phase = ref('')
const teams = computed(() => [...new Set(items.value.map((t) => t.team))].sort())
const statuses = computed(() => [...new Set(items.value.map((t) => t.status))].sort())
const phases = computed(() => [...new Set(items.value.map((t) => t.phase))].sort())
const shown = computed(() =>
  items.value.filter((t) => (!team.value || t.team === team.value) && (!status.value || t.status === status.value) && (!phase.value || t.phase === phase.value)),
)
const STATUS_TEXT: Record<string, string> = { done: '완료', active: '진행 중', open: '대기', blocked: '막힘' }
</script>

<template>
  <PanelBox title="Task 목록 (FR-002)" :src="state.tasks" :span="12">
    <template #tools>
      <span class="spacer"></span>
      <select v-model="phase" aria-label="Phase"><option value="">모든 Phase</option><option v-for="p in phases" :key="p">{{ p }}</option></select>
      <select v-model="team" aria-label="팀"><option value="">모든 팀</option><option v-for="t in teams" :key="t">{{ t }}</option></select>
      <select v-model="status" aria-label="상태"><option value="">모든 상태</option><option v-for="s in statuses" :key="s" :value="s">{{ STATUS_TEXT[s] ?? s }}</option></select>
      <span class="muted small">{{ shown.length }} / {{ items.length }}</span>
    </template>
    <div class="table-wrap">
      <table>
        <thead><tr><th>ID</th><th>Phase</th><th>팀</th><th>상태</th><th>제목</th><th>의존</th></tr></thead>
        <tbody>
          <tr v-for="t in shown" :key="t.id" :class="t.status">
            <td><code>{{ t.id }}</code></td>
            <td>{{ t.phase }}</td>
            <td><span class="chip team">{{ t.team }}</span></td>
            <td><span class="chip" :class="t.status === 'done' ? 'ok' : t.status === 'blocked' ? 'bad' : t.status === 'active' ? 'info' : 'muted'">{{ STATUS_TEXT[t.status] ?? t.status }}</span></td>
            <td class="title" :title="t.title">{{ t.title }}</td>
            <td class="muted small">{{ t.deps.join(', ') || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </PanelBox>
</template>
