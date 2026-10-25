<script setup lang="ts">
import { computed } from 'vue'
import { PALETTE } from '../lib/chart'
import { levelColor, num, pct, relative, time } from '../lib/format'
import { load, state } from '../lib/store'
import EChart from './EChart.vue'
import PanelBox from './PanelBox.vue'

const u = computed(() => state.usage.env?.data ?? null)
const ts = computed(() => state.series.env?.data ?? null)
const RANGES = ['5h', '24h', '7d', '30d'] as const

function setRange(r: (typeof RANGES)[number]) {
  state.range = r
  void load('series')
}

function gauge(title: string, value: number | null | undefined) {
  const v = value ?? 0
  return {
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: '95%',
        progress: { show: true, width: 14, itemStyle: { color: value == null ? '#555' : v >= 80 ? '#f2495c' : v >= 60 ? '#f2cc0c' : '#73bf69' } },
        axisLine: { lineStyle: { width: 14, color: [[1, '#2c3235']] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        anchor: { show: false },
        title: { show: true, offsetCenter: [0, '38%'], color: '#9fa7b3', fontSize: 12 },
        detail: { valueAnimation: true, offsetCenter: [0, '-5%'], fontSize: 26, color: '#d8d9da', formatter: value == null ? '—' : '{value}%' },
        data: [{ value: Math.round(v), name: title }],
      },
    ],
  }
}

const g5 = computed(() => gauge('5시간 한도', u.value?.five_hour?.used_percentage))
const g7 = computed(() => gauge('7일 한도', u.value?.seven_day?.used_percentage))

const chart = computed(() => {
  const d = ts.value
  if (!d) return {}
  const daily = d.bucket === 'day'
  const labels = d.buckets.map((b) => {
    const t = new Date(b)
    return daily ? `${t.getMonth() + 1}/${t.getDate()}` : `${String(t.getHours()).padStart(2, '0')}:00`
  })
  return {
    color: PALETTE,
    grid: { left: 56, right: 16, top: 30, bottom: 28 },
    tooltip: { trigger: 'axis', backgroundColor: '#181b1f', borderColor: '#2c3235', textStyle: { color: '#d8d9da' } },
    legend: { top: 0, textStyle: { color: '#9fa7b3' } },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#2c3235' } }, axisLabel: { color: '#9fa7b3' } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#22252b' } }, axisLabel: { color: '#9fa7b3', formatter: (v: number) => num(v) } },
    series: d.series.map((s) => ({
      name: s.key,
      type: 'bar',
      stack: 'tokens',
      barMaxWidth: 24,
      data: s.input_tokens.map((x, i) => x + s.output_tokens[i] + s.cache_creation_input_tokens[i]),
    })),
  }
})
</script>

<template>
  <PanelBox title="Claude 사용량 (FR-004)" :src="state.usage" :span="12">
    <div v-if="u" class="usage-grid">
      <div class="gauges">
        <div class="gauge-box">
          <EChart :option="g5" height="160px" />
          <div v-if="u.five_hour?.resets_at_iso" class="muted small center">초기화 {{ time(u.five_hour?.resets_at_iso) }} ({{ relative(u.five_hour?.resets_at_iso) }})</div>
        </div>
        <div class="gauge-box">
          <EChart :option="g7" height="160px" />
          <div v-if="u.seven_day?.resets_at_iso" class="muted small center">초기화 {{ time(u.seven_day?.resets_at_iso) }} ({{ relative(u.seven_day?.resets_at_iso) }})</div>
        </div>
        <p v-if="!u.limits_available" class="notice warn small">{{ u.limits_notice }}</p>
        <p v-else-if="u.snapshot.stale" class="notice warn small">한도 값이 {{ Math.round((u.snapshot.age_sec ?? 0) / 60) }}분 전 기준입니다.</p>
      </div>
      <div class="usage-stats">
        <div class="mini"><span>오늘 응답</span><strong>{{ num(u.today.totals.responses) }}</strong></div>
        <div class="mini"><span>오늘 입력</span><strong>{{ num(u.today.totals.input_tokens + u.today.totals.cache_creation_input_tokens) }}</strong></div>
        <div class="mini"><span>오늘 출력</span><strong>{{ num(u.today.totals.output_tokens) }}</strong></div>
        <div class="mini"><span>캐시 적중</span><strong>{{ u.today.totals.cache_hit_rate == null ? '—' : pct(u.today.totals.cache_hit_rate * 100) }}</strong></div>
        <div class="mini"><span>세션 비용</span><strong>{{ u.session_cost_usd == null ? '—' : `$${u.session_cost_usd.toFixed(2)}` }}</strong></div>
        <div class="mini"><span>컨텍스트</span><strong :style="{ color: levelColor(u.context_used_percentage) }">{{ pct(u.context_used_percentage) }}</strong></div>
        <div class="mini wide"><span>모델</span><strong class="small">{{ u.model_id ?? '—' }}</strong></div>
      </div>
      <div class="usage-chart">
        <div class="row gap">
          <span class="muted small">시간대별 · 모델별 토큰 (입력 + 출력 + 캐시 생성)</span>
          <span class="spacer"></span>
          <div class="tabs">
            <button v-for="r in RANGES" :key="r" :class="{ on: state.range === r }" @click="setRange(r)">{{ r }}</button>
          </div>
        </div>
        <p v-if="ts && !ts.series.length" class="notice muted">이 구간의 사용 기록이 없습니다.</p>
        <EChart v-else :option="chart" height="220px" />
      </div>
    </div>
  </PanelBox>
</template>
