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
| ① 사고 후 회수 | HUG 대위변제 채권의 회수 우선순위 판단이 어려움 | ML 기반 회수율·소요기간 예측 + 회수 우선순위 스코어 → **HUG 채권회수 대시보드** |
| ② 계약 전 예방 | 임차인이 계약 전 위험 신호를 알기 어려움 | 등기부 실시간 조회 + 공공데이터 결합 **rule-based 위험진단** + 악성임대인 명단 대조 |

### 핵심 차별점

1. **역할 4종 통합 생태계** — 임차인·임대인·상담사·HUG가 같은 데이터 위에서 각자의 화면을 사용
2. **HUG 채권회수 대시보드** — HOUSTA 실집계 + ML 예측으로 회수 업무 지원
3. **RAG 상담엔진** — 비식별 상담사례 938건 + 안심전세포털 공식자료를 근거로 한 출처 표시형 AI 상담
4. **전자계약 블록체인 앵커링** — 계약 원본 해시를 체인에 기록해 사고 후 분쟁·회수 단계의 증거력 확보

---

## 2. 주요 사용자

| 역할 | 데모 계정 | 주요 기능 |
|---|---|---|
| **임차인** (tenant) | `tenant01@example.com` | 계약 등록, 위험진단 리포트, AI 전세상담, 증빙 요청, 사고 접수, 전자계약 |
| **임대인** (landlord) | `landlord01@example.com` | 증빙 제출, 반환계획 등록, 전자계약 상대방 플로우 |
| **상담사** (advisor) | `advisor01@example.com` | 증빙 검증 큐, 상담 현황(ML 자동분류 태그), 유사사례 검색 |
| **HUG 담당자** (hug_admin) | `hugadmin01@example.com` | 채권회수 대시보드(우선순위 채권·사고율 지도·발급 시계열·피해 분포), 사고 큐 |
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
| **사고위험 PU PoC** | 합성 사고 P + RTMS 미라벨 U 기반 위험점수·백분위, 계약별 성공/범위밖/실패 이력 | ✅ 백엔드 서빙·배치 구현 |
| **HUG 사고 전 예방** | 진행 계약 목록, 예방 우선순위, D-90/60/30 항목별 증빙 bundle, 3자 알림·조치 | ✅ 백엔드 구현 |
| **HUG 보증이행** | 사고통지 → 서류 → 심사 → 명도 → 대위변제 → 채권등록·인계 상태머신 | ✅ 백엔드 구현 |
| **HUG 등록채권 관리** | 병렬 상태축, append-only 원장, 저장형 회수전망 예측, 종결·감사이력 | ✅ 백엔드 구현 |
| **HUG 대시보드** | 업무대장·합성 참조·공공 집계를 분리한 KPI와 발급·사고 추이 | ✅ 백엔드 보완 |
| **사고 접수·상담 현황·알림** | 사고 접수→상태 추적, 챗봇→상담사 이관 큐, 구조화 예방 알림 | ✅ 구현 |

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
│  api/v1 (106 operations) → services → repositories                  │
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
│ · 업무 컬렉션│  │ CODEF 등기부   │  │ Polygon Amoy (어댑터 스켈레톤)│
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
[거주 중]  사고위험 PoC·Rule → D-90/60/30 증빙·신용보강 → 3자 예방 알림
    ↓
[사고 후]  임차인 사고통지 → 이행청구·심사 → 명도·대위변제 → 채권등록
    ↓
[회수]  법무·경매·배당·입금 원장 → ML 회수전망·우선순위 → 종결
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

> 합성데이터 7종에는 공통 사건 ID가 없어 파일 간 개별 사건 조인은 하지 않습니다. 특히 사고표본과 RTMS 계약을 대조할 공통키가 없으므로 RTMS를 확정 정상으로 단정할 수 없습니다. 260721 case-control 모델은 비교 baseline으로만 유지하고, 발제사 조언에 따라 **260723 RTMS를 미라벨(U)로 처리하는 bagging PU Learning PoC로 보완**했습니다(9장 참조).

#### 5.3.1 미라벨 계약군 — RTMS 전월세 실거래 (PU Learning, 260723 보완)

발제 데이터에는 확인된 사고 사례만 있고 정상 종료 라벨이 없습니다. 국토부 실거래가(RTMS) **전월세 신고 건별 데이터**를 추가 확보했지만 개별 사고 여부를 알 수 없으므로, 이를 정상군이 아닌 **미라벨군(Unlabeled)** 으로 사용합니다.

