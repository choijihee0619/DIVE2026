# HUG 안심전세 체인 — Backend (FastAPI MVP)

`docs/API_Contract_260714.yaml`을 기준으로 시작해 HUG 사고 전 예방·보증이행·등록채권 관리까지 확장한 FastAPI 백엔드다. `/risk/diagnose`는 확인된 사실 기반 **rule-based 진단**, `/ml/accident/predict`는 별도의 미보정 PU PoC로 분리한다. 실제 구현 범위는 `docs/HUG_백엔드_구현현황_260723.md`를 함께 참고한다.

## 1. 요구사항

- Python **3.11+** (개발/검증은 **3.12.5**로 진행)
- MongoDB Atlas 접근 권한(`backend/.env`의 `MONGODB_URI`)
- (선택) OpenAI API 키 — 없으면 RAG 검색이 자동으로 키워드 fallback + `is_mock=true`로 동작

## 2. 가상환경 & 설치

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. 환경변수

`backend/.env`는 이미 존재하며 이번 작업에서 값을 바꾸거나 삭제하지 않았다. 누락되어 있던 항목은
`backend/.env.example`에만 추가했다(`BUILDING_REGISTRY_ENDPOINT`, `DEBUG`, `CORS_ALLOW_ORIGINS`,
`ATLAS_VECTOR_COLLECTION`, `ATLAS_VECTOR_PATH`, `BLOCKCHAIN_MODE`, `POLYGON_PRIVATE_KEY`,
`POLYGON_CHAIN_ID`, `INTERNAL_SERVICE_TOKEN`). `app/core/config.py`는 기존 키(`SECRET_KEY`,
`EMBEDDING_MODEL_NAME`, `EMBEDDING_DIMENSIONS`, `MONGODB_VECTOR_INDEX` 등)와 과제가 요구한 표준 키
이름(`JWT_SECRET_KEY`, `OPENAI_EMBEDDING_MODEL`, `ATLAS_VECTOR_INDEX_NAME` 등)을 `AliasChoices`로 함께
인식하므로 `.env`를 새로 고칠 필요는 없다.

## 4. 서버 실행

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Health: http://localhost:8000/health , http://localhost:8000/api/v1/health

> **이번 개발 세션의 네트워크 제약**: 이 세션이 실행된 샌드박스 환경에서는 MongoDB Atlas(포트 27017,
> TLS)로 나가는 아웃바운드 연결이 차단되어 있었다(같은 URI로 raw `openssl s_client` 테스트도 동일하게
> `SSL alert 80/internal_error`로 실패, 반면 HTTPS/443 트래픽은 정상). 따라서 이 세션에서는
> `uvicorn app.main:app`을 실제 Atlas에 붙여 기동하는 것을 끝까지 확인하지 못했다. 대신 아래 5번처럼
> `mongomock-motor`로 동일한 라우터/의존성 그래프를 pytest 92건으로 전량 검증했다. 사용자 로컬 환경은
> 이런 제약이 없을 가능성이 높고(`scripts/setup_mongodb.py`가 동일 URI로 이미 정상 접속·시드에
> 성공한 이력이 있음), 로컬에서 위 명령으로 재확인을 권장한다.

## 5. 테스트

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Atlas 없이도 전량 통과하도록 `mongomock-motor`로 MongoDB를 대체하고(`tests/conftest.py`),
FastAPI lifespan(Mongo 연결)을 건너뛰기 위해 `httpx.ASGITransport`를 직접 사용한다. 실행 결과(이 세션 기준):
`92 passed`.

## 6. Mock Mode 설명

| 데이터/기능 | 상태 | 비고 |
|---|---|---|
| 도로명주소, 건축물대장, 실거래가, 사업자등록상태, DART | live 연동 완료(데이터 수집 단계) | 이번 FastAPI MVP는 이 값들을 `registry_snapshots` 등 기존 컬렉션에서 **읽기만** 하며, 새 외부 API 호출 코드는 이번 범위에 없음 |
| CODEF 등기부 | 100% mock | `mortgage_ratio`/`rights_burden_ratio`/`has_seizure`는 `source_status.registry == "live"`일 때만 계산 — 지금은 항상 `missing` 또는 `mock`으로 표시되고 실제 값으로 계산되지 않음 |
| 공시가격 3종 | mock | `jeonse_ratio`도 동일 원칙으로 `official_price_status == "live"`일 때만 계산 |
| 온비드 | 배제 확정(260721) | 서비스 도메인에서 완전 제외 |
| RAG 검색 | 실제 Atlas Vector Search 코드 구현됨 | `OPENAI_API_KEY`가 없거나 OpenAI 호출이 실패하면 키워드 fallback 검색으로 전환하고 `is_mock=true` 반환(뒤에서 500으로 끝나지 않고 `ERROR-009`로 명확히 반환) |
| 블록체인 | `BLOCKCHAIN_MODE=mock`(기본값) | 외부 RPC 호출 없이 `MockBlockchainAdapter`가 `0x`+64hex tx_hash를 즉시 `Confirmed`로 발급. `BLOCKCHAIN_MODE=polygon`으로 바꾸면 `PolygonBlockchainAdapter`가 스켈레톤 오류를 반환한다(추후 구현 예정, private key는 코드에 두지 않음) |

