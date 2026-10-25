// SSE 구독 + 폴링 폴백 (contracts/sse-events.md). 연결 실패·503 이면 5초 폴링, 30초 뒤 SSE 재시도.
import { ref } from 'vue'

export type Mode = 'connecting' | 'live' | 'polling'
export const mode = ref<Mode>('connecting')
export const warming = ref<number | null>(null)

const POLL_MS = 5000
const RETRY_SSE_MS = 30000

interface Handlers {
  onChanged: (topics: string[]) => void
  onReconnect: () => void
}

export function connect(h: Handlers, factory: (url: string) => EventSource = (u) => new EventSource(u)): () => void {
  let es: EventSource | null = null
  let poll: ReturnType<typeof setInterval> | null = null
  let retry: ReturnType<typeof setTimeout> | null = null
  let stopped = false

  const startPolling = () => {
    mode.value = 'polling'
    if (!poll) poll = setInterval(h.onReconnect, POLL_MS)
    if (!retry) retry = setTimeout(() => { retry = null; open() }, RETRY_SSE_MS)
  }
  const stopPolling = () => {
    if (poll) clearInterval(poll)
    poll = null
  }

  function open() {
    if (stopped) return
    es?.close()
    mode.value = 'connecting'
    es = factory('/api/v1/events')
    es.onopen = () => {
      const wasPolling = mode.value !== 'live'
      mode.value = 'live'
      stopPolling()
      if (wasPolling) h.onReconnect() // 재연결 직후 모든 패널 한 번 다시 조회
    }
    es.addEventListener('changed', (ev) => {
      try {
        const data = JSON.parse((ev as MessageEvent).data) as { topics?: string[] }
        if (Array.isArray(data.topics)) h.onChanged(data.topics)
      } catch {
        /* 형식이 틀린 프레임은 무시 */
      }
    })
    es.addEventListener('warming', (ev) => {
      try {
        warming.value = (JSON.parse((ev as MessageEvent).data) as { progress: number }).progress
      } catch {
        warming.value = 0
      }
    })
    es.addEventListener('ready', () => {
      if (warming.value !== null) h.onChanged(['usage'])
      warming.value = null
    })
    es.onerror = () => {
      // 브라우저가 스스로 재연결하는 중이면(CONNECTING) 기다리는 동안만 폴링, 완전히 닫혔으면(503 등) 폴백
      if (es?.readyState === 2) {
        es = null
        startPolling()
      } else if (mode.value === 'live') {
        mode.value = 'connecting'
        if (!poll) poll = setInterval(h.onReconnect, POLL_MS)
      }
    }
  }

  open()
  return () => {
    stopped = true
    es?.close()
    stopPolling()
    if (retry) clearTimeout(retry)
  }
}
