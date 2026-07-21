# 안심이음 (Ansim-Ieum)

> **공공데이터 기반 전세 위험진단·증빙검증·이력관리 플랫폼**
>
> DIVE 2026 해커톤 — 주택도시보증공사(HUG) × (주)아이엔 발제 대응 솔루션

---

## 1. 프로젝트 소개

**안심이음**은 전세 계약의 전 생애주기 — **계약 전 예방 → 계약 체결 → 거주 중 모니터링 → 사고 후 회수** — 를 하나의 루프로 잇는 플랫폼입니다. 발제 슬로건 *"사고를 막는 데이터, 함께 만들어 주십시오"* 에 대한 답으로, **"막고(예방), 남기고(계약 기록), 되찾는(회수) 데이터 루프"** 를 구현했습니다.

### 해결하려는 문제

| 소주제 | 문제 | 안심이음의 대응 |
|---|---|---|
| ① 사고 후 회수 | HUG 대위변제 채권의 회수 우선순위 판단이 어려움 | ML 기반 회수율·소요기간 예측 + 회수 우선순위 스코어 → **HUG 회수 코크핏** |
| ② 계약 전 예방 | 임차인이 계약 전 위험 신호를 알기 어려움 | 등기부 실시간 조회 + 공공데이터 결합 **rule-based 위험진단** + 악성임대인 명단 대조 |

### 핵심 차별점

1. **역할 4종 통합 생태계** — 임차인·임대인·상담사·HUG가 같은 데이터 위에서 각자의 화면을 사용
2. **HUG 채권회수 코크핏** — HOUSTA 실집계 + ML 예측으로 회수 업무 지원
3. **RAG 상담엔진** — 비식별 상담사례 938건 + 안심전세포털 공식자료를 근거로 한 출처 표시형 AI 상담
4. **전자계약 블록체인 앵커링** — 계약 원본 해시를 체인에 기록해 사고 후 분쟁·회수 단계의 증거력 확보

---

## 2. 주요 사용자

| 역할 | 데모 계정 | 주요 기능 |
|---|---|---|
| **임차인** (tenant) | `tenant01@example.com` | 계약 등록, 위험진단 리포트, AI 전세상담, 증빙 요청, 사고 접수, 전자계약 |
| **임대인** (landlord) | `landlord01@example.com` | 증빙 제출, 반환계획 등록, 전자계약 상대방 플로우 |
| **상담사** (advisor) | `advisor01@example.com` | 증빙 검증 큐, 상담 큐(ML 자동분류 태그), 유사사례 검색 |
| **HUG 담당자** (hug_admin) | `hugadmin01@example.com` | 회수 코크핏(우선순위 채권·사고율 지도·발급 시계열·피해 분포), 사고 큐 |
| **시스템 관리자** (system_admin) | `sysadmin01@example.com` | 사용자 관리, 블록체인 트랜잭션 로그 조회 |

공통 비밀번호: `P@ssw0rd!` (`backend/scripts/seed_demo_users.py`로 idempotent 시드)

---

## 3. 핵심 기능

| 기능 | 설명 | 상태 |
|---|---|---|
| **매물·계약 등록** | 매물 등록 → 임대인 연결 → 계약 생성, 계약 상태 전이 관리 | ✅ 구현 |
| **등기부 실시간 조회** | CODEF(샌드박스) 실호출로 등기부 스냅샷 수집·갱신, 근저당·압류 등 권리 신호 자동 파싱. 실패 시 시나리오 폴백 | ✅ 구현 |
| **전세 위험진단** | 등기부·공시가격·지역 사고율·임대인 신호를 결합한 rule-based 진단 (LOW/MEDIUM/HIGH) | ✅ 구현 |
| **위험요인·필요서류 안내** | 진단 결과에 위험근거, 누락 데이터, 필요서류, 권장행동 포함 | ✅ 구현 |
| **증빙 요청·제출·검증** | 임차인 요청 → 임대인 제출(SHA-256 파일 해시) → 상담사 승인/반려 | ✅ 구현 |
| **계약 타임라인·반환계획** | 계약별 이벤트 타임라인, 보증금 반환계획 등록·추적 | ✅ 구현 |
| **RAG 기반 상담지원** | Atlas Vector Search 근거 검색 + LLM 답변 + 출처 카드(공식자료/상담사례 구분) | ✅ 구현 |
| **블록체인 이력관리** | 위험진단·증빙·검증·전자계약 해시 앵커링, 트랜잭션 조회·검증 | ✅ 구현 (Mock Chain) |
| **전자계약 (esign)** | 임차인·임대인 공동세션 → 특약 합의 → 양측 서명 → 계약서 해시 자동 앵커 → 위변조 검증 | ✅ 구현 |
| **ML 회수 예측** | 예상 회수율·등급, 배당 소요기간, SHAP 요인 설명, 상담 자동분류 | ✅ 구현 |
| **HUG 대시보드** | 회수 우선순위, 지역 사고율 지도, 발급 시계열, 피해주택 분포 (HOUSTA 실집계) | ✅ 구현 |
| **사고 접수·상담 큐·알림** | 사고 접수→상태 추적, 챗봇→상담사 이관 큐, 모니터링 알림 | ✅ 구현 |