## 7. HUG 업무 백엔드 확장 (2026-07-23)

이번 확장은 프론트엔드를 수정하지 않고 다음 업무 API와 저장 원장을 추가했다.

| 영역 | 구현 내용 |
|---|---|
| 통합 대시보드 | `/hug/dashboard/overview`, `/hug/dashboard/issuance-incident-trend`; LIVE·DEMO 업무대장과 합성 참조·공공 집계 분리 |
| 사고 전 계약 | `/hug/contracts`; PU PoC 단건·일괄 추론, 성공/범위밖/실패 이력, 50/20/15/15 예방 우선순위 |
| 사전예방 | D-90/60/30 각 3개 필수 증빙, prevention case/action, 멱등 sweep, 임차인·임대인·HUG 구조화 알림 |
| 보증이행 | 사고통지와 별도 performance claim, 서류·심사·명도·대위변제·채권등록·인계 액션과 감사 이벤트 |
| 채권관리 | `/hug/recovery`; LIVE/DEMO 분리 KPI, 병렬 상태축, append-only 원장, 등록채권 기반 회수전망 이력, 종결 후 읽기 전용 |
| 시연 | `hug-workflow-v1.1.0`; 고정 기준일·ID의 S1~S7 및 증빙·심사·지급·알림 하위원장 upsert, manifest·digest·모델 hash |

주요 컬렉션은 `accident_predictions`, `prevention_cases`, `preventive_actions`, `evidence_bundles`, `performance_claims`, `claim_documents`, `performance_claim_events`, `subrogation_payments`, `recovery_claims`, `recovery_events`, `recovery_ledger`, `recovery_predictions`, `demo_seed_manifests`다. 신규 응답과 저장 객체는 `data_mode`, `source_type`, `source_dataset`, `as_of_date`, `scenario_id`, `model_version`, `input_snapshot`, `is_demo`, `basis` 출처 구조를 사용한다.

보안·무결성 보완으로 공개 회원가입의 관리자 역할 생성을 차단했고, 증빙 계약 소유권 검증, HUG 업무 RBAC, 상태·버전 CAS, idempotency key와 고유 인덱스를 적용했다. 상세 API·상태전이·운영 전 제한은 [`../docs/HUG_백엔드_구현현황_260723.md`](../docs/HUG_백엔드_구현현황_260723.md)에 정리했다.

## 8. rule-based 위험진단 원칙 (`POST /api/v1/risk/diagnose`)

- 등급은 **A/B/C가 아니라 API_Contract의 `RiskGrade` enum(`LOW`/`MEDIUM`/`HIGH`)**을 그대로 사용한다
  (모든 선행 문서가 LOW/MEDIUM/HIGH만 정의하며 A/B/C 표기는 어디에도 없음 — 충돌사항 1번).
- `jeonse_ratio`/`mortgage_ratio`/`rights_burden_ratio`/`has_seizure`는 등기부·공시가격 출처가
  `api_live`일 때만 계산한다. 지금처럼 두 출처가 모두 mock/미확보 상태면 **`missing_fields`에
  넣을 뿐 "위험 낮음"으로 채점하지 않는다.**
- `data_completeness < 0.4`이면 원점수가 낮아도 `risk_grade`를 `LOW`로 내리지 않고 최소 `MEDIUM`으로
  올린다(데이터 부족 ≠ 안전).
- 응답에는 `risk_score`, `risk_grade`, `assessment_mode="rule_based_fallback"`, `confidence`,
  `data_completeness`, `risk_factors`, `positive_factors`, `missing_fields`, `required_documents`,
  `recommended_actions`, `source_status`가 항상 포함된다.

## 9. API_Contract와의 의도적인 차이(반드시 확인 필요한 항목)

과제 지시사항(4절 "위험진단 API")과 `API_Contract_260714.yaml`이 서로 다른 형태를 요구해 아래처럼
절충했다. 프론트 연동 전 팀 확인이 필요하다.

1. **`POST /risk/diagnose`가 202(비동기 폴링) 대신 200 즉시 응답이다.** rule-based fallback은
   외부 API 오케스트레이션 없이 동기 계산만 하므로 폴링이 필요 없다고 판단했다. `GET /risk/{case_id}`는
   계약대로 유지했고 동일한 저장 결과를 반환한다.
