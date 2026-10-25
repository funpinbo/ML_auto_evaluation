// 패널 상태 + topic → 재조회 매핑 (contracts/sse-events.md §3). 서버는 무상태, 화면은 알림을 받으면 다시 읽는다.
import { reactive } from 'vue'
import { getJson, type Control, type Envelope, type Memory, type Pipeline, type Plan, type Tasks, type Timeseries, type UsageSummary } from './api'

export interface Slot<T> {
  env: Envelope<T> | null
  loading: boolean
  failed: string | null
}

function slot<T>(): Slot<T> {
  return { env: null, loading: false, failed: null }
}

export const state = reactive({
  pipeline: slot<Pipeline>(),
  plan: slot<Plan>(),
  tasks: slot<Tasks>(),
  memory: slot<Memory>(),
  control: slot<Control>(),
  usage: slot<UsageSummary>(),
  series: slot<Timeseries>(),
  range: '24h' as '5h' | '24h' | '7d' | '30d',
  updatedAt: null as Date | null,
})

type Key = 'pipeline' | 'plan' | 'tasks' | 'memory' | 'control' | 'usage' | 'series'

const tz = -new Date().getTimezoneOffset()
const BUCKET: Record<string, string> = { '5h': 'hour', '24h': 'hour', '7d': 'day', '30d': 'day' }

const PATHS: Record<Key, () => string> = {
  pipeline: () => '/pipeline',
  plan: () => '/plan',
  tasks: () => '/tasks?limit=500',
  memory: () => '/memory',
  control: () => '/control',
  usage: () => `/usage/summary?tz_offset_min=${tz}`,
  series: () => `/usage/timeseries?range=${state.range}&bucket=${BUCKET[state.range]}&group=model&tz_offset_min=${tz}`,
}

export async function load(key: Key): Promise<void> {
  const s = state[key] as Slot<unknown>
  s.loading = true
  try {
    s.env = await getJson(PATHS[key]())
    s.failed = null
    state.updatedAt = new Date()
  } catch (e) {
    s.failed = e instanceof Error ? e.message : String(e)
  } finally {
    s.loading = false
  }
}

// topic 하나가 여러 패널을 다시 읽게 할 수 있다. `tasks` → `/plan` 도 (I-17 P1 진행률 바)
export const TOPIC_KEYS: Record<string, Key[]> = {
  pipeline: ['pipeline'],
  plan: ['plan'],
  tasks: ['tasks', 'plan'],
  memory: ['memory'],
  control: ['control'],
  usage: ['usage', 'series'],
}

export function keysFor(topics: string[]): Key[] {
  const out = new Set<Key>()
  for (const t of topics) for (const k of TOPIC_KEYS[t] ?? []) out.add(k) // 모르는 topic 은 무시
  return [...out]
}

export function refreshTopics(topics: string[]): Promise<void[]> {
  return Promise.all(keysFor(topics).map(load))
}

export function refreshAll(): Promise<void[]> {
  return Promise.all((Object.keys(PATHS) as Key[]).map(load))
}