---

## 4. 전체 시스템 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│  Frontend — Next.js 16 (App Router) · React 19 · TypeScript         │
│  역할별 라우트: /tenant /landlord /advisor /hug /admin              │
│  공통: /esign /blockchain /registry /notifications                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST (JWT Bearer)
┌──────────────────────────────▼──────────────────────────────────────┐
│  Backend — FastAPI · Python 3.12 · Motor (async MongoDB)            │
│                                                                     │
│  api/v1 (61 endpoints) → services → repositories                    │
│                                                                     │
│  ┌───────────────┐ ┌──────────────┐ ┌───────────────────────────┐   │
│  │ Risk Engine   │ │ ML Service   │ │ RAG Service               │   │
│  │ rule-based    │ │ LightGBM×2   │ │ OpenAI 임베딩             │   │
│  │ 진단·등급     │ │ 분류기×2     │ │ + Atlas Vector Search     │   │
│  │               │ │ + SHAP       │ │ + LLM 답변 생성           │   │
│  └───────────────┘ └──────────────┘ └───────────────────────────┘   │
│  ┌───────────────┐ ┌──────────────┐ ┌───────────────────────────┐   │
│  │ Registry Svc  │ │ Blockchain   │ │ Public Data Loader        │   │
│  │ CODEF 실조회  │ │ SHA-256 앵커 │ │ HOUSTA·악성임대인·        │   │
│  │ + 폴백        │ │ Mock/Polygon │ │ 우선순위 스코어 CSV 캐시  │   │
│  └───────────────┘ └──────────────┘ └───────────────────────────┘   │
└──────┬──────────────────┬───────────────────────┬──────────────────┘
       │                  │                       │
┌──────▼───────┐  ┌───────▼────────┐  ┌───────────▼───────────────────┐
│ MongoDB      │  │ 외부 API       │  │ 블록체인                      │
│ Atlas        │  │ 도로명주소     │  │ MockChain (기본)              │
│ · 33개 컬렉션│  │ CODEF 등기부   │  │ Polygon Amoy (어댑터 스켈레톤)│
│ · Vector     │  │ 건축물대장     │  └───────────────────────────────┘
│   Search     │  │ 실거래가       │
│   인덱스     │  │ 사업자등록     │
└──────────────┘  │ OpenDART       │
                  └────────────────┘
```

### 업무 흐름 (생애주기 루프)

```
[계약 전]  주소·보증금 입력 → 등기부 조회 → 위험진단 → 리포트·필요서류 안내 → AI 상담
    ↓
[계약 체결]  전자계약 공동세션 → 특약 합의 → 양측 서명 → 계약 해시 블록체인 앵커
    ↓
[거주 중]  증빙 요청·제출·검증 → 반환계획 관리 → 타임라인·알림 모니터링
    ↓