| 항목 | 내용 |
|---|---|
| 수집 스크립트 | `scripts/collect_rtms_rent.py` — 전월세 4종 API(아파트·연립다세대·단독다가구·오피스텔) × 대표 시군구 17개(세종 포함). 260723 지역코드 라벨 2건 정정, 기준월 CLI, 전 페이지 수집, 원문 XML·셀별 manifest·완전성 gate를 코드에 반영 |
| **현재 모델 적용 산출** | `processed/control/rtms_jeonse_controls_260721.csv` — 전세 18,765건(2025.02~06, 기존 첫 페이지 중심 표본). 파일명·기존 `is_accident=0`과 무관하게 새 모델에서는 전부 **사고 여부 미확인 U**로 해석 |
| 다음 재수집 산출 | `processed/control/rtms_jeonse_unlabeled_<시작월>_<종료월>_<실행시각>.csv` + `.manifest.json` — `label_status=unlabeled`; 모든 요청 셀이 완전하지 않으면 학습용 CSV를 만들지 않으며 부분 CSV는 학습기가 거부 |
| 공통 피처 | 지역(시도), 주택유형, `log1p(보증금)` — P·U에서 함께 존재하는 축만 사용 |
| 키 상태 | `DATA_GO_KR_API_KEY`로 전월세 4종 활용신청 완료(260721, 자동승인) |

방법론 주의: P는 합성 사고군, U는 HUG 가입 여부·사고 여부를 모르는 RTMS 전체 전세실거래라 모집단과 출처가 다릅니다. 실제 정상 라벨이 없으므로 ROC/PR은 `P-vs-U proxy`로만 보고, Brier·정확도·ECE를 실제 확률 성능으로 제시하지 않습니다. 상세 결과는 `processed/ml/ACCIDENT_MODEL_PU_POC_README.md`.

### 5.4 Mock 유지 (미연동)

| 데이터 | 사유 | 대체 방식 |
|---|---|---|
| ~~공시가격 3종~~ | **260721 live 전환 완료** — VWorld NED 데이터 API(`getApartHousingPriceAttr`·`getIndvdHousingPriceAttr`·`getIndvdLandPriceAttr`, `domain=등록 서비스 URL` 필수) 실호출 검증 | `POST /properties/{id}/official-price/refresh` → `official_price_snapshots` 저장, 전세가율 신호 실계산. 가격 미제공 필지는 `missing` 유지 |
| 온비드 공매 | **배제 확정(260721)** — API 미발급, mock 파일도 삭제 | 서비스 도메인에서 완전 제외 |

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
  │                 + 회수 우선순위 스코어 CSV + 사고위험 PU PoC(accident_clf_pu_poc)
  ├── control/    → RTMS 전세 미라벨 U CSV (PU PoC용, 현재 18,765건)
  └── rag/        → RAG 청크 JSONL (상담 1,009 + 포털 97 + 법령 124)
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
| 생애주기 | `timeline_events` `return_plans` `incidents` `counsels` `counsel_queue` `referrals` `notifications` | 타임라인, 반환계획, 사고, 상담 현황, 알림 |
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

> 현재 `/risk/diagnose` 리포트는 계속 **고위험 패턴 충족도**를 반환합니다. PU 모델은 별도 `/ml/accident/predict`와 HUG 사고 전 계약 API에 연결했지만, 실제 정상 종료계약으로 보정·검증하기 전에는 `AGGREGATE_PRIOR_ALIGNED_UNVALIDATED` PoC로만 노출합니다.

---

## 9. ML 모델

`scripts/train_ml_models.py`로 학습, `backend/app/services/ml_service.py`가 joblib 아티팩트를 서빙합니다.

### 모델 4종 + 파생 스코어 + 사고위험 PU PoC (2026-07-20~23 학습, seed=42)

| 모델 | 알고리즘 | 학습 데이터 | 성능 (hold-out) | 서빙 엔드포인트 |
|---|---|---|---|---|
| **예상 회수율** (`recovery_ratio_lgbm`) | LightGBM 회귀 → LOW/MED/HIGH 등급화 | 배당내역 합성 28,961 (train 23,168 / test 5,793) | MAE 0.113, R² 0.404, 등급 정확도 71.9% | `POST /ml/recovery/predict` |
| **배당 소요기간** (`days_to_dividend_lgbm`) | LightGBM 회귀 | 동일 (음수 소요일 38건 제외) | MAE 100.9일, 중앙값 AE 78.6일 | 동일 응답에 통합 |
| **분쟁유형 분류** (`dispute_clf`) | TF-IDF + 분류기 (5클래스: 전세사기·보증금미반환·경공매·묵시적갱신·기타) | 상담 938 (train 748 / test 187) | 정확도 73.8%, macro-F1 0.723 | `POST /ml/counsel/classify` |
| **진행단계 분류** (`stage_clf`) | 동일 (6클래스: 상담·내용증명·임차권등기·소송·판결집행·HUG이행청구) | 동일 | 정확도 66.8%, macro-F1 0.605 | 동일 응답에 통합 |
| **회수 우선순위 스코어** | (파생) 예상회수액 = 회수율×채권금액, 소요기간 페널티 가중 | 위 2모델 출력 | — | `GET /hug/dashboard/priority` |
| **사고위험 PU PoC** (`accident_clf_pu_poc`) | LightGBM bagging PU, 10 bags | 합성 사고군 P 18,054 + RTMS 전세 미라벨 U 18,765 (공유 8개 시도) | P-vs-U **proxy** ROC-AUC 0.9108 · PR-AUC 0.9025, U 상위 10% 기준 P recall 71.67% | `POST /ml/accident/predict` + HUG 계약 배치 |

