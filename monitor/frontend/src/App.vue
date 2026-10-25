<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import ControlPanel from './components/ControlPanel.vue'
import MemoryPanel from './components/MemoryPanel.vue'
import PipelinePanel from './components/PipelinePanel.vue'
import PlanPanel from './components/PlanPanel.vue'
import StatCard from './components/StatCard.vue'
import TasksPanel from './components/TasksPanel.vue'
import UsagePanel from './components/UsagePanel.vue'
import { connect, mode, warming } from './lib/events'
import { duration, levelColor, pct } from './lib/format'
import { refreshAll, refreshTopics, state } from './lib/store'

let disconnect: (() => void) | null = null
const now = ref(Date.now())
let tick: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  void refreshAll()
  disconnect = connect({ onChanged: (t) => void refreshTopics(t), onReconnect: () => void refreshAll() })
  tick = setInterval(() => (now.value = Date.now()), 1000)
})
onBeforeUnmount(() => {
  disconnect?.()
  if (tick) clearInterval(tick)
})

const pipeline = computed(() => state.pipeline.env?.data)
const plan = computed(() => state.plan.env?.data)
const memory = computed(() => state.memory.env?.data)
const usage = computed(() => state.usage.env?.data)
const control = computed(() => state.control.env?.data)
const currentPhase = computed(() => plan.value?.phases.find((p) => p.current) ?? null)
const five = computed(() => usage.value?.five_hour?.used_percentage ?? null)

// 경고 배너 (FR-010 최소): cascade 미처리, blocked Task, 한도 80% 이상
const alerts = computed(() => {
  const out: string[] = []
  if (memory.value && memory.value.pending_cascade !== 'none') out.push('미처리 메모리 cascade 가 있습니다 — Claude Code 가 먼저 처리해야 합니다.')
  const blocked = state.tasks.env?.data?.items.filter((t) => t.status === 'blocked').length ?? 0
  if (blocked) out.push(`막힌(blocked) Task ${blocked}개`)
  if (five.value !== null && five.value >= 80) out.push(`5시간 한도 사용률 ${Math.round(five.value)}% — 일시정지를 고려하세요.`)
  if ((usage.value?.seven_day?.used_percentage ?? 0) >= 80) out.push(`7일 한도 사용률 ${Math.round(usage.value!.seven_day!.used_percentage!)}%`)
  return out
})

const MODE_TEXT = { live: '실시간', polling: '5초 폴링', connecting: '연결 중' }
const updated = computed(() => (state.updatedAt ? `${Math.max(0, Math.round((now.value - state.updatedAt.getTime()) / 1000))}초 전 갱신` : ''))
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand"><span class="logo">◆</span> AI-DLC Monitor</div>
      <span class="muted small">funpinbo · 로컬 전용</span>
      <span class="spacer"></span>
      <span v-if="warming !== null" class="chip info">사용량 집계 중 {{ Math.round(warming * 100) }}%</span>
      <span class="chip" :class="mode === 'live' ? 'ok' : mode === 'polling' ? 'warn' : 'muted'">● {{ MODE_TEXT[mode] }}</span>
      <span class="muted small">{{ updated }}</span>
      <button class="btn ghost" title="모두 다시 읽기" @click="refreshAll()">⟳</button>
    </header>

    <div v-if="alerts.length" class="alerts" role="alert">
      <div v-for="a in alerts" :key="a">⚠ {{ a }}</div>
    </div>

    <main class="grid">
      <div class="kpis" style="grid-column: span 12">
        <StatCard
          label="파이프라인 단계"
          :value="pipeline ? `${pipeline.current_stage} · ${pipeline.current_stage_name}` : '—'"
          :sub="pipeline?.next_command ? `다음: ${pipeline.next_command}` : undefined"
          color="var(--blue)"
        />
        <StatCard
          :label="`Phase ${currentPhase?.phase ?? ''} 진행률`"
          :value="currentPhase ? `${currentPhase.percent}%` : '—'"
          :sub="currentPhase ? `${currentPhase.checked} / ${currentPhase.total} Task` : undefined"
          :percent="currentPhase?.percent ?? null"
          color="var(--green)"
        />
        <StatCard
          label="현재 Task"
          :value="memory?.stm.status === 'active' ? memory.stm.task : '대기'"
          :sub="memory?.stm.status === 'active' ? `[${memory.stm.team}] ${duration(memory.stm.elapsed_sec)} 경과` : 'STM idle'"
          :color="memory?.stm.status === 'active' ? 'var(--orange)' : 'var(--muted)'"
        />
        <StatCard
          label="5시간 한도"
          :value="pct(five)"
          :sub="usage && !usage.limits_available ? '한도 정보 없음' : undefined"
          :percent="five"
          :color="levelColor(five)"
        />
        <StatCard
          label="루프"
          :value="control?.label ?? '—'"
          :sub="control?.iterations_total != null ? `${control.iterations_done ?? 0} / ${control.iterations_total} 반복` : undefined"
          :color="control?.view === 'V2' ? 'var(--green)' : control?.view === 'V3' || control?.view === 'V4' ? 'var(--yellow)' : 'var(--muted)'"
        />
      </div>

      <PipelinePanel />
      <ControlPanel />
      <UsagePanel />
      <PlanPanel />
      <MemoryPanel />
      <TasksPanel />
    </main>
  </div>
</template>