[사고 후]  사고 접수 → HUG 회수 코크핏 → ML 회수율·우선순위 예측 → 회수 진행 추적
```

---

## 5. 데이터 출처 및 활용

### 5.1 실시간 연동 API (Live)

| 데이터 | 출처 | 시스템 활용 | 상태 |
|---|---|---|---|
| 도로명주소 상세검색 | 주소기반산업지원서비스 (juso.go.kr) | 주소 정규화, 법정동코드(`adm_cd`) 확보 → 지역 사고율 조인 키 | ✅ Live |
| 등기부등본 | **CODEF API (샌드박스)** | 근저당 채권최고액·압류·권리부담 실시간 파싱 → 위험진단 핵심 입력. `registry_snapshots`에 `source_system="api_live"` 저장 | ✅ Live (실패 시 시나리오 폴백) |
| 건축물대장 | 공공데이터포털 건축HUB | 주택 용도·사용승인일 → 주택유형 신호 | ✅ Live |
| 아파트 매매 실거래가 | 공공데이터포털 RTMS | 지역 시세 참조 | ✅ Live |
| 사업자등록 상태조회 | 국세청 (공공데이터포털) | 임대사업자 휴·폐업 여부 → 임대인 신호 | ✅ Live |
| OpenDART 기업공시 | 금융감독원 | 법인 임대인 공시 이력 확인 | ✅ Live |

### 5.2 공공 공개데이터 실집계 (파일 수집 → 정규화)

| 데이터 | 출처 | 주요 컬럼 | 도출 인사이트 | 시스템 활용 |
|---|---|---|---|---|
| 시군구별 보증사고 현황 (272행) | HUG 빅데이터 개방 포털 HOUSTA | 사고건수·사고금액·**사고율(%)**·법정동코드 | 지역별 실제 사고율 ('25.8월 기준 3개월 평균) | 위험진단 "지역 사고율 신호", HUG 사고율 지도 |
| 전세보증금반환보증 발급현황 (6,906행) | HOUSTA | 시도×연월×주택유형 발급건수·보증금액 (2016.01~) | 합성데이터에 없던 **정상 모수(분모)** 확보 | HUG 대시보드 발급 시계열 |
| 전세사기 피해주택 소재지 (416행) | HOUSTA (경공매지원서비스 신청자) | 시군구별 피해주택 수 (2023.7~2025.3) | 실제 피해 주택 위치 분포 | HUG 피해 분포 지도 |
| 서울 연도별 사고·대위변제 (8행) | HOUSTA | 2020~2023 건수·금액 | 시계열 추세 근거 | 발표·대시보드 근거 수치 |
| 전세금안심대출보증 사고율 (10행) | HOUSTA | 연도별 신청·사고건수 → 사고율 파생 | 상품별 사고율 추세 | 상품 비교 시각화 |
| **악성임대인 공개명단 (2,280건)** | HUG 안심전세포털 (법정 공개정보) | 성명·연령·주소(시도)·구상채무액·기준일·근거법령 | 수도권 67% 집중, 구상채무 중앙값 5.45억 | 위험진단 "임대인 신호" — 성명+지역 매칭 결과만 반환 (명단 나열·검색 제공 금지, RAG 코퍼스 제외) |

### 5.3 발제사 제공 데이터

| 데이터 | 구분 | 행 수 | 시스템 활용 |
|---|---|---:|---|
| 비식별 임대차 상담데이터 | **실데이터** (비식별) | 938 | RAG 상담 코퍼스, 분쟁유형·진행단계 분류기 학습 |
| 전세/임대보증 대위변제 | 합성 | 23,107 + 66,579 | 대위변제 규모·패턴 분석 |
| 임대보증 사고현황 | 합성 | 25,687 | 사고사유·시점 패턴 |
| 전세사고 비율 데이터 2종 | 합성 | 69,435 ×2 | 전세가율 고위험 패턴 참조선 (사고사례 84%가 비율 80%↑) |
| 경매현황 / 배당내역 | 합성 | 32,542 / 28,961 | **회수율·소요기간 예측 모델 학습** |

> 합성데이터 7종에는 공통 사건 ID가 없어 파일 간 개별 사건 조인은 하지 않으며, 정상 종료 계약이 없어 "사고 발생확률" 모델은 의도적으로 만들지 않았습니다(8장 참조). ML 산출물에는 "합성데이터 기준, 실데이터 재학습 전제" 원칙을 명시합니다.

### 5.4 Mock 유지 (미연동)

| 데이터 | 사유 | 대체 방식 |
|---|---|---|
| 공시가격 3종 (개별공시지가·개별주택·공동주택) | VWorld 키는 발급됐으나 실제 API URL·레이어명 확정 전 | 진단 엔진이 `official_price_status`를 `missing`으로 처리 — **mock 값으로 채점하지 않음** |
| 온비드 공매 | API 미발급 | 서비스 도메인에서 제외 |

> **데이터 정직성 원칙**: 등기부·공시가격 파생 지표(`jeonse_ratio`, `mortgage_ratio` 등)는 출처가 `live`일 때만 계산합니다. 데이터가 없으면 "위험 낮음"으로 채점하는 대신 `missing_fields`로 보고하고, 프론트에는 mock 여부 라벨 대신 **데이터 출처 상태(`source_status`)** 를 전달합니다.

---

## 6. 데이터 처리 파이프라인

```
raw (원본 수집)                          scripts/collect_raw_data.py
  ├── address/ codef/ building/ rtms/     · API 응답 JSON 원본 보존
  ├── business_status/ dart/              · raw_{출처}_{YYYYMMDD}_{id}.json
  ├── housta/ khug_disclosure/            · HOUSTA 파일·악성임대인 크롤링
  └── hug/ in/ auction/ dividend/         · 발제사 CSV/Excel
        ↓
interim (표준화·전처리)                  parquet 변환, 컬럼 정규화
  ├── hug/ in/ auction/ dividend/          · 금액 단위 통일, 결측 규칙 적용
        ↓
processed (서비스 산출물)
  ├── housta/     → 지역 사고율·발급 시계열·피해분포 CSV (5종)
  ├── khug_disclosure/ → 악성임대인 통합 명단
  ├── ml/         → 학습된 모델 4종(.joblib) + 지표 + SHAP 전역 중요도
  │                 + 회수 우선순위 스코어 CSV
  └── rag/        → RAG 청크 JSONL (상담 1,009 + 포털 70)
        ↓
MongoDB Atlas 적재                       scripts/setup_mongodb.py
  · rag_chunks (임베딩 포함)              scripts/load_rag_jsonl.py
  · registry_snapshots 등 스냅샷          scripts/embed_rag_chunks.py
        ↓