### SHAP 설명 구조

- 회수율 예측 응답에 건별 **SHAP 요인 기여도**(예: "채권구분=구상채권 → 회수율 하향") 포함
- 전역 중요도는 `processed/ml/shap_global_*.csv`로 별도 산출, 프론트 `ShapBars` 컴포넌트로 시각화
- `GET /ml/models/info`로 모델 파일·지표·기준(basis) 공개

### 사고위험 PoC — Positive–Unlabeled 보완 (260723)

발제사 답변의 두 방안 중, 실제 사고목록과 RTMS를 계약 단위로 대조하는 방안은 공통키가 없어 적용할 수 없습니다. 이에 RTMS를 확정 정상으로 오라벨링하지 않는 **PU Learning**을 구현했습니다.

- 학습: `scripts/build_accident_model_pu.py` → `processed/ml/accident_clf_pu_poc_260723.joblib`, 지표 JSON, `ACCIDENT_MODEL_PU_POC_README.md`
- 방식: 각 bag에서 알려진 사고 P와 bootstrap한 미라벨 U를 학습하고 10개 LightGBM 점수를 평균. 별도 P calibration split에서 Elkan–Noto `c`를 진단
- 누출 완화: P와 U를 먼저 합친 뒤 동일한 `시도·주택유형·보증금` feature vector가 train/calibration/test 어느 출처에도 교차 유입되지 않도록 **전역 그룹 분할**(`global_group_overlap_count=0`), 반복행은 빈도 제곱근 역가중
- proxy 진단: P-vs-U ROC-AUC 0.9108, PR-AUC 0.9025, U 상위 약 10% 임계에서 알려진 P recall 0.7167·proxy lift 6.63. 이는 실제 정상군 기반 성능이 아니라 두 출처의 분리도를 포함함
- 출력: `pu_risk_score`와 U 참조 `risk_percentile`이 기본값. `prior_aligned_estimate`는 HOUSTA 전국 최근 3개월 사고율 1.6%에 calibration U 평균만 정렬한 `AGGREGATE_PRIOR_ALIGNED_UNVALIDATED` 값(test U 평균 1.8563%)
- 추론 안전장치: 미지원 지역·주택유형, 결측·0 이하 또는 학습 범위(200만원~55억원) 밖 보증금은 임의 점수 대신 `NOT_SCORABLE`과 실패 사유를 반환
- 재현성: artifact schema·전처리 매핑·명시적 하이퍼파라미터·학습 스크립트/입력/HOUSTA prior SHA-256·수집기간·라이브러리 버전을 joblib/metrics에 기록. seed=42 재실행 시 artifact와 metrics SHA-256 동일 확인
- 계산하지 않은 지표: 확정 정상 라벨이 없으므로 Brier·ECE·정확도는 실제 확률 성능으로 계산·표시하지 않음
- 과거 baseline: `accident_clf_poc_260721`의 ROC-AUC 0.921은 RTMS를 확정 negative로 둔 비교 결과로만 보존하며 운영 모델 성능으로 사용하지 않음
- **현재는 백엔드 연결된 PoC** — 계약별 추론·이력·일괄 갱신·예방업무 연동까지 구현했지만 UI는 이번 범위에서 변경하지 않았다. 실제 HUG 정상 종료/사고 코호트로 시간순 외부검증과 확률 calibration을 마치기 전에는 운영 확률이 아니다.

#### 보완 계획과 실행 상태

| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | RTMS의 확정 Negative 라벨 제거, U 의미로 전환 | ✅ 완료 |
| 2 | P·U 통합 전역 그룹 split로 교차 출처 누출 방지·빈도 역가중 | ✅ 완료 (`global overlap=0`) |
| 3 | 10-bag LightGBM PU 학습과 artifact 추론 smoke test | ✅ 완료 |
| 4 | HOUSTA 1.6% 집계 prior 정렬 및 미검증 상태코드 부여 | ✅ 완료 |
| 5 | RTMS 지역코드 라벨 정정·기준월·전 페이지·원문/manifest·완전성 gate | ✅ 코드 보완, **현재 artifact에는 미적용**(세종 U 포함 재수집 필요) |
| 6 | 입력 SHA·기간·전처리·의존성 metadata 및 범위 밖 입력 차단 | ✅ 완료 |
| 7 | HUG 실제 계약의 사고/정상 종료 라벨로 외부검증·확률보정 | ⬜ 데이터 제공 후 수행 |
| 8 | 사고 전 계약관리 API·멱등 sweep·예측 배치 연결 | ✅ 백엔드 완료 (UI는 별도 범위) |

