#!/usr/bin/env python3
"""OpenAPI 3.x 명세 -> REST API 레퍼런스 Markdown.

  openapi_docs.py detect                         저장소에서 OpenAPI 명세 파일 탐지
  openapi_docs.py render <spec> [-o docs/api]    레퍼런스 생성 (reference.md)

JSON 은 표준 라이브러리로, YAML 은 PyYAML 이 설치된 경우에만 읽는다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
MAX_DEPTH = 4


def load_spec(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    try:
        import yaml  # type: ignore
    except ImportError:
        raise SystemExit(f"{path} 는 YAML 입니다. `pip install pyyaml` 후 다시 실행하거나 JSON 으로 변환하세요.")
    return yaml.safe_load(text)


def detect(root: Path) -> list[Path]:
    found = []
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file():
            continue
        if p.suffix not in (".json", ".yaml", ".yml") or p.stat().st_size > 5_000_000:
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            continue
        if re.search(r'^\s*"?openapi"?\s*:\s*"?3\.', head, re.M):
            found.append(p)
    return sorted(found)


# ---------------------------------------------------------------- schema helpers
class Spec:
    def __init__(self, data: dict):
        self.data = data

    def resolve(self, node):
        seen = 0
        while isinstance(node, dict) and "$ref" in node and seen < 20:
            ref = node["$ref"]
            if not ref.startswith("#/"):
                return {"description": f"외부 참조: {ref}"}
            cur = self.data
            for part in ref[2:].split("/"):
                cur = cur.get(part.replace("~1", "/").replace("~0", "~"), {}) if isinstance(cur, dict) else {}
            node, seen = cur, seen + 1
        return node or {}

    @staticmethod
    def ref_name(node) -> str | None:
        if isinstance(node, dict) and "$ref" in node:
            return node["$ref"].rsplit("/", 1)[-1]
        return None

    def type_label(self, raw) -> str:
        name = self.ref_name(raw)
        s = self.resolve(raw)
        if "allOf" in s or "oneOf" in s or "anyOf" in s:
            key = next(k for k in ("allOf", "oneOf", "anyOf") if k in s)
            inner = " | ".join(self.type_label(x) for x in s[key]) if key != "allOf" else " & ".join(self.type_label(x) for x in s[key])
            return name or inner
        t = s.get("type", "object" if "properties" in s else "any")
        if isinstance(t, list):
            t = " | ".join(t)
        if t == "array":
            return f"array<{self.type_label(s.get('items', {}))}>"
        label = name or t
        if s.get("format"):
            label += f" ({s['format']})"
        if s.get("enum"):
            label += " enum: " + ", ".join(f"`{e}`" for e in s["enum"])
        return label

    def merged(self, raw) -> dict:
        s = self.resolve(raw)
        if "allOf" not in s:
            return s
        out: dict = {"type": "object", "properties": {}, "required": []}
        for part in s["allOf"]:
            p = self.merged(part)
            out["properties"].update(p.get("properties", {}))
            out["required"] += p.get("required", [])
        return out

    def fields(self, raw, prefix="", depth=0) -> list[tuple[str, str, bool, str]]:
        s = self.merged(raw)
        if s.get("type") == "array" and depth == 0:
            return self.fields(s.get("items", {}), "[]", depth)
        rows = []
        required = set(s.get("required", []))
        for name, prop in (s.get("properties") or {}).items():
            p = self.merged(prop)
            path = f"{prefix}.{name}" if prefix else name
            desc = p.get("description") or ""
            if "default" in p:
                desc += f" (기본값: `{p['default']}`)"
            rows.append((path, self.type_label(prop), name in required, desc))
            if depth + 1 < MAX_DEPTH:
                if p.get("properties"):
                    rows += self.fields(prop, path, depth + 1)
                elif p.get("type") == "array" and self.merged(p.get("items", {})).get("properties"):
                    rows += self.fields(p["items"], path + "[]", depth + 1)
        return rows

    def example(self, raw, depth=0):
        s = self.merged(raw)
        if "example" in s:
            return s["example"]
        if "default" in s:
            return s["default"]
        if s.get("enum"):
            return s["enum"][0]
        for key in ("oneOf", "anyOf"):
            if s.get(key):
                return self.example(s[key][0], depth)
        t = s.get("type", "object" if "properties" in s else None)
        if isinstance(t, list):  # OpenAPI 3.1: ["string", "null"]
            t = next((x for x in t if x != "null"), None)
        if depth > MAX_DEPTH:
            return None
        if t == "object":
            return {k: self.example(v, depth + 1) for k, v in (s.get("properties") or {}).items()}
        if t == "array":
            return [self.example(s.get("items", {}), depth + 1)]
        fmt = s.get("format", "")
        return {"string": {"date-time": "2026-01-01T00:00:00Z", "date": "2026-01-01", "uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                           "email": "user@example.com", "uri": "https://example.com"}.get(fmt, "string"),
                "integer": 0, "number": 0.0, "boolean": True}.get(t)


def media_example(spec: Spec, media: dict):
    if "example" in media:
        return media["example"]
    if media.get("examples"):
        first = next(iter(media["examples"].values()))
        return spec.resolve(first).get("value")
    return spec.example(media.get("schema", {}))


# ---------------------------------------------------------------- rendering
def anchor(text: str) -> str:
    return re.sub(r"[^\w\- ]", "", text.lower()).strip().replace(" ", "-")


def _cell(v: str) -> str:
    return re.sub(r"(?<!\\)\|", r"\\|", str(v)).replace("\n", " ")


def table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def security_label(spec: Spec, op: dict) -> str:
    reqs = op.get("security", spec.data.get("security"))
    if not reqs:
        return "불필요"
    schemes = spec.data.get("components", {}).get("securitySchemes", {})
    labels = []
    for req in reqs:
        if not req:
            labels.append("선택(인증 없이도 가능)")
            continue
        for name, scopes in req.items():
            sc = schemes.get(name, {})
            kind = {"http": f"HTTP {sc.get('scheme', '')}", "apiKey": f"API Key ({sc.get('in')}: `{sc.get('name')}`)",
                    "oauth2": "OAuth2", "openIdConnect": "OpenID Connect"}.get(sc.get("type"), name)
            labels.append(kind + (f" — scopes: {', '.join(scopes)}" if scopes else ""))
    return " 또는 ".join(labels)


def curl(spec: Spec, base: str, method: str, path: str, op: dict, params: list[dict]) -> str:
    url_path = path
    query = []
    headers = []
    for p in params:
        ex = p.get("example", spec.example(p.get("schema", {})))
        if p["in"] == "path":
            url_path = url_path.replace("{" + p["name"] + "}", str(ex))
        elif p["in"] == "query" and p.get("required"):
            query.append(f"{p['name']}={ex}")
        elif p["in"] == "header" and p.get("required"):
            headers.append(f"{p['name']}: {ex}")
    url = base.rstrip("/") + url_path + ("?" + "&".join(query) if query else "")
    lines = [f"curl -X {method.upper()} '{url}'"]
    sec = security_label(spec, op)
    if "bearer" in sec.lower() or "oauth2" in sec.lower() or "openid" in sec.lower():
        lines.append("  -H 'Authorization: Bearer $TOKEN'")
    elif "API Key (header" in sec:
        name = re.search(r"`(.+?)`", sec)
        lines.append(f"  -H '{name.group(1) if name else 'X-API-Key'}: $API_KEY'")
    lines += [f"  -H '{h}'" for h in headers]
    body = spec.resolve(op.get("requestBody", {})).get("content", {})
    if "application/json" in body:
        lines.append("  -H 'Content-Type: application/json'")
        payload = json.dumps(media_example(spec, body["application/json"]), ensure_ascii=False)
        lines.append(f"  -d '{payload}'")
    return " \\\n".join(lines)


def render(spec_path: Path, out_dir: Path) -> Path:
    spec = Spec(load_spec(spec_path))
    d = spec.data
    if not str(d.get("openapi", "")).startswith("3"):
        raise SystemExit(f"{spec_path}: OpenAPI 3.x 명세가 아닙니다.")
    info = d.get("info", {})
    servers = d.get("servers") or [{"url": "http://localhost:8000"}]
    base = servers[0]["url"]

    ops_by_tag: dict[str, list] = {}
    for path, item in (d.get("paths") or {}).items():
        item = spec.resolve(item)
        shared = item.get("parameters", [])
        for method in METHODS:
            if method not in item:
                continue
            op = item[method]
            tag = (op.get("tags") or ["default"])[0]
            ops_by_tag.setdefault(tag, []).append((method, path, op, shared))
    tag_desc = {t["name"]: t.get("description", "") for t in d.get("tags", [])}

    md = [f"# {info.get('title', 'API')} — REST API 레퍼런스", ""]
    md += [f"> `{spec_path.relative_to(ROOT) if spec_path.is_relative_to(ROOT) else spec_path}` 에서 자동 생성됨 "
           f"(`python3 aidlc/scripts/openapi_docs.py render`). 직접 수정하지 말고 명세를 고친 뒤 다시 생성하세요.", ""]
    md += [table(["항목", "값"], [["버전", f"`{info.get('version', '-')}`"], ["OpenAPI", f"`{d.get('openapi')}`"],
                                  ["서버", "<br>".join(f"`{s['url']}` {s.get('description', '')}" for s in servers)]]), ""]
    if info.get("description"):
        md += [info["description"].strip(), ""]

    schemes = d.get("components", {}).get("securitySchemes", {})
    if schemes:
        md += ["## 인증", ""]
        rows = []
        for name, sc in schemes.items():
            detail = sc.get("scheme") or sc.get("name") or ", ".join((sc.get("flows") or {}).keys())
            rows.append([f"`{name}`", sc.get("type", ""), str(detail), sc.get("description", "").replace("\n", " ")])
        md += [table(["이름", "유형", "상세", "설명"], rows), ""]

    md += ["## 엔드포인트 목록", ""]
    rows = []
    for tag, ops in ops_by_tag.items():
        for method, path, op, _ in ops:
            title = f"{method.upper()} {path}"
            dep = " ⚠️ deprecated" if op.get("deprecated") else ""
            rows.append([tag, f"`{method.upper()}`", f"[`{path}`](#{anchor(title)})", (op.get("summary") or "") + dep])
    md += [table(["그룹", "메서드", "경로", "설명"], rows), ""]

    for tag, ops in ops_by_tag.items():
        md += [f"## {tag}", ""]
        if tag_desc.get(tag):
            md += [tag_desc[tag], ""]
        for method, path, op, shared in ops:
            md += [f"### {method.upper()} {path}", ""]
            if op.get("deprecated"):
                md += ["> ⚠️ **Deprecated** — 신규 연동에 사용하지 마세요.", ""]
            if op.get("summary"):
                md += [f"**{op['summary']}**", ""]
            if op.get("description"):
                md += [op["description"].strip(), ""]
            md += [f"- **인증:** {security_label(spec, op)}"]
            if op.get("operationId"):
                md += [f"- **operationId:** `{op['operationId']}`"]
            md += [""]

            params = {(p["name"], p["in"]): p for p in (spec.resolve(x) for x in shared + op.get("parameters", []))}
            params_list = list(params.values())
            if params_list:
                md += ["#### 파라미터", ""]
                md += [table(["이름", "위치", "타입", "필수", "설명"],
                             [[f"`{p['name']}`", p["in"], spec.type_label(p.get("schema", {})), "✅" if p.get("required") else "",
                               (p.get("description") or "").replace("\n", " ")] for p in params_list]), ""]

            body = spec.resolve(op.get("requestBody", {}))
            if body.get("content"):
                media_type, media = next(iter(body["content"].items()))
                md += ["#### 요청 본문", "", f"`{media_type}`" + (" (필수)" if body.get("required") else ""), ""]
                rows = spec.fields(media.get("schema", {}))
                if rows:
                    md += [table(["필드", "타입", "필수", "설명"], [[f"`{f}`", t, "✅" if r else "", desc] for f, t, r, desc in rows]), ""]
                if "json" in media_type:
                    md += ["```json", json.dumps(media_example(spec, media), ensure_ascii=False, indent=2), "```", ""]

            responses = op.get("responses", {})
            if responses:
                md += ["#### 응답", ""]
                rows = []
                for code, resp in responses.items():
                    resp = spec.resolve(resp)
                    content = resp.get("content", {})
                    schema = next(iter(content.values()), {}).get("schema") if content else None
                    rows.append([f"`{code}`", (resp.get("description") or "").replace("\n", " "),
                                 spec.type_label(schema) if schema else "-"])
                md += [table(["상태 코드", "설명", "본문"], rows), ""]
                ok = next((c for c in responses if str(c).startswith("2")), None)
                if ok:
                    content = spec.resolve(responses[ok]).get("content", {})
                    if "application/json" in content:
                        media = content["application/json"]
                        rows = spec.fields(media.get("schema", {}))
                        if rows:
                            md += [f"`{ok}` 응답 필드", "",
                                   table(["필드", "타입", "필수", "설명"], [[f"`{f}`", t, "✅" if r else "", desc] for f, t, r, desc in rows]), ""]
                        md += ["```json", json.dumps(media_example(spec, media), ensure_ascii=False, indent=2), "```", ""]

            md += ["#### 예시", "", "```bash", curl(spec, base, method, path, op, params_list), "```", ""]

    comp = d.get("components", {}).get("schemas", {})
    if comp:
        md += ["## 스키마", ""]
        for name, schema in comp.items():
            s = spec.merged(schema)
            md += [f"### {name}", ""]
            if s.get("description"):
                md += [s["description"].strip(), ""]
            rows = spec.fields(schema)
            if rows:
                md += [table(["필드", "타입", "필수", "설명"], [[f"`{f}`", t, "✅" if r else "", desc] for f, t, r, desc in rows]), ""]
            else:
                md += [f"타입: {spec.type_label(schema)}", ""]

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "reference.md"
    out.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "detect":
        specs = detect(ROOT)
        for p in specs:
            print(p.relative_to(ROOT))
        if not specs:
            print("OpenAPI 명세를 찾지 못했습니다.")
        return 0 if specs else 1
    if len(argv) >= 3 and argv[1] == "render":
        out_dir = Path(argv[argv.index("-o") + 1]) if "-o" in argv else ROOT / "docs" / "api"
        out = render(Path(argv[2]).resolve(), out_dir.resolve())
        print(f"created {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
