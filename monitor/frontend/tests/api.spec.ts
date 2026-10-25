import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, ERROR_TEXT, postJson } from '../src/lib/api'

const CODES = ['VALIDATION_ERROR', 'NOT_FOUND', 'METHOD_NOT_ALLOWED', 'BAD_HOST', 'FORBIDDEN_ORIGIN', 'NO_ACTIVE_LOOP', 'TOO_MANY_STREAMS', 'CONTROL_WRITE_FAILED', 'INTERNAL_ERROR']

afterEach(() => vi.unstubAllGlobals())

describe('API 클라이언트', () => {
  it('닫힌 오류 코드 9개 모두에 안내 문구가 있다 (METHOD_NOT_ALLOWED 포함, D-26)', () => {
    expect(Object.keys(ERROR_TEXT).sort()).toEqual([...CODES].sort())
  })

  it('POST 는 application/json 으로 보내고 오류 코드를 ApiError 로 바꾼다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'NO_ACTIVE_LOOP', message: 'x' } }), { status: 409 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const err = await postJson('/control/pause').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe('NO_ACTIVE_LOOP')
    expect((err as ApiError).message).toBe(ERROR_TEXT.NO_ACTIVE_LOOP)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/control/pause')
    expect(init.headers['Content-Type']).toBe('application/json')
  })
})
