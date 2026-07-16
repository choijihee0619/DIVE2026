# MongoDB 사용 매뉴얼

작성일: 2026-07-14  
갱신일: 2026-07-15  
기준: 해커톤용 HUG보증관리시스템 Backend/RAG 개발

이 프로젝트는 로컬 파일·로컬 DB 중심이 아니라 **MongoDB Atlas를 공통 데이터베이스로 사용**한다. 배포 단계까지 가지 않더라도, 팀원이 같은 데이터를 보고 RAG용 벡터 검색을 쓰려면 Atlas가 가장 단순하다.

---

## 1. 결론

| 용도 | 선택 |
|---|---|
| 앱이 실제로 읽고 쓰는 DB | MongoDB Atlas |
| RAG 벡터 검색 | MongoDB Atlas Vector Search |
| raw CSV/JSON/parquet 파일 | 백업·재현용 원본 |
| MongoDB Compass | Atlas와 로컬 DB를 눈으로 확인하는 데스크톱 도구 |
| 로컬 MongoDB(`localhost:27017`) | 네트워크 장애 시 임시 대체 또는 개인 실험용 |

원칙:

```text
raw/interim/processed 파일 = 원본과 분석 산출물
MongoDB Atlas = 백엔드 앱이 사용하는 운영 데이터
```

raw 파일을 바로 지우면 안 된다. API 응답 재현, 발표 근거, 데이터 재수집 비교에 필요하다.

현재 Compass에 `cluster0...mongodb.net`과 `localhost:27017`이 함께 보인다면, 기준은 다음처럼 둔다.

```text
공식 개발 데이터: cluster0...mongodb.net (Atlas)
개인 테스트 데이터: localhost:27017
```

앱 `.env`의 `MONGODB_URI`는 Atlas 연결 문자열을 기본값으로 둔다. 로컬 DB는 Atlas 접속이 안 되거나 개인 실험을 할 때만 임시로 바꾼다.

---

## 2. Atlas 생성 절차

1. https://cloud.mongodb.com 접속
2. Organization/Project 생성
3. `Deploy a database` 선택
4. Free tier 또는 해커톤용 최소 클러스터 선택
5. 리전은 가능하면 서울 또는 가까운 아시아 리전 선택
6. Database Access에서 DB 사용자 생성
7. Network Access에서 접속 IP 허용
   - 개발 중: 팀원 IP 추가
   - 급한 테스트: `0.0.0.0/0` 허용 가능
   - 발표/공유 전: 필요한 IP로 다시 제한
8. Connect > Drivers > Python 선택 후 연결 문자열 복사

`.env`에는 아래처럼 저장한다.

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGODB_DB_NAME=dive2026
RAG_BACKEND=atlas_vector_search
OPENAI_API_KEY=<OpenAI project API key>
EMBEDDING_MODEL_NAME=text-embedding-3-large
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=64
MONGODB_VECTOR_INDEX=rag_chunks_vector_index
```

주의:
- 연결 문자열은 문서, Git, 채팅에 올리지 않는다.
- 비밀번호 특수문자는 URL 인코딩이 필요할 수 있다.
- `backend/backend_env_설정_260714.txt`에는 실제 값을 넣을 수 있지만 Git 커밋 금지다.

---

## 3. 왜 Atlas인가

해커톤에서는 DB를 직접 운영하는 것보다 “모두가 같은 DB를 보고 빠르게 개발하는 것”이 중요하다.

Atlas를 쓰는 이유:
- 팀원들이 같은 데이터에 접근 가능
- FastAPI 백엔드와 바로 연결 가능
- MongoDB Compass와 웹 콘솔로 데이터 확인 가능
- 상담 RAG용 벡터 검색을 같은 DB에서 처리 가능
- 별도 Chroma, Pinecone, PostgreSQL+pgvector를 추가하지 않아도 됨

로컬 MongoDB는 빠른 단독 실험에는 좋지만, RAG 벡터 검색과 팀 공유에는 불리하다.

---

## 4. MongoDB Compass 사용 기준

Compass는 DB 서버가 아니라 **DB를 보는 데스크톱 화면**이다. 왼쪽에 보이는 연결 중 어떤 것을 누르느냐에 따라 보는 DB가 달라진다.

| Compass 연결 | 의미 | 사용 기준 |
|---|---|---|
| `cluster0...mongodb.net` | MongoDB Atlas 클라우드 DB | 팀 공통 개발 기준 |
| `localhost:27017` | 내 컴퓨터의 로컬 MongoDB | 개인 실험 또는 임시 확인 |

권장 사용법:

1. 발표/개발 기준 데이터는 Atlas 연결에서 확인한다.
2. 로컬 연결에 만든 데이터는 팀원에게 자동 공유되지 않는다.
3. 같은 컬렉션 이름이라도 Atlas와 로컬은 완전히 다른 DB다.
4. 실수 방지를 위해 Atlas DB 이름은 `dive2026`, 로컬 실험 DB는 `dive2026_local`처럼 분리한다.

로컬 MongoDB를 잠깐 쓸 때의 `.env` 예시:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=dive2026_local
RAG_BACKEND=none
```

