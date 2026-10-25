import { describe, expect, it } from 'vitest'
import { keysFor } from '../src/lib/store'

describe('topic → 재조회 패널', () => {
  it('tasks 이벤트는 /plan 도 다시 읽는다 (I-17)', () => {
    expect(keysFor(['tasks']).sort()).toEqual(['plan', 'tasks'])
  })
  it('usage 는 요약과 시계열 둘 다', () => {
    expect(keysFor(['usage']).sort()).toEqual(['series', 'usage'])
  })
  it('모르는 topic 은 무시하고 중복은 합친다', () => {
    expect(keysFor(['teams', 'timeline', 'plan', 'tasks']).sort()).toEqual(['plan', 'tasks'])
  })
})