FastAPI 서비스 계층에서 소비
  · public_data.py — processed CSV 파일 캐시 로더 (HUG 대시보드·위험진단)
  · ml_service.py — joblib 모델 로드·추론
  · rag_service.py — Atlas Vector Search
```

모든 산출물에는 수집일이 파일명에 포함되며(`*_20260720.csv`), 수집 이력은 `개별수집데이터 및 API/metadata/`에 기록됩니다. PII 검수 현황은 `metadata/pii_review_260714.md`로 관리합니다.

---

## 7. 데이터베이스 설계

### MongoDB Atlas 선정 이유

- 외부 API 응답(등기부·건축물대장 등)의 **비정형·가변 스키마**를 스냅샷 그대로 보존
- **Atlas Vector Search**로 별도 벡터 DB 없이 RAG 검색 구현
- 해커톤 기간 내 스키마 진화 속도 대응 (Motor 비동기 드라이버 + Repository 패턴)

### 컬렉션 구성 (33개)

| 그룹 | 컬렉션 | 역할 |
|---|---|---|
| 사용자·매물·계약 | `users` `properties` `landlords` `contracts` `contract_versions` | 역할 기반 사용자, 매물-임대인-계약 관계 |
| 외부 데이터 스냅샷 | `registry_snapshots` `building_registry_snapshots` `rtms_transactions` `official_price_snapshots` `api_raw_snapshots` `api_call_logs` `data_sources` | API 응답 원본·파싱 결과, 출처(`source_system`: api_live/mock) 추적 |
| 위험진단 | `risk_assessments` | case_id별 진단 결과·근거·완결성 |
| 증빙·검증 | `evidence_requests` `evidences` `verifications` | 요청→제출(파일 해시)→검증 결정 |
| 생애주기 | `timeline_events` `return_plans` `incidents` `counsels` `counsel_queue` `referrals` `notifications` | 타임라인, 반환계획, 사고, 상담 큐, 알림 |
| 전자계약 | `esign_sessions` | 공동세션·특약·서명·앵커 상태 |
| RAG·LLM | `rag_chunks` `rag_search_logs` `llm_conversations` `llm_messages` `llm_answer_logs` | 임베딩 청크, 검색·답변 로그 |
| ML·블록체인 | `recovery_predictions` `model_versions` `blockchain_transactions` | 예측 이력, 모델 버전, 트랜잭션 |
| 운영 | `system_logs` `schema_migrations` | 시스템 로그, 마이그레이션 이력 |

### 주요 인덱스·무결성 설계

- `contracts`: `(tenant_user_id, property_id, contract_start_date)` **unique** — 중복 계약 방지
- `evidences`: `(evidence_request_id, document_hash)` **unique** — 동일 파일 중복 제출 차단
- `verifications`: `evidence_id` **unique** — 증빙:검증 1:1 보장
- `blockchain_transactions`: `(event_type, reference_id)` **unique** — 중복 앵커링 차단, `tx_hash` unique
- `rag_chunks`: `chunk_id` unique + Vector Search 인덱스 `rag_chunks_vector_index`
- `counsel_queue`: `(status, priority_rank, created_at)` — 큐 정렬 최적화

앱 기동 시 `app/db/indexes.py`가 인덱스를 idempotent하게 보장합니다.

---

## 8. 전세 위험진단 시스템

`POST /api/v1/risk/diagnose` — rule-based 엔진 (`app/services/risk_engine.py`)

### 판단 요소 (5대 신호)

| 신호 | 입력 | 판정 기준 |
|---|---|---|
| **권리관계** | CODEF 등기부 (live) | 압류 존재 → 즉시 HIGH급 감점 / 근저당 채권최고액 비율 >60% 높음, >30% 주의 / 권리부담 비율 |
| **전세가율** | 공시가격 (live일 때만) | 보증금/공시가격 >80% 높음, >60% 주의 — 합성데이터 고위험 패턴(사고사례 84%가 80%↑) 참조 |
| **지역 사고율** | HOUSTA 실집계 (live) | 시군구 사고율 구간별 가점 — 법정동코드로 조인, 근거·기준일 함께 반환 |
| **임대인** | 악성임대인 명단 + 사업자등록 + DART | 성명+시도 일치(`name_sido`) → 강한 경고 / 성명만 일치(`name_only`) → 동명이인 주의 안내. 폐업 여부·법인 공시 확인 |
| **주택유형** | 건축물대장 | 다세대·다가구 사고 집중 패턴 반영 |

### 등급 산정과 데이터 완결성

- 등급: **LOW / MEDIUM / HIGH** (API Contract enum 준수)
- `data_completeness`: 출처별 가중치(등기부·공시가격이 핵심 가중)로 계산
- **데이터 부족 ≠ 안전**: `data_completeness < 0.4`이면 원점수가 낮아도 최소 MEDIUM으로 상향 (`INSUFFICIENT_DATA_FOR_LOW_GRADE` 근거 첨부)
- 등기부·공시가격 파생 지표는 출처가 `api_live`일 때만 계산 — mock 값으로 채점하지 않음

### 응답 구성

`risk_score` · `risk_grade` · `assessment_mode="rule_based_fallback"` · `confidence` · `data_completeness` · `risk_factors`(코드·설명) · `positive_factors` · `missing_fields` · `required_documents` · `recommended_actions` · `source_status`(출처별 live/mock/missing)

> 진단 리포트는 "사고확률"이 아니라 **고위험 패턴 충족도**임을 명시합니다 — 정상 계약 대조군이 없는 데이터 한계를 감안한 정직한 방법론입니다.

---

## 9. ML 모델

`scripts/train_ml_models.py`로 학습, `backend/app/services/ml_service.py`가 joblib 아티팩트를 서빙합니다.

### 모델 4종 + 파생 스코어 (2026-07-20 학습, seed=42)

| 모델 | 알고리즘 | 학습 데이터 | 성능 (hold-out) | 서빙 엔드포인트 |
|---|---|---|---|---|
| **예상 회수율** (`recovery_ratio_lgbm`) | LightGBM 회귀 → LOW/MED/HIGH 등급화 | 배당내역 합성 28,961 (train 23,168 / test 5,793) | MAE 0.113, R² 0.404, 등급 정확도 71.9% | `POST /ml/recovery/predict` |
| **배당 소요기간** (`days_to_dividend_lgbm`) | LightGBM 회귀 | 동일 (음수 소요일 38건 제외) | MAE 100.9일, 중앙값 AE 78.6일 | 동일 응답에 통합 |
| **분쟁유형 분류** (`dispute_clf`) | TF-IDF + 분류기 (5클래스: 전세사기·보증금미반환·경공매·묵시적갱신·기타) | 상담 938 (train 748 / test 187) | 정확도 73.8%, macro-F1 0.723 | `POST /ml/counsel/classify` |
| **진행단계 분류** (`stage_clf`) | 동일 (6클래스: 상담·내용증명·임차권등기·소송·판결집행·HUG이행청구) | 동일 | 정확도 66.8%, macro-F1 0.605 | 동일 응답에 통합 |
| **회수 우선순위 스코어** | (파생) 예상회수액 = 회수율×채권금액, 소요기간 페널티 가중 | 위 2모델 출력 | — | `GET /hug/dashboard/priority` |

### SHAP 설명 구조

- 회수율 예측 응답에 건별 **SHAP 요인 기여도**(예: "채권구분=구상채권 → 회수율 하향") 포함
- 전역 중요도는 `processed/ml/shap_global_*.csv`로 별도 산출, 프론트 `ShapBars` 컴포넌트로 시각화
- `GET /ml/models/info`로 모델 파일·지표·기준(basis) 공개

### 개발 상태와 데이터 한계

- **"사고 발생확률" 모델은 의도적으로 제외** — 전 사례가 사고 데이터라 정상 대조군이 없어 학습·검증 불가. 대신 HOUSTA 발급현황(모수)×사고현황(분자) 결합으로 지역×기간 실제 사고율을 통계적 사전확률로 사용
- 모든 지표에 `"합성데이터/비식별 상담데이터 기준. 실제 HUG 성능 아님"` 명시 — 실데이터 확보 시 동일 파이프라인으로 재학습 가능한 구조

---

## 10. RAG·LLM 시스템

### 코퍼스 (총 1,079 청크, `dive2026.rag_chunks`)

| 소스 | 청크 수 | 내용 |
|---|---:|---|
| 비식별 상담데이터 | 1,009 | 변호사 심층상담 938건 기반, 500~900자 청크 (overlap 80~150자) |
| 안심전세포털 공식자료 (`khug_portal`) | 70 | 전세사기 유형별 사례·대처방안, 계약 단계별 유의사항, 보증가입, 피해지원 프로그램, 경공매 지원 특별법 등 23페이지 (`scripts/crawl_khug_portal.py`) |

### 검색·답변 흐름

```
질문 → OpenAI 임베딩 (text-embedding-3-large, 1024차원)
     → Atlas Vector Search ($vectorSearch, 인덱스: rag_chunks_vector_index)
        · topic/region 필터 → 결과 없으면 필터 완화 재검색
     → LLM 답변 생성 (JSON 강제: 결론 + 근거 요약)
     → 출처 카드 (공식자료/상담사례 배지 구분) + 면책문구