---

## 10. RAG·LLM 시스템

### 코퍼스 (총 **1,230 청크**, `dive2026.rag_chunks` — 260721 적재·임베딩 완료)

| 소스 | 청크 수 | 내용 |
|---|---:|---|
| 비식별 상담데이터 | 1,009 | 변호사 심층상담 938건 기반, 500~900자 청크 (overlap 80~150자) |
| 안심전세포털 공식자료 (`khug_portal`) | 97 | 전세사기 유형별 사례·대처방안, 계약 단계별 유의사항, 보증가입, 피해지원 프로그램, 경공매 지원 특별법, FAQ·피해확인서·든든전세주택 등 33페이지 (`scripts/crawl_khug_portal.py`, 260721 사이트맵 대조로 10페이지 보강) |
| 법령 조문 (`law`) | 124 | 주택임대차보호법(47)·전세사기피해자 지원 특별법(77) 조문 단위 청크, 국가법령정보센터 DRF API (`scripts/collect_law_chunks.py`, OC=hugin) — 벡터검색 실동작 확인 |

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

### 백엔드 — API Contract 기반 + HUG 업무확장 106 operations

| 상태 | 내용 |
|---|---|
| ✅ 구현 완료 | 기존 API Contract 도메인 + 사고위험 PoC·사고 전 계약/예방·보증이행 상태머신·등록채권 원장/예측/종결·S1~S7 Seed·통합 KPI |
| 🔶 Fallback 동작 | RAG (OpenAI 키 없으면 키워드 검색), 등기부 (CODEF 실패 시 시나리오 폴백), 블록체인 (Mock Chain) |
| ⬜ 설계만 존재 | Polygon 실연동, `GET /admin/system-logs` |

### 프론트엔드 — 전 역할 화면 + 실데이터 연동

- 2026-07-21 전면 리디자인: HUG 디자인 토큰(`frontend/styles/globals.css`), 시각화 컴포넌트 8종(`components/viz/` — DonutGauge, ShapBars, ContractStepper, RiskSignals, TimelineList 등), 전 역할 공통 셸
- 실데이터 연동 완료: 로그인/세션, 임차인 대시보드·계약 등록·계약 상세(진단·타임라인·반환계획·증빙), AI 상담(채팅형), 임대인 홈, 상담사 검증 큐, HUG 채권회수 대시보드, 관리자(사용자·블록체인 로그), 블록체인 검증 상세
- 서비스 계층 15개 모듈(`frontend/services/`)은 기존 API Contract 범위를 대응한다. 260723에 추가한 사고 전 예방·보증이행·등록채권 백엔드 API의 UI 연동은 이번 범위에서 수정하지 않았다.

### 테스트

```
backend$ pytest -q
92 passed  (2026-07-23 실측)
```

`mongomock-motor`로 Atlas 없이 전량 실행 가능 — 기존 도메인 회귀와 PU 예측·D-day 예방·이행청구 상태전이·원장·회수예측·종결·시연 Seed·출처 분리를 함께 검증합니다.

---

## 13. API 구성

Base URL: `/api/v1` — OpenAPI 기준 **106 operations**. 기존 계약은 `docs/API_Contract_260721.yaml`, HUG 확장은 `docs/HUG_백엔드_구현현황_260723.md`를 따릅니다.

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
| ML | `POST /ml/accident/predict`, `POST /ml/recovery/predict`, `POST /ml/counsel/classify`, `GET /ml/models/info` |
| 전자계약 | `POST /esign/sessions`, `POST .../join`, `GET /esign/sessions/{id}`, `POST .../terms`, `POST .../sign`, `POST /esign/contracts/{id}/verify` |
| HUG 대시보드 | 기존 5종 + `GET /hug/dashboard/overview·issuance-incident-trend` |
| HUG 사고 전 계약 | `GET /hug/contracts`, 단건·일괄 예측, prevention 조회·조치·sweep |
| HUG 보증이행 | `GET /hug/incidents`, `/performance-claims/{id}` 문서·심사·명도·지급·채권등록·인계 액션 |
| HUG 채권관리 | `/hug/recovery` 현황·목록·상세·병렬 이벤트·원장·예측이력·종결 |
| HUG 시연 Seed | `POST /hug/demo/seed`, `GET /hug/demo/manifest` |
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
| 테스트·도구 | pytest + pytest-asyncio + mongomock-motor (92 tests) · ESLint |

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
│   └── tests/                 #   pytest 92건
├── scripts/                   # 데이터 파이프라인 (수집·전처리·학습·임베딩)
│   ├── collect_raw_data.py collect_housta_data.py collect_bad_landlords.py
│   ├── process_housta_data.py crawl_khug_portal.py collect_law_chunks.py
│   ├── train_ml_models.py embed_rag_chunks.py load_rag_jsonl.py
│   ├── collect_rtms_rent.py build_accident_model_pu.py    # RTMS U 수집·PU PoC
│   ├── build_accident_model_poc.py                         # 과거 case-control baseline
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
python scripts/setup_mongodb.py                         # 기본 컬렉션·인덱스·초기 시드
backend/.venv/bin/python backend/scripts/seed_demo_users.py   # 데모 계정 5종
backend/.venv/bin/python backend/scripts/seed_hug_workflow.py # 고정 S1~S7 HUG 업무 시나리오
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
cd backend && pytest -q    # Atlas 없이 mongomock으로 92건 전량 실행
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

