<script setup lang="ts">
import { computed } from 'vue'
import { state } from '../lib/store'
import PanelBox from './PanelBox.vue'

const p = computed(() => state.pipeline.env?.data ?? null)
const STAGE_TEXT: Record<string, string> = { done: '완료', in_progress: '진행', waiting: '대기', unknown: '알 수 없음' }
</script>

<template>
  <PanelBox title="파이프라인 단계 (FR-001)" :src="state.pipeline" :span="8">
    <template v-if="p">
      <ol class="stages">
        <li v-for="s in p.stages" :key="s.index" :class="[s.state, { current: s.index === p.current_stage }]">
          <span class="dot">{{ s.state === 'done' ? '✓' : s.index }}</span>
          <span class="name">{{ s.name }}</span>
          <code>{{ s.command }}</code>
          <span class="state">{{ STAGE_TEXT[s.state] ?? s.state }}</span>
        </li>
      </ol>
      <div class="row gap">
        <span class="muted">다음 명령</span>
        <code class="next">{{ p.all_done ? '모든 단계 완료' : p.next_command ?? '—' }}</code>
        <span class="spacer"></span>
        <span v-for="g in p.gates" :key="g.layer" class="chip" :class="g.result === 'PASS' ? 'ok' : g.result === 'FAIL' ? 'bad' : 'muted'">
          {{ g.layer }} Gate {{ g.result ?? '—' }}<template v-if="g.result === 'FAIL'"> · 미작성 {{ g.unwritten }} · 누락 {{ g.missing }}</template>
        </span>
      </div>
    </template>
  </PanelBox>
</template>
