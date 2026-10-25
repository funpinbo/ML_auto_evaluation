// 빌드 직후 dist/.build-meta.json 기록 — 해시 규칙의 단일 출처는 monitor/tools/check_dist_fresh.py (ADR-005 §4)
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const tool = fileURLToPath(new URL('../../tools/check_dist_fresh.py', import.meta.url))
for (const py of ['python3', 'python', 'py']) {
  const r = spawnSync(py, [tool, '--write'], { stdio: 'inherit' })
  if (r.error) continue // 실행 파일 없음 → 다음 후보
  process.exit(r.status ?? 1)
}
console.error('Python 을 찾을 수 없어 .build-meta.json 을 쓰지 못했습니다.')
process.exit(1)