```

- **Fallback 체계**: OpenAI 키 부재·호출 실패 시 키워드 검색으로 전환하고 `is_mock=true` 명시 반환 (500 에러 대신 `ERROR-009`). LLM 생성 실패 시 근거 발췌 모드로 강등
- **개인정보 보호**: 검색 로그(`rag_search_logs`)에 질문·답변 300자 절단 저장, 원문 스니펫은 항상 마스킹·절단 후 반환. 상담 청크는 정규식 5종(전화·주민번호·이메일·계좌·상세주소) 전수 스캔 0건 검출 — 단 자유서술 실명 가능성 때문에 사람 검수 전까지 `pii_removed=false` 유지
- 근거가 없으면 답변을 거부하고 상담사 이관(`POST /counsel-queue`)을 안내

---

## 11. 블록체인 시스템

### 설계 (`app/services/blockchain/`)

```
이벤트 발생 (위험진단 확정 / 증빙 제출 / 검증 결정 / 전자계약 서명 완료)
  → canonical JSON → SHA-256 result_hash 생성 (utils/hashing.py)
  → (event_type, reference_id) 기존 트랜잭션 조회 — 있으면 기존 tx 반환 (중복 앵커 차단)
  → BlockchainAdapter.anchor() → tx_hash 발급 → blockchain_transactions 저장