Atlas를 쓸 때의 `.env` 예시:

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGODB_DB_NAME=dive2026
RAG_BACKEND=atlas_vector_search
```

---

## 5. 데이터 저장 구조

앱 데이터는 `property_id`, `contract_id`, `user_id` 같은 UUID 기준으로 연결한다.

권장 컬렉션:

| 컬렉션 | 역할 |
|---|---|
| `users` | 임차인, 임대인, 아이엔, HUG 담당자 |
| `properties` | 주소 정규화된 부동산 물건 |
| `contracts` | 임대차 계약 |
| `registry_snapshots` | CODEF 등기부 또는 Mock 등기부 결과 |
| `building_registry_snapshots` | 건축물대장 조회 결과 |
| `rtms_transactions` | 실거래가 조회 결과 |
| `official_price_snapshots` | 공시가격 live 또는 mock 결과 |
| `landlords` | 임대인·사업자·DART 정보 |
| `risk_assessments` | 위험진단 결과 |
| `evidence_requests` | 보완요청 |
| `evidences` | 증빙 제출 메타데이터 |
| `timeline_events` | 계약/검증 상태 변경 이력 |
| `api_call_logs` | 외부 API 호출 기록 |
| `rag_chunks` | RAG 검색용 상담/제도 문서 chunk |

예시:

```json
{
  "_id": "uuid",
  "property_id": "uuid",
  "source": "rtms",
  "source_system": "api_live",
  "requested_at": "2026-07-15T09:37:19+09:00",
  "request": {
    "LAWD_CD": "11680",
    "DEAL_YMD": "202506"
  },
  "response": {},
  "result_hash": "sha256..."
}
```

---

## 6. 데이터 규칙

반드시 지킬 규칙:

- `_id`는 UUID 문자열 사용
- MongoDB 기본 `ObjectId`에 의존하지 않음
- 컬렉션·필드명은 `snake_case`
- 날짜/시간은 ISO 형식 사용
- 금액은 원 단위 정수
- 비율은 0~1 float
- 외부 API 결과에는 `source_system`을 반드시 저장
  - `api_live`
  - `mock`
  - `user_upload`
- 원문 PDF, 계약서 파일은 MongoDB에 직접 저장하지 않음
- 파일은 Object Storage 또는 로컬 파일 저장소에 두고 MongoDB에는 `object_uri`, `document_hash`만 저장

개인정보 원칙:
- 상세주소, 이름, 사업자번호, 계약서 원문은 최소 저장
- 로그에는 마스킹 또는 해시만 남김
- CODEF 토큰 같은 인증값은 저장 금지

---

## 7. RAG와 Vector Search

RAG용 상담 데이터는 `rag_chunks` 컬렉션에 저장한다.

필드 예시:

```json
{
  "_id": "uuid",
  "source": "counsel_data",
  "topic": "deposit_return",
  "region": "seoul",
  "text": "상담 또는 제도 설명 본문",
  "metadata": {
    "case_type": "전세보증금 반환",
    "pii_removed": false
  },
  "embedding": [0.012, -0.034, 0.087]
}
```

Atlas Vector Search 인덱스는 `embedding` 필드에 만든다. 차원 수는 사용하는 임베딩 모델에 맞춰야 한다.

예시:

| 임베딩 모델 | 차원 수 |
|---|---:|
| OpenAI `text-embedding-3-small` | 1536 |
| OpenAI `text-embedding-3-large` | 기본 3072, 이 프로젝트는 1024로 축소 |
| Ko-SBERT 계열 | 모델별 확인 |

이 프로젝트의 확정값:

```env
EMBEDDING_MODEL_NAME=text-embedding-3-large
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=64
MONGODB_VECTOR_INDEX=rag_chunks_vector_index
```

`text-embedding-3` 계열은 API의 `dimensions` 옵션으로 출력 차원을 줄일 수 있다. Atlas Vector Search 인덱스의 `numDimensions`도 반드시 같은 1024로 설정한다.

임베딩 생성과 인덱스 설정:

```bash
/usr/local/bin/python3 scripts/embed_rag_chunks.py
```

이 스크립트는 이미 같은 모델·차원·원문 해시로 처리된 청크를 건너뛴다. 전체를 다시 만들 때만 `--force`를 사용한다.

---

## 8. LLM API 자연어 답변 구조

LLM API를 붙여 자연어 답변을 생성하는 것도 가능하다. 단, LLM이 직접 DB를 마음대로 조회하게 만들지 말고, 백엔드가 필요한 근거만 찾아서 LLM에 넘기는 구조로 만든다.

권장 흐름:

```text
사용자 질문
→ Backend API
→ MongoDB/Atlas Vector Search에서 관련 계약·위험진단·RAG 근거 조회
→ LLM API에 근거와 질문 전달
→ 자연어 답변 생성
→ 답변, 사용 근거, 모델명, 생성시각 저장
```

저장 컬렉션 예시:

| 컬렉션 | 역할 |
|---|---|
| `llm_conversations` | 사용자 질문과 답변 묶음 |
| `llm_messages` | 개별 user/assistant 메시지 |
| `llm_answer_logs` | 사용 모델, 토큰, 근거 chunk, 생성시각 |

주의:
- LLM에는 원문 개인정보를 그대로 보내지 않는다.
- 답변에는 사용한 근거 문서 또는 `rag_chunk_id`를 함께 남긴다.
- 법률 자문처럼 단정하지 않고 “정보 제공” 표현을 사용한다.
- LLM 답변은 최종 판단이 아니라 상담/검증 담당자의 판단을 돕는 보조 기능이다.

예시 문서:

```json
{
  "_id": "uuid",
  "contract_id": "uuid",
  "question": "이 계약이 왜 위험한가요?",
  "answer": "최근 실거래가 대비 보증금 비율이 높고, 등기부상 근저당 Mock 위험 항목이 확인되었습니다.",
  "evidence_ids": ["risk_assessment_id", "rag_chunk_id"],
  "model": "gpt-4.1-mini",
  "created_at": "2026-07-15T10:00:00+09:00"
}
```

---

## 9. Python 연결 예시

설치:

```bash
pip install motor beanie pydantic
```

연결 예시:

```python
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(settings.MONGODB_URI)
db = client[settings.MONGODB_DB_NAME]
```

FastAPI에서는 앱 시작 시 1회 연결하고, 종료 시 close한다.

```python
async def startup():
    app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    app.state.db = app.state.mongo_client[settings.MONGODB_DB_NAME]

