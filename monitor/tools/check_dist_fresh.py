#!/usr/bin/env python3
"""커밋된 `monitor/frontend/dist` 가 프론트 소스와 같은 빌드인지 검사한다 (ADR-005 §4, R-07). cicd 소유.

    python monitor/tools/check_dist_fresh.py            # 검사 (exit 0 = 최신 또는 프론트 없음, 1 = 불일치)
    python monitor/tools/check_dist_fresh.py --write    # 빌드 직후 dist/.build-meta.json 기록

입력 = `monitor/frontend/` 의 `src/**`, `index.html`, `package-lock.json`, `vite.config.ts`
(ADR-005 §4). 해시 규칙(이 파일이 단일 출처, 프론트 빌드 스크립트는 `--write` 를 호출한다):
- 입력 파일을 `frontend/` 기준 POSIX 상대 경로로 정렬한다.
- 파일마다 `<경로>\\0<내용 sha256>\\n` 을 이어 붙여 다시 sha256 한다.
- 내용은 CRLF → LF 로 바꾼 뒤 해시한다(Windows 체크아웃의 autocrlf 차이로 거짓 불일치가 나지 않게).

`.build-meta.json` = `{"schema": 1, "algorithm": "sha256", "source_hash": "<hex>", "inputs": [...], "file_count": N}`.

상태
- 프론트 디렉터리(`frontend/package.json`)가 아직 없음 → "no dist yet" 안내, exit 0 (T-012 전).
- 프론트는 있는데 dist 또는 `.build-meta.json` 이 없음 → exit 1.
- 해시 불일치 → exit 1 (`cd monitor/frontend && npm ci && npm run build` 후 dist 를 같은 PR 에 포함).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
META_NAME = ".build-meta.json"
INPUT_DIRS = ("src",)
INPUT_FILES = ("index.html", "package-lock.json", "vite.config.ts")
SCHEMA = 1


def input_files(frontend: Path) -> list[Path]:
    files: list[Path] = []
    for name in INPUT_DIRS:
        base = frontend / name
        if base.is_dir():
            files.extend(p for p in base.rglob("*") if p.is_file())
    for name in INPUT_FILES:
        p = frontend / name
        if p.is_file():
            files.append(p)
    return sorted(files, key=lambda p: p.relative_to(frontend).as_posix())


def source_hash(frontend: Path) -> tuple[str, int]:
    outer = hashlib.sha256()
    files = input_files(frontend)
    for path in files:
        rel = path.relative_to(frontend).as_posix()
        content = path.read_bytes().replace(b"\r\n", b"\n")
        outer.update(rel.encode("utf-8") + b"\0")
        outer.update(hashlib.sha256(content).hexdigest().encode("ascii") + b"\n")
    return outer.hexdigest(), len(files)


def write_meta(frontend: Path) -> Path:
    dist = frontend / "dist"
    if not dist.is_dir():
        raise SystemExit(f"dist 가 없습니다: {dist} — 먼저 npm run build")
    digest, count = source_hash(frontend)
    meta = {
        "schema": SCHEMA,
        "algorithm": "sha256",
        "source_hash": digest,
        "inputs": [f"{d}/" for d in INPUT_DIRS] + list(INPUT_FILES),
        "file_count": count,
    }
    out = dist / META_NAME
    out.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8", newline="\n")
    return out


def check(frontend: Path) -> tuple[int, str]:
    """(exit code, 한 줄 메시지)."""
    if not (frontend / "package.json").is_file():
        return 0, "no dist yet — monitor/frontend 가 아직 없음 (T-012 전), 검사 생략"
    dist = frontend / "dist"
    meta_path = dist / META_NAME
    fix = "cd monitor/frontend && npm ci && npm run build 후 dist 를 같은 PR 에 포함하세요"
    if not (dist / "index.html").is_file():
        return 1, f"dist 없음 — {fix}"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 1, f"dist/{META_NAME} 없음 — {fix}"
    except (OSError, ValueError) as exc:
        return 1, f"dist/{META_NAME} 를 읽지 못함({type(exc).__name__}) — {fix}"
    if not isinstance(meta, dict) or meta.get("schema") != SCHEMA:
        return 1, f"dist/{META_NAME} 형식이 다름(schema {SCHEMA} 아님) — {fix}"
    digest, count = source_hash(frontend)
    if meta.get("source_hash") != digest:
        return 1, f"dist 가 소스와 다름(입력 {count}개) — {fix}"
    return 0, f"dist 최신 (입력 {count}개, {digest[:12]})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_dist_fresh.py")
    parser.add_argument(
        "--write", action="store_true", help="dist/.build-meta.json 을 기록"
    )
    parser.add_argument(
        "--frontend", type=Path, default=FRONTEND, help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    if args.write:
        out = write_meta(args.frontend)
        print(f"wrote {out}")
        return 0
    code, message = check(args.frontend)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