```

| 구분 | 온체인 (앵커) | 오프체인 (MongoDB) |
|---|---|---|
| 저장 항목 | `result_hash` (SHA-256), event_type, reference_id | 원문 데이터 전체, tx 상태, 타임스탬프 |
| 원칙 | **원문·개인정보는 절대 체인에 올리지 않음** | 해시 재계산으로 위변조 검증 |

### 구현 현황

- **MockBlockchainAdapter** (기본, `BLOCKCHAIN_MODE=mock`): 외부 RPC 없이 `0x`+64hex tx_hash를 즉시 `Confirmed`로 발급 — 전 플로우 동작
- **PolygonBlockchainAdapter** (`BLOCKCHAIN_MODE=polygon`): Polygon Amoy 테스트넷용 어댑터 인터페이스 완성, 실연동은 스켈레톤 (향후 계획)
- **전자계약 앵커링**: 양측 서명 완료 시 계약문서(당사자·특약·서명 시각) canonical JSON의 SHA-256을 자동 앵커 → `POST /esign/contracts/{id}/verify`로 해시 재계산 일치/불일치 검증
- 조회: `GET /blockchain` (목록), `GET /blockchain/{tx_id}` (상세 — 프론트 검증 화면 연결)

---

## 12. 구현 현황

### 백엔드 — 61 엔드포인트 전체 구현 (기준: `docs/API_Contract_260721.yaml`)

| 상태 | 내용 |
|---|---|
| ✅ 구현 완료 | 인증·사용자·매물·임대인·계약·위험진단·증빙·검증·타임라인·반환계획·RAG·블록체인·전자계약(7)·HUG 대시보드(5)·상담 큐(4)·사고(3)·알림(4)·ML(3) |
| 🔶 Fallback 동작 | RAG (OpenAI 키 없으면 키워드 검색), 등기부 (CODEF 실패 시 시나리오 폴백), 블록체인 (Mock Chain) |
| ⬜ 설계만 존재 | Polygon 실연동, 공시가격 3종 live 수집, 온비드, `GET /admin/system-logs` |

### 프론트엔드 — 전 역할 화면 + 실데이터 연동

- 2026-07-21 전면 리디자인: HUG 디자인 토큰(`frontend/styles/globals.css`), 시각화 컴포넌트 8종(`components/viz/` — DonutGauge, ShapBars, ContractStepper, RiskSignals, TimelineList 등), 전 역할 공통 셸
- 실데이터 연동 완료: 로그인/세션, 임차인 대시보드·계약 등록·계약 상세(진단·타임라인·반환계획·증빙), AI 상담(채팅형), 임대인 홈, 상담사 검증 큐, HUG 코크핏, 관리자(사용자·블록체인 로그), 블록체인 검증 상세
- 서비스 계층 15개 모듈(`frontend/services/`)이 백엔드 61 op 대응 — HUG 전용 대시보드 5종·알림·전자계약 화면 연동은 진행 중 (`docs/구현현황_문서정합_260721.md` 3장의 우선순위 로드맵 참조)

### 테스트

```
backend$ pytest -q
45 passed  (2026-07-21 실측)
```

`mongomock-motor`로 Atlas 없이 전량 실행 가능 — 인증·계약·위험진단·증빙·RAG·블록체인·전자계약·사고/상담큐/알림·ML/HUG·PII 마스킹·OpenAPI 정합 커버.

---

## 13. API 구성

Base URL: `/api/v1` — 총 **61 endpoints**. 전체 스키마는 `docs/API_Contract_260721.yaml`.

| 도메인 | 주요 엔드포인트 |
|---|---|
| 인증 | `POST /auth/signup` `POST /auth/login` `GET /auth/me` `POST /auth/logout` |
| 사용자 | `GET /users/{id}`, `GET /admin/users` |
| 매물·등기 | `GET·POST /properties`, `GET /properties/{id}`, `GET·POST /properties/{id}/registry/latest·refresh` |
| 임대인 | `GET·POST /landlords`, `GET /landlords/{id}` |
| 계약 | `GET·POST /contracts`, `GET /contracts/{id}`, `GET .../timeline`, `GET .../return-plan`, `POST /return-plans` |
| 위험진단 | `POST /risk/diagnose` (동기 200 응답), `GET /risk/{case_id}` |
| 증빙·검증 | `GET·POST /evidence-requests`, `POST /evidence`, `GET /verifications/{evidence_id}`, `POST .../decision` |
| RAG | `POST /rag/search`, `POST /rag/answer` (출처 카드 포함) |
| ML | `POST /ml/recovery/predict`, `POST /ml/counsel/classify`, `GET /ml/models/info` |
| 전자계약 | `POST /esign/sessions`, `POST .../join`, `GET /esign/sessions/{id}`, `POST .../terms`, `POST .../sign`, `POST /esign/contracts/{id}/verify` |
| HUG 대시보드 | `GET /hug/dashboard/summary·priority·region-risk·issuance·victims` |
| 사고·상담·알림 | `GET·POST /incidents`, `PATCH .../status`, `GET·POST /counsel-queue`, `GET /notifications`, `PATCH .../read` |
| 블록체인 | `POST /blockchain/anchor`, `GET /blockchain`, `GET /blockchain/{tx_id}` |

- **Swagger UI**: http://localhost:8000/docs · **ReDoc**: http://localhost:8000/redoc
- 공통 응답 봉투·오류코드 체계는 `docs/Backend_API_명세서_260714.md` 준수

---

## 14. 기술 스택

| 계층 | 기술 |
|---|---|
| Frontend | Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS · shadcn/ui (Base UI) · TanStack Query 5 · react-hook-form + zod · Recharts · Framer Motion · sonner |
| Backend | FastAPI 0.115 · Python 3.12 · Pydantic 2 · Motor 3.6 (async MongoDB) · python-jose (JWT) · passlib/bcrypt · httpx |
| Database | MongoDB Atlas · Atlas Vector Search |
| AI/ML | OpenAI (text-embedding-3-large 1024d, Chat Completions) · LightGBM · scikit-learn · SHAP · pandas |
| Blockchain | SHA-256 해시 앵커링 · Mock Chain (기본) · Polygon Amoy 어댑터 (스켈레톤) |
| 테스트·도구 | pytest + pytest-asyncio + mongomock-motor (45 tests) · ESLint |

---

## 15. 프로젝트 구조

```
DIVE2026/
├── frontend/                  # Next.js 16 앱
│   ├── app/                   #   (auth)·(common)·tenant·landlord·advisor·hug·admin 라우트
│   ├── components/            #   ui(shadcn)·viz(시각화 8종)·contracts·hug·rag·common
│   ├── services/              #   API 클라이언트 15모듈 (도메인별)
│   ├── hooks/ stores/ types/  #   상태·타입
│   └── styles/globals.css     #   HUG 디자인 토큰
├── backend/                   # FastAPI 앱
│   ├── app/
│   │   ├── api/v1/endpoints/  #   라우터 17개 (도메인 1:1)
│   │   ├── services/          #   risk_engine·ml_service·rag_service·blockchain·esign 등
│   │   ├── repositories/      #   Motor 컬렉션 CRUD 캡슐화
│   │   ├── models/ schemas/   #   컬렉션 TypedDict · Pydantic DTO
│   │   ├── core/ db/ middleware/ utils/
│   │   └── main.py
│   ├── mock_data/ storage_data/ secrets/
│   ├── scripts/               #   seed_demo_users.py · seed_demo_contracts.py
│   └── tests/                 #   pytest 45건
├── scripts/                   # 데이터 파이프라인 (수집·전처리·학습·임베딩)
│   ├── collect_raw_data.py collect_housta_data.py collect_bad_landlords.py
│   ├── process_housta_data.py crawl_khug_portal.py
│   ├── train_ml_models.py embed_rag_chunks.py load_rag_jsonl.py
│   └── setup_mongodb.py
├── 개별수집데이터 및 API/      # 데이터 레이크
│   ├── raw/                   #   API 응답·파일 원본 (15개 출처 폴더)
│   ├── interim/               #   표준화 parquet
│   ├── processed/             #   housta·khug_disclosure·ml(모델 4종)·rag(청크 JSONL)
│   ├── mock/                  #   폴백 시나리오 JSON 13종
│   └── metadata/              #   API 등록현황·컬럼 인벤토리·PII 검수·수집 이력
├── dive 데이터/                # 발제사 제공 원본 (상담 938 + 합성 CSV 7종)
└── docs/                      # 설계·명세 문서 (API Contract, 기획안, 정합 보고서 등)
```

---

## 16. 설치 및 실행 방법

### 사전 요구사항

Python 3.11+ (권장 3.12) · Node.js 20+ · MongoDB Atlas 접근 권한

### 1) 환경변수

```bash
cd backend
cp .env.example .env   # MONGODB_URI, JWT_SECRET_KEY, OPENAI_API_KEY,
                       # CODEF_* , DATA_GO_KR_API_KEY 등 설정