async def shutdown():
    app.state.mongo_client.close()
```

---

## 10. 인덱스

최소 인덱스:

```python
await db.properties.create_index("road_addr")
await db.properties.create_index("adm_cd")
await db.contracts.create_index("property_id")
await db.contracts.create_index("tenant_id")
await db.registry_snapshots.create_index("property_id")
await db.building_registry_snapshots.create_index("property_id")
await db.rtms_transactions.create_index([("lawd_cd", 1), ("deal_ymd", -1)])
await db.official_price_snapshots.create_index("property_id")
await db.risk_assessments.create_index("contract_id")
await db.api_call_logs.create_index([("api_name", 1), ("called_at", -1)])
await db.timeline_events.create_index([("contract_id", 1), ("created_at", -1)])
```

RAG용:

```text
rag_chunks.text       → text index 또는 Atlas Search index
rag_chunks.embedding  → Atlas Vector Search index
```

---

## 11. AI 에이전트를 DB 설계에 활용하는 법

AI 에이전트는 MongoDB 설계에 충분히 도움을 줄 수 있다. 다만 실제 키, 개인정보, 계약 원문을 그대로 넘기면 안 된다.

도움받기 좋은 작업:

- 컬렉션 설계 초안 만들기
- API 응답 JSON을 보고 저장 스키마 제안
- 인덱스 추천
- `api_live`와 `mock` 결과를 같은 구조로 저장하는 정규화 규칙 만들기
- 샘플 문서 생성
- MongoDB aggregation query 초안 작성
- Atlas Vector Search 인덱스 설정 초안 작성
- 중복 컬렉션/불필요 필드 리뷰

넘기면 안 되는 것:

- 실제 MongoDB 연결 문자열
- API 키, CODEF 토큰, client secret
- 임차인/임대인 실명
- 상세주소, 계약서 원문, 등기부 원문
- 사업자번호 원문

AI 에이전트에게 줄 때는 이렇게 준다.

```text
실제값: 홍길동, 서울시 강남구 ... 101동 1001호
전달값: 이름=마스킹, 주소=시군구 수준, 상세주소 제거
```

권장 요청 예시:

```text
이 JSON 응답을 MongoDB collection에 저장하려고 한다.
PII는 제거했고, source_system은 api_live/mock/user_upload 중 하나다.
조회 패턴은 property_id 기준 상세조회와 contract_id 기준 위험진단 조회다.
컬렉션 구조와 인덱스를 추천해줘.
```

---

## 12. 현재 데이터 상태

2026-07-15 기준 외부 API 수집 상태:

| 데이터 | 상태 |
|---|---|
| 도로명주소 | live 수집 가능 |
| 건축HUB 건축물대장 | live 수집 가능 |
| 아파트 매매 실거래가 | live 수집 가능 |
| 사업자등록 상태조회 | live 수집 가능 |
| OpenDART | live 수집 가능 |
| CODEF | OAuth 토큰 발급 성공, 등기부 본문은 mock 필요 |
| 공동주택가격 | VWorld API URL/레이어명 확인 전까지 mock |
| 개별주택가격 | VWorld API URL/레이어명 확인 전까지 mock |
| 개별공시지가 | VWorld API URL/레이어명 확인 전까지 mock |

개발 시작에는 충분하다. 단, 실제 권리관계와 공시가격 정확도 검증은 아직 mock 기반이다.

### 12.1 Atlas 초기 설정 결과

2026-07-15에 `scripts/setup_mongodb.py`로 Atlas DB `dive2026`을 초기화했다.

| 항목 | 결과 |
|---|---:|
| 생성/확인된 컬렉션 | 31 |
| `data_sources` | 34 |
| `api_call_logs` | 9 |
| `api_raw_snapshots` | 15 |
| `properties` | 6 |
| `registry_snapshots` | 4 |
| `building_registry_snapshots` | 1 |
| `rtms_transactions` | 1 |
| `official_price_snapshots` | 3 |
| `rag_chunks` | 1,009 |
| `schema_migrations` | 1 |

2026-07-15 기준 `rag_chunks` 1,009건 모두 `text-embedding-3-large` 1024차원으로 임베딩했다. Atlas Vector Search 인덱스 `rag_chunks_vector_index`는 `ready` 상태이며 실제 유사도 검색까지 확인했다.

---

## 13. 개발 순서

1. Atlas 클러스터 생성
2. Compass에서 Atlas 연결 확인
3. `.env`에 `MONGODB_URI`, `MONGODB_DB_NAME` 입력
4. FastAPI에서 MongoDB 연결 확인
5. `api_call_logs`부터 저장
6. 외부 API live/mock 결과를 snapshot 컬렉션에 저장
7. `properties`, `contracts`, `risk_assessments` 연결
8. RAG용 `rag_chunks` 적재
9. `scripts/embed_rag_chunks.py`로 임베딩 및 Atlas Vector Search 인덱스 생성
10. LLM API는 RAG 검색 결과가 안정된 뒤 자연어 답변 계층으로 연결

가장 먼저 만들 컬렉션:

```text
api_call_logs
properties
registry_snapshots
building_registry_snapshots
rtms_transactions
official_price_snapshots
risk_assessments
rag_chunks
llm_conversations
llm_answer_logs
```

---

## 14. 운영 팁

- MongoDB Compass를 설치하면 데이터를 눈으로 확인하기 쉽다.
- Atlas 웹 콘솔의 `Browse Collections`도 충분히 쓸 만하다.
- Compass에서 Atlas와 localhost를 헷갈리지 않는다.
- 해커톤 전날에는 Atlas Export 또는 `mongodump`로 백업한다.
- 발표용 데이터는 live/mock 여부가 보이도록 `source_system`을 화면 또는 관리자 로그에 남긴다.
- Mock 데이터는 실패가 아니라 “외부 API 미확정 구간을 대체하는 개발용 데이터”로 관리한다.

---

## 15. 한 줄 기준

이 프로젝트의 DB 기준은 다음이다.

```text
MongoDB Atlas 하나로 앱 데이터와 RAG 벡터 데이터를 관리한다.
raw 파일은 삭제하지 않고, 재현 가능한 원본 저장소로 유지한다.
```
