---
name: aidlc-interpret
description: User Layer 문서를 Gate 검사 후 doc-interpreter Agent 로 해석해 Project Layer 요구 해석서(00-interpretation.md)를 만든다.
disable-model-invocation: true
---
# /aidlc-interpret — 1단계: User Layer → Project Layer 해석

1. **Gate:** `python3 aidlc/scripts/aidlc.py check user` 실행.
   - FAIL 이면 미작성 항목 목록을 사용자에게 보여주고 **여기서 멈춘다.**
2. `doc-interpreter` 서브에이전트에 위임: "workspace/user/ 4개 문서를 해석해 workspace/project/00-interpretation.md 를 작성(또는 갱신)하라."
3. 결과 보고:
   - GO / HOLD 판단과 이유
   - §4 사용자 질문 목록 (번호 붙여 그대로 보여준다)
   - §3 충돌 항목
4. HOLD 이면: 사용자가 user 문서를 고친 뒤 `/aidlc-interpret` 를 다시 실행하도록 안내한다.
   GO 이면: 다음 단계 `/aidlc-analyze` 를 안내한다.