```

> 실제 키 값은 `.env`·`secrets/`에만 보관하며 Git에 커밋하지 않습니다.

### 2) MongoDB 초기화 & 시드

```bash
python scripts/setup_mongodb.py            # 컬렉션 33개·인덱스·초기 시드
cd backend && python scripts/seed_demo_users.py   # 데모 계정 5종
```

### 3) 백엔드

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload              # http://localhost:8000/docs
```

### 4) 프론트엔드

```bash
cd frontend
npm install
npm run dev                                # http://localhost:3000
```

### 5) RAG 데이터 적재 (선택)

```bash
backend/.venv/bin/python scripts/load_rag_jsonl.py "개별수집데이터 및 API/processed/rag/rag_chunks_khug_260720.jsonl"
backend/.venv/bin/python scripts/embed_rag_chunks.py   # 임베딩 없는 청크만 추가 임베딩
```

### 6) 테스트

```bash
cd backend && pytest -q    # Atlas 없이 mongomock으로 45건 전량 실행
```

---

## 17. 보안 및 개인정보 보호

| 영역 | 조치 |
|---|---|
| 인증·인가 | JWT Bearer + 5역할 RBAC (엔드포인트별 역할 검사) |
| 비밀정보 해시 | 비밀번호 bcrypt, 사업자등록번호 해시 저장(`business_registration_number_hash`) |
| 증빙 무결성 | 제출 파일 SHA-256 해시 저장, `(요청, 해시)` unique로 위·변조/중복 차단 |
| 개인정보 마스킹 | RAG 응답 스니펫 마스킹·절단(`utils/pii_masking.py`, 전용 테스트 존재), 검색 로그 300자 절단 |
| 악성임대인 명단 | 법정 공개정보라도 명단 나열·검색 미제공 — 매칭 여부(true/false + 근거법령·기준일)만 반환, 시연 시 실명 마스킹, RAG 코퍼스 제외 |
| 블록체인 | **원문·개인정보 온체인 저장 금지** — SHA-256 해시만 앵커 |
| 키 관리 | `.env`·`secrets/` gitignore, 문서·코드에 키 값 기록 금지 |
| 데이터 윤리 | 비식별 데이터 재식별 시도 금지, PII 정규식 5종 전수 스캔 + 사람 검수 전 `pii_removed=false` 보수적 유지 |