- ~~공시가격 3종 미연동~~ → **260721 해소**: VWorld NED 3종 live 연동, 진단 시 자동 수집(best-effort). 공동주택은 동·호 미지정 시 단지 중앙값 사용을 `price_basis`에 명시
- **ML 학습데이터 한계** — 실제 정상 라벨이 없어 RTMS를 미라벨 U로 취급하고 260723 bagging PU PoC를 구현했습니다. 정상 오라벨링은 완화했지만 P=합성 사고군, U=비보증 포함 RTMS라 출처·모집단 시프트가 크며 현재 ROC/PR은 proxy 진단입니다. 원본 P 95,122건 중 공통 지역 support의 18,054건만 학습됐고, 세종에 집중된 전세가율 사고원천 69,435건은 U에 세종 표본이 없어 전량 제외됐습니다. 현재 artifact의 U는 2025.02~06 기존 첫 페이지 중심 표본이고, 보완된 전 페이지 수집기는 아직 재실행하지 않았습니다. 파일 간 공통 사건 ID 부재로 사건 단위 조인은 여전히 불가합니다.
- **HUG 업무 백엔드의 운영 전 정책** — 예방 sweep의 실제 스케줄러 배포, 심사·승인·지급 maker-checker 권한, 공식 SLA, 채권 원장 충당순서와 다중 컬렉션 outbox/reconciliation은 추후 확정이 필요합니다. 이번 구현의 SLA와 수동 원장 배분은 명시적 PoC 정책입니다.
- **블록체인 Mock Chain** — Polygon Amoy는 어댑터 인터페이스만 완성
- **RAG PII 사람 검수 미완** — 정규식 스캔 0건이나 자유서술 실명 가능성으로 보수적 처리 중
- ~~프론트 미연동 잔여분~~ → **260721 해소**: HUG 대시보드 5종 API·알림·전자계약 화면·회수 시뮬레이터(RecoveryPredictCard) 연동 완료

### 향후 계획

1. **Polygon Amoy 실연동** — 어댑터 교체만으로 전환 가능한 구조 완성됨 (`BLOCKCHAIN_MODE=polygon`)
2. **실제 운영데이터 확보 및 모델 재학습** — HUG 실데이터로 동일 파이프라인 재학습·검증 (재학습 전제 아키텍처)
3. ~~공시가격 3종 live 수집~~ ✅ 260721 완료 — 전세가율 신호 실계산 활성화
4. ~~프론트엔드 고도화~~ ✅ 260721 완료 — HUG 채권회수 대시보드 5종 API·전자계약·알림 화면·회수 시뮬레이터
5. **RAG 코퍼스 확장** — ✅ 완료(260721): 안심전세포털 97청크(누락 10페이지 보강) + 법령 124청크(주택임대차보호법·전세사기특별법). Atlas 적재·1024차원 임베딩·벡터검색 실동작까지 확인. PII 사람 검수는 계속 진행
6. **사고위험 PU 모델 운영 승격** — 세종을 포함한 지역 coverage 기준을 세우고 보완 수집기로 RTMS 대표 시군구 전 페이지 미라벨 표본을 재수집한 뒤 범위를 전국으로 확장합니다. 최종적으로 HUG의 계약키·사고여부·관찰종료일이 연결된 실제 코호트를 확보해 시간순/임대인·물건 그룹 외부검증, class prior 재추정, Platt/isotonic calibration 후 현재 PoC 서빙 artifact를 운영 모델로 교체합니다(9장 참조).

> 아래 **19장**은 심사·시연 피드백을 반영한 다음 개발 사이클의 기능 상세 로드맵입니다.

---

## 19. 향후 개발 로드맵 (기능 상세)

> 상태 범례: 🧩 데이터/기반 준비됨 · ⬜ 미착수 · 🔗 기존 기능 확장 · ✅ 완료

