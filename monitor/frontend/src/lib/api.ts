// REST 클라이언트 — 봉투 `{data, meta}` 와 오류 `{"error":{code,message}}` (contracts/README, ADR-011)

export interface Meta {
  status: 'ok' | 'partial' | 'empty' | 'error'
  warnings: string[]
  error: { code: string; message: string } | null
  generated_at: string
  source_mtime: string | null
}
export interface Envelope<T> {
  data: T | null
  meta: Meta
}

export interface Stage { index: number; name: string; command: string; state: 'done' | 'in_progress' | 'waiting' | 'unknown' }
export interface Gate { layer: string; result: 'PASS' | 'FAIL' | 'UNKNOWN'; unwritten: number; missing: number; target_missing: boolean; no_documents: boolean; error_code: string | null }
export interface Pipeline { current_stage: number; current_stage_name: string; next_command: string | null; all_done: boolean; stages: Stage[]; gates: Gate[] }

export interface Phase { phase: string; title: string; total: number; checked: number; percent: number; completed: boolean; current: boolean }
export interface Plan { current_phase: string | null; completed_phases: string[]; phases: Phase[] }

export interface Task { id: string; team: string; title: string; refs: string[]; deps: string[]; phase: string; checked: boolean; status: string; well_formed: boolean }
export interface Tasks { total: number; items: Task[] }

export interface Stm { status: string; task: string; team: string; outcome: string; opened_at: string; elapsed_sec: number | null; error_code: string | null }
export interface Memory { stm: Stm; ltm_rev: number | null; last_merged_stm: number | null; tasks_rev: number | null; synced_ltm_rev: number | null; current_phase: string | null; completed_phases: string[]; archive_count: number; latest_archive_seq: number | null; pending_cascade: string; stop_blocks: number }

export interface Control {
  state: string; view: string; label: string; hint: string | null; can_pause: boolean; can_resume: boolean
  loop_state: string | null; iterations_done: number | null; iterations_total: number | null; remaining_iterations: number | null
  paused_since: string | null; heartbeat_age_sec: number | null; max_pause_sec: number; remaining_pause_sec: number | null; ended_message: string | null
}

export interface Totals { responses: number; input_tokens: number; output_tokens: number; cache_creation_input_tokens: number; cache_read_input_tokens: number; cache_hit_rate: number | null }
export interface LimitWindow { used_percentage: number | null; resets_at_iso: string | null; reset_passed: boolean | null }
export interface UsageSummary {
  limits_available: boolean; limits_notice: string | null; five_hour: LimitWindow | null; seven_day: LimitWindow | null
  snapshot: { state: string; captured_at: string | null; age_sec: number | null; stale: boolean; code: string | null }
  session_cost_usd: number | null; context_used_percentage: number | null; model_id: string | null
  project_dir_found: boolean; today: { totals: Totals }; five_hour_tokens: { totals: Totals; estimated: boolean }
  warming: { state: string; progress: number | null }
}
export interface Series { key: string; responses: number[]; input_tokens: number[]; output_tokens: number[]; cache_creation_input_tokens: number[]; cache_read_input_tokens: number[] }
export interface Timeseries { range: string; bucket: string; buckets: string[]; series: Series[]; totals: Totals }

export const ERROR_TEXT: Record<string, string> = {
  NO_ACTIVE_LOOP: '실행 중인 루프가 없습니다. VSCode 에서 /aidlc-run 을 먼저 실행하세요.',
  CONTROL_WRITE_FAILED: '제어 파일을 쓰지 못했습니다. 잠시 후 다시 시도하세요.',
  FORBIDDEN_ORIGIN: '허용되지 않은 출처의 요청입니다. 대시보드 주소(127.0.0.1)로 접속하세요.',
  BAD_HOST: '허용되지 않은 주소입니다. http://127.0.0.1:<포트> 로 접속하세요.',
  METHOD_NOT_ALLOWED: '지원하지 않는 요청 방식입니다. 화면을 새로고침하세요.',
  VALIDATION_ERROR: '요청 값이 올바르지 않습니다.',
  NOT_FOUND: '요청한 항목을 찾을 수 없습니다.',
  TOO_MANY_STREAMS: '대시보드 창이 너무 많이 열려 있습니다. 5초 간격 새로고침으로 전환합니다.',
  INTERNAL_ERROR: '서버 내부 오류가 발생했습니다.',
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message)
  }
}

async function parse<T>(resp: Response): Promise<T> {
  let body: unknown = null
  try {
    body = await resp.json()
  } catch {
    /* 본문 없음 */
  }
  if (!resp.ok) {
    const err = (body as { error?: { code?: string; message?: string } } | null)?.error
    const code = err?.code ?? 'INTERNAL_ERROR'
    throw new ApiError(code, ERROR_TEXT[code] ?? err?.message ?? `HTTP ${resp.status}`, resp.status)
  }
  return body as T
}

export async function getJson<T>(path: string): Promise<Envelope<T>> {
  return parse<Envelope<T>>(await fetch(`/api/v1${path}`, { headers: { Accept: 'application/json' } }))
}

export async function postJson<T>(path: string, body: unknown = {}): Promise<Envelope<T>> {
  const resp = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  })
  return parse<Envelope<T>>(resp)
}