---

## 18. 한계 및 향후 계획

### 현재 한계

- **공시가격 3종 미연동** — VWorld 키는 발급됐으나 API URL·레이어명 확정 전. 전세가율 신호가 `missing` 처리됨 (mock으로 채점하지 않는 원칙 유지)
- **ML 학습데이터 한계** — 합성데이터 기준 성능이며 실제 HUG 성능이 아님. 정상 계약 대조군 부재로 사고확률 모델 불가, 파일 간 공통 사건 ID 부재로 사건 단위 조인 불가
- **블록체인 Mock Chain** — Polygon Amoy는 어댑터 인터페이스만 완성
- **RAG PII 사람 검수 미완** — 정규식 스캔 0건이나 자유서술 실명 가능성으로 보수적 처리 중
- **프론트 미연동 잔여분** — HUG 전용 대시보드 API 5종·알림·전자계약 화면 연결 (백엔드는 완성, 우선순위 로드맵 수립됨)

### 향후 계획

1. **Polygon Amoy 실연동** — 어댑터 교체만으로 전환 가능한 구조 완성됨 (`BLOCKCHAIN_MODE=polygon`)
2. **실제 운영데이터 확보 및 모델 재학습** — HUG 실데이터로 동일 파이프라인 재학습·검증 (재학습 전제 아키텍처)
3. **공시가격 3종 live 수집** → 전세가율 신호 실계산 활성화
4. **프론트엔드 고도화** — HUG 코크핏에 전용 API 5종 연결, 전자계약·알림 화면 완성, 회수 시뮬레이터
5. **RAG 코퍼스 확장** — 주택임대차보호법·전세사기특별법 법령 청크 추가, PII 사람 검수 완료

---

## 관련 문서

| 문서 | 위치 |
|---|---|
| API 계약 명세 (현행) | `docs/API_Contract_260721.yaml` |
| 구현현황·문서정합 보고서 | `docs/구현현황_문서정합_260721.md` |
| 솔루션 기획안 (생애주기 루프) | `docs/솔루션_재정비_기획안_260718.md` |
| 백엔드 상세 README | `backend/README.md` |
| 데이터 사전 (발제사 데이터) | `dive 데이터/README.md` |
| 데이터 수집·API 가이드 | `docs/데이터수집_및_API가이드_260714.md` |
| ML 개발 가이드 | `docs/ML개발가이드_260714.md` |
| 블록체인 설계서 | `docs/Blockchain_설계서_260714.md` |
| MongoDB 사용 매뉴얼 | `docs/MongoDB_사용_매뉴얼_260714.md` |