### 19.1 계약 후 관리 화면 — 3자(임차인·임대인·HUG) 공동 열람 ✅ (260722)

계약 **진행 중** 건과 계약 **후 관리** 건을 UI에서 분리하고, 계약 전반(계약 내용·변경사항·증빙 제출 이력)을 세 주체가 **동시 접속 없이도 동일하게** 확인할 수 있는 공유 화면.

- 계약 상태 축을 `진행중 / 관리중(계약 후)` 2탭으로 분리 — 현재 임차인 계약 상세에 흩어진 진단·타임라인·반환계획·증빙을 "계약 후 관리" 뷰로 재구성
- 동일 계약을 임차인/임대인/HUG가 각자 역할 화면에서 열어도 **같은 원본(계약 내용·변경 이력·증빙 상태)** 을 보도록 `contracts`·`contract_versions`·`timeline_events`를 공유 소스로 노출
- 변경사항은 타임라인 이벤트로 누적되어 누가 언제 무엇을 바꿨는지 3자가 추적 가능
- 기존 계약 상세 기능을 포함하되 관리 국면(반환 D-day, 증빙 현황, 특약 이행)을 전면 배치
- **구현(260722)**: 공용 라우트 `frontend/app/(common)/contracts/[contractId]/manage/` + 공유 뷰 `components/contracts/ContractManagementView.tsx`(D-day 히어로·증빙 현황·특약 이행 골격·변경 이력, 역할별 CTA 분기). 국면 분류는 `lib/contract-labels.ts`의 `contractPhase()`(계약 확정 이후 = 관리중). 진입점: 임차인 내 계약 2탭(`app/tenant/contracts/page.tsx`)·임차인 상세 배너·임대인 홈 "내 계약" 카드·HUG 사건 목록 행 클릭. 백엔드는 `contract_service._get_owned()`에 열람 역할(hug_admin·system_admin·advisor) 우회 추가 + return-plan·evidence-requests 라우트에 hug_admin 허용. 잔여: `contract_versions` 컬렉션·타임라인 행위자(actor) 기록은 미구현(특약 이행은 정적 골격).

### 19.2 임대인 보증금 상환능력 증빙 — 요청·업로드·3자 동시 확인 ✅ (260722) 🔗

임차인·HUG가 임대인의 **보증금 상환 능력**을 증빙으로 확인. 기존 증빙 요청·제출·검증 플로우(3장)를 상환능력 트랙으로 확장.

- 임차인 → 임대인 **추가 제출 요청** → 임대인 업로드 → **임차인·HUG 동시 확인** (검증 상태 공유)
- 상환능력 증빙 유형 신설: 소득·재직 증빙, 다른 보증금 반환 이력, 대환/여신 한도, 자산 증빙 등
- **D-90 사전 확보 강화**: 계약 만기 90일 전 기본 상환능력 서류 업로드를 요구하고, 미제출 시 임차인·임대인·HUG에 **단계별 노티**(D-90/D-60/D-30) 발송 — 기존 `notifications` 컬렉션 재사용
- 제출 파일은 현행대로 SHA-256 해시·블록체인 앵커로 무결성 보장
- **구현(260722, 백엔드 260723 보완)**: `EvidenceType` 4종과 관리 국면 상태 보호를 유지한다. 기존 `POST /contracts/dday-sweep`은 새 `PreventionService` 호환 wrapper가 됐고, HUG 전용 `POST /hug/contracts/prevention/sweep`을 추가했다. D-90/60/30마다 3개 필수 항목을 bundle로 추적하며 한 항목 제출을 전체 완료로 보지 않는다. 계약별 PU 예측·Rule 신호·기한초과를 예방 케이스로 묶고 임차인·임대인·HUG에 멱등 구조화 알림(info/warning/critical)을 보낸다. UI는 이번 260723 범위에서 수정하지 않았으며, 실제 일일 스케줄러와 이메일/푸시 채널은 남아 있다.

### 19.3 임대인 신뢰도 점수 (인센티브) ⬜

증빙을 제때 제출하거나 특약을 이행하는 등 **임차인 불안 해소·HUG 채권관리에 기여하는 행동**을 하면 신뢰도 점수가 상승하는 **당근마켓 매너온도식** 지표.

- 가점 이벤트: 증빙 기한 내 제출, 특약 이행, D-90 상환능력 서류 선제출, 반환계획 준수, 무사고 만기 등
- 감점 이벤트: 제출 지연, 요청 무응답, 사고 발생
- 점수는 임대인의 **다음 매물 계약·광고에 유리하게** 노출 (매물 카드 신뢰도 배지) → 자발적 성실 이행 유인
- 산정 로직·이벤트 소스는 `timeline_events`·`verifications`·`return_plans`에 이미 존재 → 집계 서비스 + 배지 컴포넌트 추가

