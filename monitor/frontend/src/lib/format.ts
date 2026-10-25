export function num(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e4) return `${(n / 1e3).toFixed(1)}K`
  return n.toLocaleString('ko-KR')
}

export function pct(n: number | null | undefined): string {
  return n === null || n === undefined ? '—' : `${Math.round(n)}%`
}

export function duration(sec: number | null | undefined): string {
  if (sec === null || sec === undefined) return '—'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h) return `${h}시간 ${m}분`
  if (m) return `${m}분 ${s}초`
  return `${s}초`
}

export function time(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function relative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—'
  const diff = (new Date(iso).getTime() - now) / 1000
  if (Number.isNaN(diff)) return '—'
  const abs = Math.abs(diff)
  const text = abs < 3600 ? `${Math.round(abs / 60)}분` : `${Math.floor(abs / 3600)}시간 ${Math.round((abs % 3600) / 60)}분`
  return diff >= 0 ? `${text} 후` : `${text} 전`
}

// 사용률 → Grafana 임계값 색 (초록 < 60 ≤ 노랑 < 80 ≤ 빨강)
export function levelColor(p: number | null | undefined): string {
  if (p === null || p === undefined) return 'var(--muted)'
  if (p >= 80) return 'var(--red)'
  if (p >= 60) return 'var(--yellow)'
  return 'var(--green)'
}
