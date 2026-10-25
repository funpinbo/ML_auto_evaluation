import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { connect, mode } from '../src/lib/events'

class FakeES {
  readyState = 0
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {}
  constructor(public url: string) {}
  addEventListener(name: string, fn: (e: MessageEvent) => void) {
    ;(this.listeners[name] ??= []).push(fn)
  }
  emit(name: string, data: unknown) {
    for (const fn of this.listeners[name] ?? []) fn(new MessageEvent(name, { data: JSON.stringify(data) }))
  }
  close() {
    this.readyState = 2
  }
}

let made: FakeES[] = []
const factory = (u: string) => {
  const es = new FakeES(u)
  made.push(es)
  return es as unknown as EventSource
}

beforeEach(() => {
  made = []
  vi.useFakeTimers()
})
afterEach(() => vi.useRealTimers())

describe('SSE 구독', () => {
  it('changed 이벤트의 topic 을 넘긴다', () => {
    const onChanged = vi.fn()
    const stop = connect({ onChanged, onReconnect: vi.fn() }, factory)
    made[0].onopen?.()
    expect(mode.value).toBe('live')
    made[0].emit('changed', { topics: ['memory', 'tasks'], at: 'x' })
    expect(onChanged).toHaveBeenCalledWith(['memory', 'tasks'])
    stop()
  })

  it('연결이 닫히면(503 등) 5초 폴링으로 바꾸고 30초 뒤 SSE 를 다시 연다', () => {
    const onReconnect = vi.fn()
    const stop = connect({ onChanged: vi.fn(), onReconnect }, factory)
    made[0].readyState = 2
    made[0].onerror?.()
    expect(mode.value).toBe('polling')
    vi.advanceTimersByTime(10_000)
    expect(onReconnect).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(20_000)
    expect(made).toHaveLength(2)
    made[1].onopen?.()
    expect(mode.value).toBe('live')
    stop()
  })
})