### 19.4 RAG 청크의 화면 활용 — 법령 자동추천 · 지식맵 🧩

임베딩 완료된 **1,230청크(법령·안심전세포털 공식자료·FAQ)** 를 상담을 넘어 심사·계약 화면에서 능동 활용. 데이터·벡터검색은 준비 완료(10장), UI가 미착수.

- **관련 법령 자동 추천** — 심사·계약 화면의 현재 맥락(예: "근저당 설정")을 쿼리로 임베딩해 관련 조문을 **사이드 패널에 자동 표시**. 기존 `POST /rag/search`(law 필터) 재사용
- **지식 맵 / 토픽 클러스터** — 청크 임베딩을 2D(UMAP/t-SNE)로 투영해 "우리가 어떤 주제를 얼마나 커버하는지" 시각화 (커버리지·공백 진단, 발표용)
- 임차인 ↔ 아이엔(상담사) 상담 화면에 근거 카드로 노출

### 19.5 한반도 사고율 지도 — 코로플레스 시각화 ✅ (260722)

지역 데이터는 이미 처리 완료(5.2). 시군구 단위 사고율을 **코로플레스(choropleth)** 로 시각화.

| 데이터(processed/housta) | 행 | 용도 |
|---|---:|---|
| `housta_region_risk` | 273 | `adm_cd`·`accident_rate_pct` → **면 색칠(코로플레스)** |
| `housta_victim_locations` | 416 | 시군구별 피해주택 수 → **버블 오버레이** |
| `housta_issuance_region_monthly` | 6,907 | 시도×월×주택유형 발급 → 시계열 |

- **1순위 코로플레스** — 시군구 경계 GeoJSON(행정안전부/VWorld 무료)에 `adm_cd` 조인, `accident_rate_pct`로 색 농도. 면(폴리곤) 데이터라 점 히트맵보다 정확·오해 없음
- **2순위 버블** — `victim_locations` 시군구 중심좌표에 피해건수 비례 원 → 인천 미추홀구 등 다발지 강조
- 구현 스택(자체 완결, CSP 안전): `react-leaflet` + 시군구 GeoJSON **또는** `echarts-for-react` map (둘 다 설치형)
- 좌표 필요 시 VWorld 지오코딩 (메모리 기록대로 **domain 필수** 제약 감안)
- ⚠️ **주의**: `accident_rate_pct`는 3개월 평균이라 표본 적은 군 지역은 튈 수 있음 → **건수 하한(예: n<3 회색 처리)** 으로 오해 방지
- **구현(260722)**: HUG 사이드바 "사고율 지도" → `frontend/app/hug/map/page.tsx` — **echarts**(`echarts`+`echarts-for-react` 신규 설치, 외부 타일 불필요라 leaflet 대신 채택) 코로플레스 + 피해주택 scatter 버블 + 사고율 TOP10·피해주택 TOP5 카드. 경계는 `scripts/build_sigungu_geojson.py`가 **VWorld `LT_C_ADSIGG_INFO`**(기존 OFFICIAL_PRICE 키·domain 재사용)에서 수집→shapely 단순화(0.004도)→`frontend/public/geo/sigungu.json`(0.71MB, 256 features). ⚠️ **스파이크 발견사항**: VWorld 최신 경계는 **2026 행정개편 반영**(전남광주통합특별시 12xxx 신코드·인천 재편·화성 4구 분구) — housta 2025-08 구코드와 불일치 → 스크립트가 feature별 `src_cd`(구코드 조인 키)를 이름·수동 매핑으로 부여해 **251/252 조인**(유일 미표시: 인천 동구 — 제물포구 병합이라 1:1 대응 없음, 지도에서 회색+툴팁 사유 표기). n<3(143개 시군구)은 회색 — 실제로 사고 1건에 100% 사례 존재(고흥군). 피해주택 버블은 (sido_short, sigungu) 이름 매칭(특례시 "성남시 분당구" 형태 지원), 미매칭 16건은 각주 표기. 잔여: 시도 필터·연도 탭, 발급 시계열 연계.

### 19.6 HUG 화면 전문용어 → 결과 중심 라벨 리네이밍 ✅ (260722)

문제: 모델명(LightGBM)·기법명(SHAP)을 UI 라벨에 그대로 노출(`frontend/app/hug/dashboard/page.tsx:350`, `frontend/components/hug/RecoveryPredictCard.tsx:64`). 담당자는 "회수 가능한가·얼마나·왜"가 궁금하지 알고리즘 이름이 궁금한 게 아님. **로직은 그대로, 텍스트만 교체**.

