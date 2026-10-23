# Chatbot API (샘플) — REST API 레퍼런스

> `aidlc/examples/chatbot-openapi.json` 에서 자동 생성됨 (`python3 aidlc/scripts/openapi_docs.py render`). 직접 수정하지 말고 명세를 고친 뒤 다시 생성하세요.

| 항목 | 값 |
|---|---|
| 버전 | `1.0.0` |
| OpenAPI | `3.1.0` |
| 서버 | `https://api.example.com/v1` 운영<br>`http://localhost:8000/v1` 로컬 |

AI-DLC 문서 생성기 데모용 샘플 명세입니다. 대화(Conversation)를 만들고 메시지를 보내면 FAQ 근거와 함께 답변을 받습니다.

## 인증

| 이름 | 유형 | 상세 | 설명 |
|---|---|---|---|
| `bearerAuth` | http | bearer | `Authorization: Bearer <token>` |

## 엔드포인트 목록

| 그룹 | 메서드 | 경로 | 설명 |
|---|---|---|---|
| system | `GET` | [`/health`](#get-health) | 헬스 체크 |
| conversations | `GET` | [`/conversations`](#get-conversations) | 대화 목록 |
| conversations | `POST` | [`/conversations`](#post-conversations) | 대화 생성 |
| conversations | `GET` | [`/conversations/{conversationId}`](#get-conversationsconversationid) | 대화 조회 |
| conversations | `DELETE` | [`/conversations/{conversationId}`](#delete-conversationsconversationid) | 대화 종료 |
| messages | `GET` | [`/conversations/{conversationId}/messages`](#get-conversationsconversationidmessages) | 메시지 이력 |
| messages | `POST` | [`/conversations/{conversationId}/messages`](#post-conversationsconversationidmessages) | 메시지 전송 (답변 생성) |
| messages | `POST` | [`/legacy/ask`](#post-legacyask) | 단발 질문 (구버전) ⚠️ deprecated |
| faq | `GET` | [`/faq/search`](#get-faqsearch) | FAQ 검색 |

## system

상태 확인

### GET /health

**헬스 체크**

- **인증:** 불필요
- **operationId:** `getHealth`

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 정상 | object |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `status` | string |  |  |

```json
{
  "status": "ok"
}
```

#### 예시

```bash
curl -X GET 'https://api.example.com/v1/health'
```

## conversations

대화 세션 생성·조회·종료

### GET /conversations

**대화 목록**

- **인증:** HTTP bearer
- **operationId:** `listConversations`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `cursor` | query | string |  | 이전 응답의 `next_cursor` |
| `limit` | query | integer |  | 페이지 크기 |
| `status` | query | string enum: `open`, `closed` |  | 상태 필터 |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 성공 | ConversationPage |
| `401` | 인증 실패 | Error |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | array<Conversation> | ✅ |  |
| `data[].channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `data[].locale` | string |  | 응답 언어 (기본값: `ko-KR`) |
| `data[].id` | string (uuid) | ✅ |  |
| `data[].status` | string enum: `open`, `closed` | ✅ |  |
| `data[].created_at` | string (date-time) | ✅ |  |
| `next_cursor` | string \| null |  | 다음 페이지 커서. 마지막 페이지면 null |

```json
{
  "data": [
    {
      "channel": "web",
      "locale": "ko-KR",
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "status": "open",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "next_cursor": "string"
}
```

#### 예시

```bash
curl -X GET 'https://api.example.com/v1/conversations' \
  -H 'Authorization: Bearer $TOKEN'
```

### POST /conversations

**대화 생성**

새 대화 세션을 만듭니다. `Idempotency-Key` 헤더를 보내면 같은 키의 재시도는 같은 대화를 반환합니다.

- **인증:** HTTP bearer
- **operationId:** `createConversation`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `Idempotency-Key` | header | string |  | 재시도 안전 키 |

#### 요청 본문

`application/json` (필수)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `locale` | string |  | 응답 언어 (기본값: `ko-KR`) |

```json
{
  "channel": "web",
  "locale": "ko-KR"
}
```

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `201` | 생성됨 | Conversation |
| `400` | 요청 검증 실패 | Error |
| `401` | 인증 실패 | Error |

`201` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `locale` | string |  | 응답 언어 (기본값: `ko-KR`) |
| `id` | string (uuid) | ✅ |  |
| `status` | string enum: `open`, `closed` | ✅ |  |
| `created_at` | string (date-time) | ✅ |  |

```json
{
  "channel": "web",
  "locale": "ko-KR",
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "open",
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### 예시

```bash
curl -X POST 'https://api.example.com/v1/conversations' \
  -H 'Authorization: Bearer $TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"channel": "web", "locale": "ko-KR"}'
```

### GET /conversations/{conversationId}

**대화 조회**

- **인증:** HTTP bearer
- **operationId:** `getConversation`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `conversationId` | path | string (uuid) | ✅ | 대화 ID |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 성공 | Conversation |
| `404` | 리소스 없음 | Error |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `locale` | string |  | 응답 언어 (기본값: `ko-KR`) |
| `id` | string (uuid) | ✅ |  |
| `status` | string enum: `open`, `closed` | ✅ |  |
| `created_at` | string (date-time) | ✅ |  |

```json
{
  "channel": "web",
  "locale": "ko-KR",
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "open",
  "created_at": "2026-01-01T00:00:00Z"
}
```

#### 예시

```bash
curl -X GET 'https://api.example.com/v1/conversations/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer $TOKEN'
```

### DELETE /conversations/{conversationId}

**대화 종료**

대화를 종료합니다. 종료된 대화에는 메시지를 보낼 수 없습니다.

- **인증:** HTTP bearer
- **operationId:** `closeConversation`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `conversationId` | path | string (uuid) | ✅ | 대화 ID |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `204` | 종료됨 | - |
| `404` | 리소스 없음 | Error |

#### 예시

```bash
curl -X DELETE 'https://api.example.com/v1/conversations/3fa85f64-5717-4562-b3fc-2c963f66afa6' \
  -H 'Authorization: Bearer $TOKEN'
```

## messages

대화 내 메시지 전송과 이력

### GET /conversations/{conversationId}/messages

**메시지 이력**

- **인증:** HTTP bearer
- **operationId:** `listMessages`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `conversationId` | path | string (uuid) | ✅ | 대화 ID |
| `cursor` | query | string |  | 이전 응답의 `next_cursor` |
| `limit` | query | integer |  | 페이지 크기 |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 성공 | MessagePage |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | array<Message> |  |  |
| `data[].id` | string (uuid) |  |  |
| `data[].role` | string enum: `user`, `bot`, `agent` |  |  |
| `data[].text` | string |  |  |
| `data[].created_at` | string (date-time) |  |  |
| `next_cursor` | string \| null |  |  |

```json
{
  "data": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "role": "user",
      "text": "string",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "next_cursor": "string"
}
```

#### 예시

```bash
curl -X GET 'https://api.example.com/v1/conversations/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages' \
  -H 'Authorization: Bearer $TOKEN'
```

### POST /conversations/{conversationId}/messages

**메시지 전송 (답변 생성)**

- **인증:** HTTP bearer
- **operationId:** `sendMessage`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `conversationId` | path | string (uuid) | ✅ | 대화 ID |

#### 요청 본문

`application/json` (필수)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | ✅ | 사용자 메시지 (최대 2000자) |

```json
{
  "text": "환불은 며칠 걸리나요?"
}
```

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 봇 답변 | BotReply |
| `404` | 리소스 없음 | Error |
| `409` | 종료된 대화 | Error |
| `429` | 요청 한도 초과 (`Retry-After` 헤더 참고) | Error |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message` | Message | ✅ |  |
| `message.id` | string (uuid) |  |  |
| `message.role` | string enum: `user`, `bot`, `agent` |  |  |
| `message.text` | string |  |  |
| `message.created_at` | string (date-time) |  |  |
| `sources` | array<FaqHit> | ✅ | 답변 근거 FAQ |
| `sources[].faq_id` | string |  |  |
| `sources[].title` | string |  |  |
| `sources[].score` | number |  | 유사도 0~1 |
| `sources[].url` | string (uri) |  |  |
| `handoff` | boolean | ✅ | 상담원 연결 권장 여부 |

```json
{
  "message": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "role": "user",
    "text": "string",
    "created_at": "2026-01-01T00:00:00Z"
  },
  "sources": [
    {
      "faq_id": "FAQ-102",
      "title": "환불 처리 기간",
      "score": 0.87,
      "url": "https://example.com"
    }
  ],
  "handoff": true
}
```

#### 예시

```bash
curl -X POST 'https://api.example.com/v1/conversations/3fa85f64-5717-4562-b3fc-2c963f66afa6/messages' \
  -H 'Authorization: Bearer $TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"text": "환불은 며칠 걸리나요?"}'
```

### POST /legacy/ask

> ⚠️ **Deprecated** — 신규 연동에 사용하지 마세요.

**단발 질문 (구버전)**

- **인증:** HTTP bearer
- **operationId:** `legacyAsk`

#### 요청 본문

`application/json`

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | ✅ | 사용자 메시지 (최대 2000자) |

```json
{
  "text": "환불은 며칠 걸리나요?"
}
```

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 답변 | BotReply |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message` | Message | ✅ |  |
| `message.id` | string (uuid) |  |  |
| `message.role` | string enum: `user`, `bot`, `agent` |  |  |
| `message.text` | string |  |  |
| `message.created_at` | string (date-time) |  |  |
| `sources` | array<FaqHit> | ✅ | 답변 근거 FAQ |
| `sources[].faq_id` | string |  |  |
| `sources[].title` | string |  |  |
| `sources[].score` | number |  | 유사도 0~1 |
| `sources[].url` | string (uri) |  |  |
| `handoff` | boolean | ✅ | 상담원 연결 권장 여부 |

```json
{
  "message": {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "role": "user",
    "text": "string",
    "created_at": "2026-01-01T00:00:00Z"
  },
  "sources": [
    {
      "faq_id": "FAQ-102",
      "title": "환불 처리 기간",
      "score": 0.87,
      "url": "https://example.com"
    }
  ],
  "handoff": true
}
```

#### 예시

```bash
curl -X POST 'https://api.example.com/v1/legacy/ask' \
  -H 'Authorization: Bearer $TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"text": "환불은 며칠 걸리나요?"}'
```

## faq

답변 근거가 되는 FAQ 검색

### GET /faq/search

**FAQ 검색**

- **인증:** HTTP bearer
- **operationId:** `searchFaq`

#### 파라미터

| 이름 | 위치 | 타입 | 필수 | 설명 |
|---|---|---|---|---|
| `q` | query | string | ✅ | 검색어 |
| `limit` | query | integer |  | 페이지 크기 |

#### 응답

| 상태 코드 | 설명 | 본문 |
|---|---|---|
| `200` | 검색 결과 | array<FaqHit> |

`200` 응답 필드

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `[].faq_id` | string |  |  |
| `[].title` | string |  |  |
| `[].score` | number |  | 유사도 0~1 |
| `[].url` | string (uri) |  |  |

```json
[
  {
    "faq_id": "FAQ-102",
    "title": "환불 처리 기간",
    "score": 0.87,
    "url": "https://example.com"
  }
]
```

#### 예시

```bash
curl -X GET 'https://api.example.com/v1/faq/search?q=환불' \
  -H 'Authorization: Bearer $TOKEN'
```

## 스키마

### ConversationCreate

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `locale` | string |  | 응답 언어 (기본값: `ko-KR`) |

### Conversation

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `locale` | string |  | 응답 언어 (기본값: `ko-KR`) |
| `id` | string (uuid) | ✅ |  |
| `status` | string enum: `open`, `closed` | ✅ |  |
| `created_at` | string (date-time) | ✅ |  |

### ConversationPage

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | array<Conversation> | ✅ |  |
| `data[].channel` | string enum: `web`, `kakao`, `slack` | ✅ | 유입 채널 |
| `data[].locale` | string |  | 응답 언어 (기본값: `ko-KR`) |
| `data[].id` | string (uuid) | ✅ |  |
| `data[].status` | string enum: `open`, `closed` | ✅ |  |
| `data[].created_at` | string (date-time) | ✅ |  |
| `next_cursor` | string \| null |  | 다음 페이지 커서. 마지막 페이지면 null |

### MessageCreate

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | ✅ | 사용자 메시지 (최대 2000자) |

### Message

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `id` | string (uuid) |  |  |
| `role` | string enum: `user`, `bot`, `agent` |  |  |
| `text` | string |  |  |
| `created_at` | string (date-time) |  |  |

### MessagePage

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `data` | array<Message> |  |  |
| `data[].id` | string (uuid) |  |  |
| `data[].role` | string enum: `user`, `bot`, `agent` |  |  |
| `data[].text` | string |  |  |
| `data[].created_at` | string (date-time) |  |  |
| `next_cursor` | string \| null |  |  |

### BotReply

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `message` | Message | ✅ |  |
| `message.id` | string (uuid) |  |  |
| `message.role` | string enum: `user`, `bot`, `agent` |  |  |
| `message.text` | string |  |  |
| `message.created_at` | string (date-time) |  |  |
| `sources` | array<FaqHit> | ✅ | 답변 근거 FAQ |
| `sources[].faq_id` | string |  |  |
| `sources[].title` | string |  |  |
| `sources[].score` | number |  | 유사도 0~1 |
| `sources[].url` | string (uri) |  |  |
| `handoff` | boolean | ✅ | 상담원 연결 권장 여부 |

### FaqHit

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `faq_id` | string |  |  |
| `title` | string |  |  |
| `score` | number |  | 유사도 0~1 |
| `url` | string (uri) |  |  |

### Error

모든 4xx/5xx 응답의 공통 포맷

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `error` | object | ✅ |  |
| `error.code` | string | ✅ | 기계가 읽는 에러 코드 |
| `error.message` | string | ✅ | 사람이 읽는 메시지 |
| `error.trace_id` | string |  | 문의 시 전달할 추적 ID |