2. **위험등급은 LOW/MEDIUM/HIGH.** 과제 예시의 A/B/C는 어느 선행 문서에도 없어 계약 enum을 따랐다.
3. **`GET/POST /verifications/{id}`의 `{id}`가 `verification_id`가 아니라 `evidence_id`다.**
   Evidence-Verification이 1:1이고 결정 전에는 verification 레코드 자체가 없어 evidence_id로 조회하게
   했다.
4. **`POST /auth/signup`은 계약에 없는 신규 엔드포인트다.** 과제 지시사항 D절이 "회원가입"을 최소
   기능으로 명시했고 계약에는 사용자 생성 경로가 없어 추가했다.
5. **`POST /blockchain/anchor`를 advisor/hug_admin/system_admin이 직접 호출할 수 있게 열었다.**
   계약상 "Backend 내부 서비스 전용"이지만 Node.js Anchor 서비스가 아직 없어 시연을 위해 열어두었다.

## 10. 디렉터리 구조

```text
backend/app/
├── main.py                 # FastAPI 앱, lifespan, 미들웨어, 예외 핸들러
├── core/                    # config, security(JWT/bcrypt), exceptions, responses, logging
├── db/                      # mongodb.py(Motor), indexes.py
├── models/                  # enums.py, collections.py(Document 형태 TypedDict)
├── schemas/                 # Pydantic Request/Response DTO
├── repositories/            # Motor 컬렉션 CRUD 캡슐화
├── services/                # 유즈케이스, risk_engine.py(rule engine), blockchain/(adapter)
├── api/v1/endpoints/        # Router (Contract Tag 1:1)
├── middleware/              # Request-ID/Trace-ID
└── utils/                   # pii_masking.py, hashing.py, datetime_utils.py
```

Beanie 대신 **Motor를 직접 사용**했다(Backend_API_명세서는 Beanie를 권장하지만, 해커톤 일정상
Repository 패턴만으로도 계층 분리 요구사항을 충분히 만족하고 mongomock 테스트도 더 단순해서 선택한
구현 세부사항 변경이다. 계약/데이터모델과는 무관).

## 11. 시드 스크립트

```bash
python scripts/seed_demo_users.py
python scripts/seed_hug_workflow.py
# 오프라인 시연에서 저장 모델 대신 명시적 캐시 결과 사용
python scripts/seed_hug_workflow.py --cached-predictions
```

`tenant01/landlord01/advisor01/hugadmin01/sysadmin01@example.com`, 공통 비밀번호 `P@ssw0rd!` 계정을
idempotent하게 생성한다(이미 있으면 건너뜀).

두 번째 스크립트는 template `hug-workflow-v1.1.0`, `demo-ct-*`, `demo-inc-*`, `demo-perf-*`, `demo-rc-*` 고정 ID와 기준일 `2026-07-23`로 S1~S7 업무흐름을 upsert한다. 계약·예측뿐 아니라 증빙 요청/제출/검증, 이행청구 서류, 대위변제, 감사 이벤트, 회수 원장, 3자 예방알림도 함께 생성한다. API에서는 `MOCK_MODE=true`일 때 `POST /api/v1/hug/demo/seed`, `GET /api/v1/hug/demo/manifest`를 사용할 수 있다.

Seed 후 연결 조회용 계정은 `workflow.tenant@example.com`, `workflow.landlord@example.com`, `workflow.hug@example.com`이며 공통 비밀번호는 `P@ssw0rd!`다. 이 계정은 실제 운영 계정이 아닌 MOCK 시연 전용이다.

## 12. 남은 문제

- CODEF 등기부 실조회는 live 전환 완료, 공시가격 3종(VWorld)은 live 연동 진행, 온비드는 배제 확정(260721).
- `processed_risk_features_v1.parquet` 없음 → 정식 ML 모델 학습/검증 금지 상태 유지.
- 사고위험 PU PoC는 8개 시도와 현재 artifact 학습 범위만 지원하며 실제 HUG 정상 종료·사고 코호트의 외부검증·확률보정 전에는 운영 확률이 아니다.
- 예방 sweep의 실제 스케줄러 배포, 이행서류 object storage 통합, HUG 공식 SLA, maker-checker 권한, 채권원장 충당순서와 outbox/reconciliation은 운영 전 확정이 필요하다.
- Polygon Amoy 실연동, Node.js Anchor 서비스 — 스켈레톤만 존재.
- RAG `pii_removed`가 데이터 전체적으로 여전히 `false`(사람 표본검수 전) — API는 `metadata.pii_removed`
  값을 있는 그대로 노출하고 별도로 원문을 항상 마스킹/절단해서 반환한다.