| 현재 (기술 노출) | 제안 (업무 언어) |
|---|---|
| 선택 채권 · 요인 분석 (SHAP) | 이 채권, 왜 이 점수인가 — 판단 근거 Top 3 |
| 신규 채권 회수 예측 LightGBM + SHAP 실계산 | 회수 가능성 예측 — 예상 회수율·회수 소요일 자동 산정 |
| `priority_score` | 회수 우선순위 점수 (0~100) |
| `top_factors` / `shap` | 영향 요인 — "▲ 올림 / ▼ 내림" 아이콘 + 한 줄 설명 |

- **요인을 문장으로**: `{label} 값이 {value}라서 회수율을 {direction} 방향으로 {정도} 밀었습니다` 자동 문장화 (label·value·direction·shap 이미 반환됨 → 프론트 조립만)
- **발산형 막대 바**: 상위 3요인을 좌(내림 빨강)/우(올림 파랑)로 — 숫자보다 직관적
- 알고리즘 이름은 근거 툴팁 안으로 숨기고 전면에는 "얼마·언제·왜"만 (19.7과 직접 연결)
- 구현: `frontend/components/viz/FactorSentences.tsx`(받침 조사 자동 처리 포함) + `ShapBars.tsx` 발산형 개편, 라벨 교체는 `hug/dashboard/page.tsx`·`RecoveryPredictCard.tsx`

### 19.7 전문용어 툴팁 — 용어 사전 + 재사용 `<Term>` 컴포넌트 ✅ (260722)

전문용어에 마우스 호버 툴팁 / 물음표 아이콘 설명. "누구나 이해할 수 있게 설계했다"는 접근성 메시지. **19.6과 같은 용어 사전을 공유하므로 한 작업으로 처리 권장(반나절 규모).**

- **중앙 용어 사전** — `frontend/lib/glossary.ts` 단일 소스: `{ 용어키: { term, short(호버 1~2줄), long(클릭 상세), 역할대상 } }`. 예: 대위변제·근저당·확정일자·SHAP·LightGBM·앵커링·회수율·배당
- **`<Term>` 컴포넌트** — 점선 밑줄 + 데스크톱 호버·모바일 탭 팝오버. Radix UI Popover/Tooltip(shadcn 계열 이미 사용 → CSP·외부 의존성 문제 없음)
- **물음표 아이콘 변형** — 섹션 제목 옆 ⓘ/? → `long` 설명 팝오버 (HUG "요인 분석" 등)
- **접근성** — `aria-describedby`, 키보드 포커스로도 열림
- 구현: `frontend/lib/glossary.ts`(27개 용어 + 채권구분 매핑 + 자동매칭 표면형) + `components/common/Term.tsx`(`<Term>`·`<TermHelp>` ⓘ·`<GlossaryText>` 데이터 문자열 자동 래핑) + `components/ui/popover.tsx`(Base UI, `openOnHover`로 호버·탭 겸용)
- 적용 화면: HUG 대시보드(KPI·테이블·채권구분 값·예측 카드) / 임차인 계약 상세(위험 요인·권장 조치·AI 특약 — GlossaryText 자동) / 등기부 뷰어(근저당·압류 배지) / 아이엔 상담 현황(분쟁유형·단계·RAG 근거) / RAG 상담 패널(분류·함께 본 자료)
- 역할별 우선 용어: 임차인(대위변제·근저당·확정일자·전세보증·선순위) / 임대인(보증가입·사고·구상권) / 아이엔(분쟁 유형·상담 단계·RAG 근거) / HUG(회수율·회수 우선순위·SHAP 요인·배당·채권)

---

## 관련 문서

| 문서 | 위치 |
|---|---|
| API 계약 명세 (현행) | `docs/API_Contract_260721.yaml` |
| 구현현황·문서정합 보고서 | `docs/구현현황_문서정합_260721.md` |
| 정상 대조군 확보 초기안 (과거 case-control 제안) | `docs/정상대조군_확보방안_260721.md` |
| 사고위험 PU PoC 결과 (주 모델) | `개별수집데이터 및 API/processed/ml/ACCIDENT_MODEL_PU_POC_README.md` |
| 과거 case-control 결과 (비교 baseline) | `개별수집데이터 및 API/processed/ml/ACCIDENT_MODEL_POC_README.md` |
| 솔루션 기획안 (생애주기 루프) | `docs/솔루션_재정비_기획안_260718.md` |
| 백엔드 상세 README | `backend/README.md` |
| 데이터 사전 (발제사 데이터) | `dive 데이터/README.md` |
| 데이터 수집·API 가이드 | `docs/데이터수집_및_API가이드_260714.md` |
| ML 개발 가이드 | `docs/ML개발가이드_260714.md` |
| 블록체인 설계서 | `docs/Blockchain_설계서_260714.md` |
| MongoDB 사용 매뉴얼 | `docs/MongoDB_사용_매뉴얼_260714.md` |
