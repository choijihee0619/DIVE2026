# HUG × 아이엔 안심주거 생태계

## Frontend UI/UX 명세서

작성일: 2026-07-14 (KST)
문서 버전: v1.0.0
작성자 관점: Senior Frontend Architect

> **⚠️ [260721 갱신 공지]** 비주얼 기준은 `안심루프_UI시안_260718.html` + 260721 목업(HUG 블루·그린, Pretendard,
> 전 역할 사이드바 셸)으로 대체되었고 프론트 전면 리디자인이 반영됐다. 화면 ID(TEN/LAND/ADV/HUG/ADM)와 Route 구조는
> 현행 코드와 일치하므로 유효. API 경로 표기는 `API_Contract_260721.yaml` 기준으로 읽을 것.
> 화면·엔드포인트 연동 현황(21/61 연동, 미연동 우선순위)은 `구현현황_문서정합_260721.md` 3장 참조.

> 본 문서는 `개발설계보고서_260714_수정보완.docx`를 상위 문서로 하며, 충돌 시 개발설계보고서를 우선한다. 외부 API 인증·호출 상세는 `데이터수집_및_API가이드_260714.md`, ML 모델 입출력은 `ML개발가이드_260714.md`를 따른다. 내부 REST API의 정확한 Path·DTO·오류코드·ERD는 아직 작성되지 않은 `Backend_API_명세서_260714.md`에서 확정되며, 본 문서의 API 호출 표기는 위 세 문서에서 확인 가능한 범위(개발설계보고서 10.1 공통 식별자, 데이터수집가이드 부록 A 최소 엔드포인트, ML개발가이드 20장 모델 계약)로 한정하고 나머지는 `확정 필요`로 표시한다. 본 문서는 디자인 시안이 아니라 React 개발자가 화면을 바로 구현할 수 있도록 하는 개발 명세이며, CSS·React 코드·Figma·이미지는 포함하지 않는다.

---

## 목차

0. 문서 개요
1. IA (서비스 구조 / Sitemap)
2. Route
3. 사용자와 권한별 접근 화면
4. User Flow
5. 화면 목록
6. Wireframe
7. Component Library
8. API Mapping
9. 상태 정의
10. UX 원칙
11. Responsive
12. Accessibility
13. 상태관리 (React Query / Zustand)
14. 폴더 구조
15. 개발 순서
16. TODO
17. Definition of Done
18. 제외사항

---

# 0. 문서 개요

## 0.1 목적

이 문서는 HUG 안심전세 체인의 Frontend를 Next.js(App Router) + TypeScript로 구현하는 개발자가 별도 설계 회의 없이 화면을 만들 수 있도록, IA·Route·User Flow·화면별 명세·Wireframe·Component·API 매핑·상태 정의·상태관리·폴더 구조·개발 순서를 확정한 개발 기준 문서다. 디자인 시안이 아니라 구현 계약이며, 개발설계보고서가 정의한 공통 식별자(user_id, contract_id, risk_assessment_id 등)와 공통 상태(ContractStatus, VerificationStatus, BlockchainStatus, APIResultStatus, ModelResultStatus)를 화면 단위로 재정리한다.

## 0.2 프로젝트 한 줄 요약

HUG 안심전세 체인은 위험을 점수화하는 앱이 아니라, 계약 전 위험을 발견하고 위험조건이 실제로 해소됐는지 증빙과 외부 API로 검증하며, 계약서·검증 이력을 블록체인에 공증하고, 계약 만료 전 D-90 반환계획 확인과 사고 후 HUG 채권관리 인계까지 하나의 생애주기로 연결하는 주거안전 인프라다.

## 0.3 Frontend 관점 핵심 설계 포인트

프론트엔드가 반드시 반영해야 할 4가지 원칙은 다음과 같다.

첫째, 위험진단 결과 화면은 등급(숫자·색상)만 강조하지 않고 근거(risk_reasons)와 다음 행동(증빙 요청, 전문가 이관 등)을 항상 함께 보여준다. 둘째, 해결 가능한 위험(근저당 말소 예정 등)과 해결 불가능한 위험(구조적 위험)을 시각적으로 분리한다. 셋째, 모든 조회 결과 카드에는 조회시각, 데이터 출처(API/Mock/사용자업로드), 모델 버전, 블록체인 상태를 표시한다. 넷째, 외부 API·ML 모델이 실패해도 재시도, 업로드 대체, Mock 전환 경로를 사용자에게 숨기지 않고 명시적으로 보여준다. 블록체인 상태는 항상 Pending/Confirmed/Failed 3단계로만 표시하고 법적 효력이 있는 것처럼 과장하지 않는다.

## 0.4 Frontend Stack

| 영역 | 선택 | 비고 |
|---|---|---|
| 프레임워크 | Next.js (App Router) | Vercel 배포 전제(개발설계보고서 9.9절) |
| 언어 | TypeScript | strict mode |
| 스타일 | TailwindCSS | 유틸리티 클래스만 사용, 커스텀 CSS 최소화 |
| UI 컴포넌트 | shadcn/ui | Radix 기반, 접근성 기본 내장 |
| 서버 상태 | React Query (TanStack Query) | API 호출, 캐싱, 재시도 |
| 클라이언트 상태 | Zustand | 세션, 위저드 단계, UI 전역 상태 |
| 폼 | React Hook Form + Zod | 입력 검증, 스키마 공유 |
| 아이콘 | Lucide Icons | |
| 모션 | Framer Motion | 단계 전환, 상태 배지 애니메이션 |
| 차트 | Recharts | HUG 대시보드, 회수등급/처리기간 분포 |

## 0.5 소스 문서 요약 (Frontend 관점 재정리)

개발설계보고서는 6개 사용자군(임차인, 임대인, 아이엔, HUG, 시스템 관리자, 외부 API·검증기관)과 8단계 생애주기(계약 전 → 위험조건 보완 → 검증 및 계약 확정 → 계약 중 모니터링 → D-90 반환계획 → 사고 발생 → HUG 채권관리 → 계약 종료)를 정의한다. 데이터수집가이드는 CODEF·도로명주소·실거래가·건축물대장 등 외부 API의 성공/실패/Mock 전환 흐름과 11종 Mock JSON을 정의한다. ML개발가이드는 상담 분류, 회수등급, 처리기간 3개 모델의 입출력 JSON과 `is_mock`, `ModelResultStatus` 필드를 정의한다. 본 문서는 이 세 문서를 화면·컴포넌트·상태 단위로 번역한다.

---

# 1. IA (서비스 구조 / Sitemap)

## 1.1 서비스 구조

```
HUG 안심전세 체인 (Frontend)
├── 공통 영역
│   ├── 로그인/역할 선택
│   ├── 알림 센터
│   ├── 권한 오류
│   └── 블록체인 이력 조회
│
├── 임차인(tenant) 영역
│   ├── 홈 (진행 계약, 위험등급, 알림)
│   ├── 계약 전 위험진단
│   │   ├── 주소·계약정보 입력
│   │   ├── 외부 API 조회 진행
│   │   └── 위험진단 결과
│   ├── 증빙·검증 진행 확인
│   ├── 계약 타임라인
│   ├── D-90 반환계획
│   └── 사고 접수
│
├── 임대인(landlord) 영역
│   ├── 홈 (보완요청 알림)
│   ├── 증빙 요청 확인·제출
│   ├── 검증 상태 확인
│   └── 반환계획 제출
│
├── 아이엔(advisor) 영역
│   ├── 상담 현황 (RAG 근거 포함)
│   ├── 증빙 검토
│   └── 전문가 이관 처리
│
├── HUG(hug_admin) 영역
│   ├── 채권관리 대시보드
│   ├── 사건 상세
│   ├── 유사사건 비교
│   └── 법인 집단위험
│
└── 관리자(system_admin) 영역
    ├── 사용자·권한 관리
    ├── 외부 API/모델 상태 모니터링
    ├── 블록체인 로그
    └── 시스템 로그
```

## 1.2 Sitemap 표

| 레벨1 | 레벨2 | 레벨3 | 대응 사용자 |
|---|---|---|---|
| 공통 | 로그인 | - | 전체 |
| 공통 | 알림 센터 | - | 전체 |
| 공통 | 권한 오류(403) | - | 전체 |
| 공통 | 블록체인 이력 | 트랜잭션 상세 | 전체(읽기 권한별 차등) |
| 임차인 | 홈 | - | tenant |
| 임차인 | 위험진단 | 주소입력 / API조회 / 결과 | tenant |
| 임차인 | 증빙·검증 | 요청 목록 / 상세 | tenant |
| 임차인 | 계약 타임라인 | 이벤트 상세 | tenant |
| 임차인 | D-90 | 반환계획 작성 | tenant |
| 임차인 | 사고 접수 | 접수 폼 / 접수 완료 | tenant |
| 임대인 | 홈 | - | landlord |
| 임대인 | 증빙 제출 | 업로드 | landlord |
| 임대인 | 검증 상태 | - | landlord |
| 임대인 | 반환계획 제출 | - | landlord |
| 아이엔 | 상담 현황 | 상담 상세 | advisor |
| 아이엔 | 증빙 검토 | - | advisor |
| 아이엔 | 전문가 이관 | - | advisor |
| HUG | 대시보드 | - | hug_admin |
| HUG | 사건 상세 | 유사사건 비교 | hug_admin |
| HUG | 법인 집단위험 | - | hug_admin |
| 관리자 | 사용자·권한 | - | system_admin |
| 관리자 | API/모델 상태 | - | system_admin |
| 관리자 | 블록체인 로그 | - | system_admin |

---

# 2. Route

App Router 기준 경로다. `[id]`는 동적 세그먼트, 괄호는 라우트 그룹을 의미한다.

## 2.1 공통

| Route | 화면 |
|---|---|
| `/login` | 로그인/역할 선택 |
| `/unauthorized` | 권한 오류(403) |
| `/notifications` | 알림 센터 |
| `/blockchain/[txId]` | 블록체인 트랜잭션 상세 |

## 2.2 임차인 (`/tenant/**`)

| Route | 화면 ID | 화면 |
|---|---|---|
| `/tenant` | TEN-00 | 임차인 홈 |
| `/tenant/check` | TEN-01 | 주소·계약정보 입력 |
| `/tenant/check/progress` | TEN-02 | 외부 API 조회 진행 |
| `/tenant/result/[caseId]` | TEN-03 | 위험진단 결과 |
| `/tenant/evidence/[caseId]` | TEN-04 | 증빙·검증 진행 |
| `/tenant/timeline/[contractId]` | TEN-05 | 계약 타임라인 |
| `/tenant/d90/[contractId]` | TEN-06 | D-90 반환계획 |
| `/tenant/incident/new` | TEN-07 | 사고 접수 |

## 2.3 임대인 (`/landlord/**`)

| Route | 화면 ID | 화면 |
|---|---|---|
| `/landlord` | LAND-00 | 임대인 홈 |
| `/landlord/evidence/[requestId]` | LAND-01 | 증빙 요청 확인·제출 |
| `/landlord/verification/[verificationId]` | LAND-02 | 검증 상태 확인 |
| `/landlord/return-plan/[contractId]` | LAND-03 | 반환계획 제출 |

## 2.4 아이엔 (`/advisor/**`)

| Route | 화면 ID | 화면 |
|---|---|---|
| `/advisor` | ADV-00 | 상담 현황 |
| `/advisor/counsel/[counselId]` | ADV-01 | 상담 상세·RAG 근거 |
| `/advisor/verification/[verificationId]` | ADV-02 | 증빙 검토 |
| `/advisor/referral/[caseId]` | ADV-03 | 전문가 이관 |

## 2.5 HUG (`/hug/**`)

| Route | 화면 ID | 화면 |
|---|---|---|
| `/hug/dashboard` | HUG-01 | 채권관리 대시보드 |
| `/hug/case/[incidentId]` | HUG-02 | 사건 상세 |
| `/hug/case/[incidentId]/similar` | HUG-03 | 유사사건 비교 |
| `/hug/entity/[entityId]` | HUG-04 | 법인 집단위험 |

## 2.6 관리자 (`/admin/**`)

| Route | 화면 ID | 화면 |
|---|---|---|
| `/admin` | ADM-00 | 사용자·권한 관리 |
| `/admin/api-status` | ADM-01 | 외부 API/모델 상태 |
| `/admin/blockchain` | ADM-02 | 블록체인 로그 |
| `/admin/logs` | ADM-03 | 시스템 로그 |

Route 총 개수는 공통 4 + 임차인 8 + 임대인 4 + 아이엔 4 + HUG 4 + 관리자 4 = **28개**이며(로그인/알림/권한오류/블록체인상세 포함), 화면 ID 기준 화면 개수는 24개다(공통 3개 화면은 별도 ID 없이 AUTH/COMMON prefix로 5장에서 관리).

---

# 3. 사용자와 권한별 접근 화면

개발설계보고서 13.5절의 역할(tenant, landlord, advisor, hug_admin, system_admin, verifier)을 Frontend 라우트 가드 기준으로 재정리한다. `verifier`는 아이엔 내부 검증 담당자와 동일 화면(advisor 그룹)을 사용하되 증빙 검토 액션 권한만 별도 스코프로 분리한다(Backend_API_명세서 확정 필요).

| 역할 | 역할 설명 | 접근 가능 Route 그룹 | 접근 불가 시 |
|---|---|---|---|
| tenant | 임차인 | `/tenant/**`, `/notifications`, `/blockchain/[txId]`(본인 계약만) | `/unauthorized` |
| landlord | 임대인 | `/landlord/**`, `/notifications`, `/blockchain/[txId]`(본인 계약만) | `/unauthorized` |
| advisor | 아이엔 상담·검증 담당자 | `/advisor/**`, `/notifications` | `/unauthorized` |
| hug_admin | HUG 채권관리 담당자 | `/hug/**`, `/notifications` | `/unauthorized` |
| system_admin | 시스템 관리자 | `/admin/**`, 전체 읽기 전용 접근 | `/unauthorized` |
| verifier | 검증 세부 권한(advisor 내 서브 역할) | `/advisor/verification/**` 액션 권한 | 조회만 허용, 액션 버튼 비활성화 |

권한 판정은 Next.js Middleware 또는 `RoleGuard` 컴포넌트(7장)에서 세션의 `role` 클레임을 기준으로 처리하며, 서버 컴포넌트 진입 전 1차 차단, 클라이언트 액션(버튼) 진입 전 2차 차단의 이중 가드를 적용한다. 인증·세션 발급 방식(JWT/OAuth 등)의 상세는 Backend_API_명세서_260714.md에서 확정한다.

---

# 4. User Flow

개발설계보고서 11장(상위 User Flow, 표 23)을 화면 ID 단위로 구체화한다. User Flow는 총 6개다.

## 4.1 임차인 Flow

```
[로그인/역할확인]
   ↓
TEN-00 홈 (진행 계약 확인)
   ↓
TEN-01 주소·계약정보 입력 (address/normalize 호출)
   ↓
TEN-02 외부 API 조회 진행 (CODEF·실거래가·건축물대장, 실패 시 재시도/업로드/Mock)
   ↓
TEN-03 위험진단 결과 (규칙엔진 + ML 위험유사도 + SHAP 근거 + RAG)
   ↓
TEN-04 증빙·검증 진행 확인 (해결 가능 위험에 대한 보완요청 상태 확인)
   ↓
(계약 확정, 블록체인 공증 — 임대인/아이엔 처리 후 자동 반영)
   ↓
TEN-05 계약 타임라인 (Monitoring 상태, 상태변경 이력)
   ↓
TEN-06 D-90 반환계획 확인 (계약 만료 90일 전 알림 수신 후)
   ↓
[정상 종료] Closed 상태로 타임라인 갱신
   ↓ (미반환 의심 시)
TEN-07 사고 접수 → HUG 채권관리 인계
```

## 4.2 임대인 Flow

```
[알림 수신: 보완요청]
   ↓
LAND-00 홈 (보완요청 목록)
   ↓
LAND-01 증빙 요청 확인·제출 (파일 업로드, document_hash 생성)
   ↓
LAND-02 검증 상태 확인 (Pending → Reviewing → Verified/Rejected)
   ↓
(계약 만료 D-90 도달 시)
   ↓
LAND-03 반환계획 제출
```

## 4.3 아이엔 Flow

```
ADV-00 상담 현황 (신규 상담/이관 대상 정렬)
   ↓
ADV-01 상담 상세 및 RAG 근거 확인 (상담 분류 모델 결과 + 유사 상담사례)
   ↓
ADV-02 증빙 검토 (임대인 제출 증빙과 외부 API 조회 결과 대조)
   ↓
ADV-03 전문가 이관 (고위험 사건 처리, expert_referral=true 케이스)
```

## 4.4 HUG Flow

```
HUG-01 대시보드 (조기경보, 회수등급, 처리기간 우선순위 정렬)
   ↓
HUG-02 사건 상세 (사고 이력, 회수예측, 처리기간 예측)
   ↓
HUG-03 유사사건 비교 (동일 지역/주택유형 그룹)
   ↓
[담당자 액션 기록]
   ↓
[종결] Closed 상태로 반영
```

## 4.5 외부 API 실패 Flow (모든 사용자 화면에 공통 적용)

```
자동 조회 시작
   ↓
실패?
   ├─ 아니오 → 정규화 결과 표시 (APIResultStatus=Success)
   └─ 예 → 재시도(최대 2회)
            ↓
          성공?
            ├─ 예 → 정규화 결과 표시 (APIResultStatus=Success)
            └─ 아니오 → 캐시 확인
                         ↓
                       캐시 있음?
                         ├─ 예 → 캐시 결과 표시 (APIResultStatus=Partial)
                         └─ 아니오 → 업로드 대체 또는 Mock 전환 안내
                                      ↓
                                    사용자 확인
                                      ↓
                                    결과 표시 (APIResultStatus=MockFallback)
```

## 4.6 사고 후 HUG 인계 Flow

```
TEN-07 사고 접수 (ContractStatus: AtRisk → IncidentReported)
   ↓
Backend 자동 인계 처리 (ContractStatus: TransferredToHUG)
   ↓
HUG-02 사건 상세에 신규 사건으로 노출
   ↓
회수등급·처리기간 모델 추론 (recovery_prediction_id 생성)
   ↓
ContractStatus: RecoveryInProgress
   ↓
[HUG 담당자 처리 완료] ContractStatus: Closed
```

---

# 5. 화면 목록

화면마다 화면명, 목적, Route, 접근권한, 호출 API, 입력, 출력, 버튼, 다음 화면, 오류 처리, Loading, Empty, 권한 없음, Mock 지원 여부를 정의한다. API 경로 중 `데이터수집가이드 부록 A` 또는 `ML개발가이드 20장`에서 확인되지 않는 경로는 `[확정 필요]`로 표시하며 Backend_API_명세서_260714.md 작성 시 갱신한다.

## 5.1 TEN-01 주소·계약정보 입력

- 목적: 위험진단의 기준이 되는 물건 주소와 계약 조건(보증금, 계약기간, 임대인 유형)을 수집한다.
- Route: `/tenant/check`
- 접근권한: tenant
- 호출 API: `POST /api/v1/address/normalize`(데이터수집가이드 부록 A), `POST /api/v1/contract`[확정 필요]
- 입력: 주소 검색어, 주소 후보 선택, 보증금, 계약 시작일/종료일, 임대인 유형(개인/법인), 주택유형
- 출력: 표준 도로명주소, 지번주소, 법정동코드, 건물관리번호, 입력 요약 카드
- 버튼: 주소 검색, 후보 선택, 다음(진단 시작), 임시저장
- 다음 화면: TEN-02
- 오류 처리: 주소 미검색 시 인라인 오류, 필수값 미입력 시 Zod 검증 메시지, 주소 API 실패 시 수동 입력 폼으로 전환
- Loading: 주소 검색 중 Skeleton 리스트(5행)
- Empty: 검색 결과 없음 안내 + 수동 입력 유도
- 권한 없음: landlord/advisor/hug_admin 접근 시 `/unauthorized` 리다이렉트
- Mock 지원: 예 (`mock_address.json`)

## 5.2 TEN-02 외부 API 조회 진행

- 목적: CODEF 등기부, 실거래가, 건축물대장, 사업자등록 상태 등 외부 API 조회 진행 상태를 단계별로 표시한다.
- Route: `/tenant/check/progress`
- 접근권한: tenant
- 호출 API: `POST /api/v1/risk/diagnose`(내부적으로 CODEF/실거래가/건축물대장/사업자상태 조회 오케스트레이션, 데이터수집가이드 4장 연동 순서 기준)
- 입력: 없음(TEN-01에서 전달된 property_id, contract 임시값)
- 출력: API별 진행 상태 리스트(대기/조회중/성공/실패/Mock전환), 전체 진행률
- 버튼: 재시도(개별 API), 업로드로 대체, 계속 진행(일부 실패 허용 시)
- 다음 화면: TEN-03 (모든 API가 Success/Partial/MockFallback 중 하나로 종료되면 자동 이동)
- 오류 처리: 개별 API 실패 시 4.5절 Fallback Flow 적용, 인증 실패는 관리자 문의 안내
- Loading: 단계별 Progress bar + 스피너, 예상 소요시간 텍스트
- Empty: 해당 없음(항상 최소 1개 API 진행)
- 권한 없음: `/unauthorized`
- Mock 지원: 예 (등기부 3종, 공시가격, 실거래가 없음, 사업자 폐업 등 데이터수집가이드 6.1절 11종 Mock 전체 대응)

## 5.3 TEN-03 위험진단 결과

- 목적: 규칙 엔진 + ML 위험유사도 + SHAP 근거 + RAG 검색 결과를 결합한 최종 위험진단을 표시하고 다음 행동을 제시한다.
- Route: `/tenant/result/[caseId]`
- 접근권한: tenant
- 호출 API: `GET /api/v1/risk/{case_id}`(데이터수집가이드 부록 A), `POST /api/v1/rag/search`(데이터수집가이드 부록 A)
- 입력: 없음(caseId path parameter)
- 출력: 위험등급(HIGH/MEDIUM/LOW), 위험요소 리스트(해결가능/해결불가 구분), risk_reasons, SHAP 자연어 요약(2~3개 요인), 유사 상담사례 카드, 데이터 출처·조회시각·model_version, ModelResultStatus 배지
- 버튼: 증빙 요청 확인하기(TEN-04 이동), 상담 요청, 결과 공유, 재진단
- 다음 화면: TEN-04
- 오류 처리: `ModelResultStatus=RuleOnlyFallback` 시 "모델 추론 실패, 규칙 기반 결과만 제공" 배너 표시, `Failed` 시 재진단 유도
- Loading: 결과 카드 Skeleton(위험등급 배지, 근거 리스트, 유사사례 리스트 각각)
- Empty: RAG 근거 없음 시 "관련 상담사례를 찾지 못했습니다" 안내(부록 F 준수, 근거 없이 결론만 제시하지 않음)
- 권한 없음: 본인 소유 caseId가 아니면 `/unauthorized`
- Mock 지원: 예 (`is_mock: true/false` 필드로 UI 배지 전환)

## 5.4 TEN-04 증빙·검증 진행

- 목적: 규칙 엔진이 해결 가능으로 판단한 위험요소에 대해 보완요청/증빙제출/검증 상태를 확인한다.
- Route: `/tenant/evidence/[caseId]`
- 접근권한: tenant
- 호출 API: `GET /api/v1/evidence-requests`[확정 필요], `GET /api/v1/verifications`[확정 필요]
- 입력: 없음(조회 전용, 제출은 임대인 화면 LAND-01에서 수행)
- 출력: 보완요청 리스트(사유, 대상 위험요소), VerificationStatus 칩, 제출 증빙 미리보기(파일명, 제출일)
- 버튼: 새로고침, 임대인에게 알림 재발송 요청
- 다음 화면: TEN-05 (검증 완료 시 자동 안내)
- 오류 처리: 검증 Rejected 시 사유와 재제출 안내, Expired 시 재요청 버튼
- Loading: 리스트 Skeleton
- Empty: 보완요청 없음(위험 없음 또는 이미 완료) 시 "보완이 필요한 항목이 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.5 TEN-05 계약 타임라인

- 목적: 계약 생애주기 상태 변경 이벤트와 블록체인 기록 상태를 시간순으로 표시한다.
- Route: `/tenant/timeline/[contractId]`
- 접근권한: tenant
- 호출 API: `GET /api/v1/contracts/{contract_id}/timeline`[확정 필요], `GET /api/v1/blockchain/{tx_id}`[확정 필요]
- 입력: 없음
- 출력: ContractStatus 이력, TimelineEvent 리스트(10.3절 공통 이벤트 기준), 각 이벤트별 BlockchainStatus 배지
- 버튼: 이벤트 상세 보기, 블록체인 탐색기 링크(Polygon Amoy)
- 다음 화면: `/blockchain/[txId]`(이벤트 클릭 시)
- 오류 처리: 블록체인 조회 실패 시 "온체인 상태 확인 지연" 안내, DB 상태는 유지
- Loading: 타임라인 Skeleton(세로 리스트)
- Empty: 이벤트 없음(Draft 상태) 시 "아직 진행된 절차가 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예 (`mock_blockchain_tx_success.json`)

## 5.6 TEN-06 D-90 반환계획

- 목적: 계약 만료 90일 전 반환 준비 상태를 확인하고 이상징후를 조기경보한다.
- Route: `/tenant/d90/[contractId]`
- 접근권한: tenant
- 호출 API: `GET /api/v1/contracts/{contract_id}/return-plan`[확정 필요]
- 입력: 없음(조회), 반환계획 자체 제출은 임대인(LAND-03) 담당
- 출력: D-90 카운트다운, ReturnPlanStatus, 임대인 응답 여부, 조기경보 배지(미응답 기간 기준)
- 버튼: 임대인에게 알림 재발송, 사고 접수로 이동(경보 심각 시)
- 다음 화면: TEN-07(이상징후 심각 시), TEN-05(정상 진행 시)
- 오류 처리: 스케줄러 이벤트 미생성 시 "반환계획 요청이 아직 생성되지 않았습니다"
- Loading: 카운트다운 카드 Skeleton
- Empty: D-90 도달 전(계약 만료 90일 이전)에는 "아직 D-90 대상이 아닙니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.7 TEN-07 사고 접수

- 목적: 보증금 미반환 의심 상황을 신고하고 HUG 채권관리로 인계되는 절차를 안내한다.
- Route: `/tenant/incident/new`
- 접근권한: tenant
- 호출 API: `POST /api/v1/incidents`[확정 필요]
- 입력: 사고 사유, 계약 참조(contract_id 자동 연결), 첨부 서류(선택)
- 출력: 접수 완료 화면(incident_id), 예상 처리 절차 안내
- 버튼: 접수하기, 취소
- 다음 화면: TEN-05(타임라인에서 IncidentReported 상태 확인)
- 오류 처리: 중복 접수 방지 안내(이미 접수된 사건 존재 시), 필수값 검증
- Loading: 제출 버튼 스피너
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.8 LAND-01 증빙 요청 확인·제출

- 목적: 아이엔/규칙엔진이 생성한 보완요청을 확인하고 증빙을 업로드한다.
- Route: `/landlord/evidence/[requestId]`
- 접근권한: landlord
- 호출 API: `POST /api/v1/evidence`[확정 필요]
- 입력: 요청 사유 확인, 파일 업로드(등기부 말소 확인서 등)
- 출력: 업로드 파일 목록, document_hash, 제출 상태
- 버튼: 파일 첨부, 제출, 임시저장
- 다음 화면: LAND-02
- 오류 처리: 파일 형식/용량 오류, 업로드 실패 시 재시도 버튼
- Loading: 업로드 진행률 바
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.9 LAND-02 검증 상태 확인

- 목적: 제출한 증빙의 검증 진행 상태(Pending~Verified/Rejected)를 확인한다.
- Route: `/landlord/verification/[verificationId]`
- 접근권한: landlord
- 호출 API: `GET /api/v1/verifications/{verification_id}`[확정 필요]
- 입력: 없음
- 출력: VerificationStatus 칩, 검토 코멘트, 재제출 필요 여부
- 버튼: 재제출, 문의하기
- 다음 화면: LAND-01(재제출 시), LAND-03(검증 완료 후 D-90 도달 시)
- 오류 처리: Rejected 시 사유 표시, Expired 시 재요청 안내
- Loading: 상태 카드 Skeleton
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.10 LAND-03 반환계획 제출

- 목적: D-90 도달 시 보증금 반환 준비 계획을 제출한다.
- Route: `/landlord/return-plan/[contractId]`
- 접근권한: landlord
- 호출 API: `POST /api/v1/return-plans`[확정 필요]
- 입력: 반환 예정일, 반환 방법, 특이사항
- 출력: 제출 완료 확인, ReturnPlanStatus
- 버튼: 제출, 반환곤란 신고
- 다음 화면: LAND-00
- 오류 처리: 마감 초과 시 안내, 필수값 검증
- Loading: 제출 버튼 스피너
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.11 ADV-00 상담 현황

- 목적: 신규 상담과 전문가 이관 대상을 우선순위별로 정렬해 보여준다.
- Route: `/advisor`
- 접근권한: advisor
- 호출 API: `GET /api/v1/counsel-queue`[확정 필요]
- 입력: 필터(지역, 분쟁유형, 진행단계, 이관필요여부)
- 출력: 상담 리스트, `expert_referral` 배지, `dispute_type_confidence`
- 버튼: 상담 열기, 필터 적용
- 다음 화면: ADV-01
- 오류 처리: 목록 조회 실패 시 재시도 버튼
- Loading: 테이블 Skeleton
- Empty: "대기 중인 상담이 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.12 ADV-01 상담 상세 및 RAG 근거

- 목적: 상담 분류 모델 결과(모델 1)와 RAG 유사 상담사례를 함께 확인해 상담을 처리한다.
- Route: `/advisor/counsel/[counselId]`
- 접근권한: advisor
- 호출 API: `POST /api/v1/rag/search`(데이터수집가이드 부록 A), 상담 분류 결과 조회 `GET /api/v1/counsel/{counsel_id}`[확정 필요]
- 입력: 상담 원문, 처리 메모
- 출력: `predicted_dispute_type`, `predicted_stage`, `expert_referral_reasons`, 유사 상담사례 청크 리스트(source, chunk_id 포함)
- 버튼: 이관 처리(ADV-03), 검증 요청 생성, 메모 저장
- 다음 화면: ADV-02 또는 ADV-03
- 오류 처리: 모델 결과 없음(`InsufficientData`) 시 수동 분류 폼으로 전환
- Loading: 좌측 상담 상세 + 우측 RAG 근거 패널 각각 Skeleton
- Empty: RAG 근거 없음 시 "근거 문서를 찾지 못했습니다. 수동 검토가 필요합니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예 (`is_mock` 필드 표시)

## 5.13 ADV-02 증빙 검토

- 목적: 임대인이 제출한 증빙과 외부 API 조회 결과를 대조해 검증 상태를 확정한다.
- Route: `/advisor/verification/[verificationId]`
- 접근권한: advisor(verifier 서브 권한 필요)
- 호출 API: `POST /api/v1/verifications/{id}/decision`[확정 필요]
- 입력: 검토 코멘트, 승인/반려 선택
- 출력: 증빙 파일 뷰어, 외부 API 조회 결과 비교 카드
- 버튼: 승인, 반려, 보류
- 다음 화면: ADV-00
- 오류 처리: 결정 없이 이탈 시 임시저장 확인 다이얼로그
- Loading: 파일 뷰어 Skeleton
- Empty: 첨부 없음 시 "제출된 증빙이 없습니다"
- 권한 없음: verifier 권한 없는 advisor는 조회만 가능, 액션 버튼 비활성화 + 툴팁 안내
- Mock 지원: 예

## 5.14 ADV-03 전문가 이관

- 목적: 고위험 사건(압류·가압류·경매개시·중대한 계약서 불일치 등)을 전문가에게 이관 처리한다.
- Route: `/advisor/referral/[caseId]`
- 접근권한: advisor
- 호출 API: `POST /api/v1/referrals`[확정 필요]
- 입력: 이관 사유, 담당 전문가 배정, 우선순위
- 출력: 이관 완료 확인, 이관 이력
- 버튼: 이관 확정, 취소
- 다음 화면: ADV-00
- 오류 처리: 중복 이관 방지, 필수값 검증
- Loading: 제출 버튼 스피너
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.15 HUG-01 채권관리 대시보드

- 목적: 사고 접수 사건을 조기경보·회수등급·처리기간 기준으로 우선순위 정렬해 보여준다.
- Route: `/hug/dashboard`
- 접근권한: hug_admin
- 호출 API: `GET /api/v1/hug/dashboard`[확정 필요](모델 2·3 결과 집계 포함)
- 입력: 필터(지역, 회수등급, 처리기간 구간, 상태)
- 출력: 사건 카드 리스트(recovery_grade, expected_days, delay_risk), 요약 차트(등급별 분포, 처리기간 분포)
- 버튼: 사건 열기, 필터 적용, CSV 내보내기
- 다음 화면: HUG-02
- 오류 처리: 모델 결과 없음 시 "수동 우선순위(PoC 단계)" 배지 표시(개발설계보고서 부록 D, Recovery Service=PoC)
- Loading: 카드 리스트 + 차트 Skeleton
- Empty: "접수된 사건이 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.16 HUG-02 사건 상세

- 목적: 개별 사고 사건의 이력, 회수예측, 처리기간 예측, SHAP 근거를 상세 확인한다.
- Route: `/hug/case/[incidentId]`
- 접근권한: hug_admin
- 호출 API: `GET /api/v1/incidents/{incident_id}`[확정 필요], 모델 2·3 결과 `GET /api/v1/recovery-predictions/{id}`[확정 필요]
- 입력: 담당자 액션 메모
- 출력: 사건 이력, `expected_recovery_rate`, `recovery_grade`, `expected_days`, `delay_risk`, `top_factors`(SHAP 기여도, 관리자용 상세 근거)
- 버튼: 담당자 액션 기록, 유사사건 비교(HUG-03), 종결 처리
- 다음 화면: HUG-03
- 오류 처리: `ModelResultStatus` Failed/InsufficientData 시 수동 검토 안내
- Loading: 상세 패널 Skeleton
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예 (`mock_scenario_*.json` 10종 대응)

## 5.17 HUG-03 유사사건 비교

- 목적: 동일 지역/주택유형/절차유형 그룹 내 유사사건과 비교해 처리 판단을 보조한다.
- Route: `/hug/case/[incidentId]/similar`
- 접근권한: hug_admin
- 호출 API: `GET /api/v1/recovery-predictions/{id}/similar`[확정 필요]
- 입력: 비교 기준 선택(지역/주택유형/절차유형)
- 출력: `similar_group_summary`(sample_size 포함), 비교 테이블
- 버튼: 기준 변경, 사건 상세로 복귀
- 다음 화면: HUG-02
- 오류 처리: 표본 부족(sample_size 작음) 시 "표본이 적어 참고용으로만 사용하세요" 경고
- Loading: 테이블 Skeleton
- Empty: 유사사건 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.18 HUG-04 법인 집단위험

- 목적: 법인 임대인 관련 위험 신호를 집단(지역/주택유형) 단위로 확인한다. 비식별 법인키가 없어 개별 법인 추적은 제공하지 않는다(ML개발가이드 7.5절 한계 반영).
- Route: `/hug/entity/[entityId]`
- 접근권한: hug_admin
- 호출 API: `GET /api/v1/entity-risk-groups/{entity_group_id}`[확정 필요]
- 입력: 없음
- 출력: 집단 단위 위험 신호(DART 공시 여부, 사업자 상태 분포), "개별 법인 추적 불가" 안내 배너
- 버튼: 상세 사건 목록 보기
- 다음 화면: HUG-02
- 오류 처리: 데이터 부족 시 안내
- Loading: 카드 Skeleton
- Empty: "해당 집단의 위험 신호가 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.19 ADM-00 사용자·권한 관리

- 목적: 사용자 역할(tenant/landlord/advisor/hug_admin/verifier) 배정과 계정 상태를 관리한다.
- Route: `/admin`
- 접근권한: system_admin
- 호출 API: `GET /api/v1/admin/users`[확정 필요]
- 입력: 검색어, 역할 필터
- 출력: 사용자 테이블, 역할 배지, 최근 로그인
- 버튼: 역할 변경, 계정 비활성화
- 다음 화면: 없음(모달 내 처리)
- 오류 처리: 권한 변경 실패 시 롤백 안내
- Loading: 테이블 Skeleton
- Empty: "등록된 사용자가 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.20 ADM-01 외부 API/모델 상태

- 목적: 데이터수집가이드의 외부 API(CODEF, 도로명주소 등)와 ML 3개 모델의 가동 상태를 모니터링한다.
- Route: `/admin/api-status`
- 접근권한: system_admin
- 호출 API: `GET /api/v1/health`(데이터수집가이드 부록 A), `GET /api/v1/admin/model-status`[확정 필요]
- 입력: 없음
- 출력: API별 APIResultStatus 최근 이력, 모델별 ModelResultStatus 최근 이력, 평균 응답시간
- 버튼: 새로고침, 개별 API 강제 재조회
- 다음 화면: 없음
- 오류 처리: Health check 실패 시 전체 배너 경고
- Loading: 상태 카드 Skeleton
- Empty: 해당 없음
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.21 ADM-02 블록체인 로그

- 목적: 계약 버전 공증, 검증 이벤트 등 전체 블록체인 트랜잭션 로그를 조회한다.
- Route: `/admin/blockchain`
- 접근권한: system_admin
- 호출 API: `GET /api/v1/admin/blockchain-logs`[확정 필요]
- 입력: 기간 필터, BlockchainStatus 필터
- 출력: 트랜잭션 테이블(tx_hash, contract_address, status, 생성일)
- 버튼: Polygon Amoy 탐색기 링크, 필터 적용
- 다음 화면: `/blockchain/[txId]`
- 오류 처리: 체인 조회 지연 시 "Mock chain 로그 표시 중" 배지
- Loading: 테이블 Skeleton
- Empty: "기록된 트랜잭션이 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예 (`mock_blockchain_tx_success.json`)

## 5.22 ADM-03 시스템 로그

- 목적: API 재시도, 알림 발송, 인증 실패 등 시스템 이벤트 로그를 확인한다.
- Route: `/admin/logs`
- 접근권한: system_admin
- 호출 API: `GET /api/v1/admin/system-logs`[확정 필요]
- 입력: 로그 레벨 필터, 기간 필터
- 출력: 로그 테이블(개인정보 마스킹 적용, 데이터수집가이드 13장 기준)
- 버튼: 필터 적용, CSV 내보내기
- 다음 화면: 없음
- 오류 처리: 로그 조회 실패 시 재시도
- Loading: 테이블 Skeleton
- Empty: "로그가 없습니다"
- 권한 없음: `/unauthorized`
- Mock 지원: 예

## 5.23 공통 AUTH-01 로그인/역할 선택

- 목적: 로그인 후 역할에 따라 홈으로 라우팅한다.
- Route: `/login`
- 접근권한: 비로그인 사용자
- 호출 API: `POST /api/v1/auth/login`[확정 필요]
- 입력: 이메일/비밀번호 또는 소셜 로그인
- 출력: 세션 토큰, role 클레임
- 버튼: 로그인, 회원가입 이동
- 다음 화면: role별 홈(TEN-00/LAND-00/ADV-00/HUG-01/ADM-00)
- 오류 처리: 인증 실패 메시지, 잠금 계정 안내
- Loading: 버튼 스피너
- Empty: 해당 없음
- 권한 없음: 해당 없음(로그인 화면 자체)
- Mock 지원: 예(데모 계정)

## 5.24 공통 COMMON-01 알림 센터

- 목적: 역할별 알림(보완요청, D-90, 검증 결과 등)을 통합 조회한다.
- Route: `/notifications`
- 접근권한: 전체(로그인 사용자)
- 호출 API: `GET /api/v1/notifications`[확정 필요]
- 입력: 필터(읽음/안읽음, 유형)
- 출력: 알림 리스트
- 버튼: 읽음 처리, 알림 클릭 시 해당 화면 이동
- 다음 화면: 알림 유형별 해당 화면
- 오류 처리: 조회 실패 시 재시도
- Loading: 리스트 Skeleton
- Empty: "새 알림이 없습니다"
- 권한 없음: 비로그인 시 `/login` 리다이렉트
- Mock 지원: 예

권한 오류(403) 화면과 블록체인 트랜잭션 상세 화면(`/unauthorized`, `/blockchain/[txId]`)은 공용 컴포넌트(`UnauthorizedView`, `BlockchainTxDetail`)로 구현하며 별도 화면 ID를 부여하지 않는다. 이를 포함한 총 화면 개수는 **24개**다.

---

# 6. Wireframe

이미지가 아닌 ASCII Wireframe으로 표기한다. 레이아웃 골격만 정의하며 세부 스타일은 Component Library(7장)와 Tailwind 구현 시 결정한다.

## 6.1 TEN-01 주소·계약정보 입력

```
+--------------------------------------------------+
| Header (로고, 알림, 프로필)                        |
+--------------------------------------------------+
| ProgressStepper: [1.입력] 2.조회 3.결과 4.증빙       |
+--------------------------------------------------+
| AddressSearch (검색창 + 후보 리스트)                |
|--------------------------------------------------|
| ContractInputForm                                 |
|  - 보증금 입력                                     |
|  - 계약기간 (시작/종료)                             |
|  - 임대인 유형 (개인/법인)                          |
|  - 주택유형                                        |
+--------------------------------------------------+
|                              [임시저장] [다음 >]    |
+--------------------------------------------------+
```

## 6.2 TEN-02 외부 API 조회 진행

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| ProgressStepper: 1.입력 [2.조회] 3.결과 4.증빙       |
+--------------------------------------------------+
| 전체 진행률 [========------] 60%                  |
|--------------------------------------------------|
| [x] 도로명주소 정규화        Success               |
| [x] 등기부(CODEF)            Success               |
| [ ] 실거래가                 조회중... (spinner)    |
| [ ] 건축물대장                대기                  |
| [!] 사업자등록 상태           Failed [재시도] [업로드]|
+--------------------------------------------------+
|                                    [계속 진행 >]    |
+--------------------------------------------------+
```

## 6.3 TEN-03 위험진단 결과

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| ProgressStepper: 1.입력 2.조회 [3.결과] 4.증빙       |
+--------------------------------------------------+
| RiskCard                                          |
|  [HIGH] 위험등급          조회 2026-07-14 13:30    |
|  근거: 근저당설정, 전세가율 높음                     |
|  출처: CODEF / 실거래가        model_version: v1.0 |
|--------------------------------------------------|
| 해결 가능한 위험     |     해결 불가능한 위험         |
|  - 근저당 말소 예정  |     - 건물 구조적 노후          |
|--------------------------------------------------|
| RAG 유사 상담사례 리스트 (근거 chunk_id 표시)        |
+--------------------------------------------------+
|                    [상담 요청] [증빙 요청 확인하기 >]|
+--------------------------------------------------+
```

## 6.4 TEN-04 증빙·검증 진행

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| EvidenceRequestCard (사유: 근저당 말소 확인)          |
|  StatusChip: [Reviewing]                          |
|  제출 파일: 말소확인서.pdf (2026-07-14 제출)          |
+--------------------------------------------------+
| Timeline (요청 -> 제출 -> 검토 -> 완료)               |
+--------------------------------------------------+
|                              [새로고침] [알림 재발송] |
+--------------------------------------------------+
```

## 6.5 TEN-05 계약 타임라인

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| ContractCard (contract_id, ContractStatus 배지)     |
+--------------------------------------------------+
| Timeline (세로)                                    |
|  ● ContractCreated        2026-07-01  [Confirmed] |
|  ● RiskAssessed           2026-07-02  [Confirmed] |
|  ● EvidenceSubmitted      2026-07-05  [Pending]   |
|  ○ VerificationCompleted  -                        |
+--------------------------------------------------+
```

## 6.6 TEN-06 D-90 반환계획

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| D-90 CountdownCard                                 |
|  D-62  계약만료 2026-09-14                          |
|  임대인 응답: 미응답 [조기경보 배지]                  |
+--------------------------------------------------+
|                  [임대인에게 알림 재발송] [사고 접수] |
+--------------------------------------------------+
```

## 6.7 TEN-07 사고 접수

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| IncidentForm                                       |
|  - 사고 사유 선택                                   |
|  - 계약 참조 (자동 연결, 읽기전용)                    |
|  - 첨부 서류 업로드(선택)                             |
+--------------------------------------------------+
|                                  [취소] [접수하기]   |
+--------------------------------------------------+
```

## 6.8 LAND-01 증빙 요청 확인·제출

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| EvidenceRequestCard (사유, 마감일)                   |
+--------------------------------------------------+
| EvidenceUploader                                   |
|  [파일 드래그 앤 드롭 영역]                           |
|  업로드 목록: 말소확인서.pdf [====] 100%             |
+--------------------------------------------------+
|                                [임시저장] [제출]     |
+--------------------------------------------------+
```

## 6.9 ADV-01 상담 상세 및 RAG 근거

```
+---------------------------+------------------------+
| Header                                              |
+---------------------------+------------------------+
| 상담 원문 패널              | RAG 근거 패널            |
|  지역/보증금구간/주택유형     |  유사사례 1 (source, tag)|
|  상담 텍스트 전문            |  유사사례 2              |
|                             |  유사사례 3              |
| ResultCard(모델1 결과)       |                        |
|  분쟁유형: 보증금미반환 71%   |                        |
|  진행단계: 소송제기 64%       |                        |
|  expert_referral: true       |                        |
+---------------------------+------------------------+
|                    [메모 저장] [검증요청] [이관처리 >]  |
+------------------------------------------------------+
```

## 6.10 HUG-01 채권관리 대시보드

```
+--------------------------------------------------+
| Header + Sidebar(HUG 메뉴)                          |
+--------------------------------------------------+
| 요약 Chart: 회수등급 분포 | 처리기간 분포 (2단 Chart) |
+--------------------------------------------------+
| 필터: [지역v][등급v][처리기간구간v]        [내보내기] |
+--------------------------------------------------+
| 사건 카드 리스트 (우선순위 정렬)                       |
|  [HIGH delay_risk] 사건#123  회수등급 MEDIUM  145일   |
|  [MEDIUM]          사건#124  회수등급 HIGH    88일    |
+--------------------------------------------------+
```

## 6.11 HUG-02 사건 상세

```
+--------------------------------------------------+
| Header                                            |
+--------------------------------------------------+
| CaseSummaryCard (incident_id, 사고사유, 지역)         |
+--------------------------------------------------+
| RecoveryCard              | DurationCard            |
|  expected_recovery_rate    |  expected_days          |
|  recovery_grade: MEDIUM    |  delay_risk: MEDIUM     |
|  top_factors (SHAP)        |  top_factors (SHAP)     |
+--------------------------------------------------+
|                    [담당자 액션 기록] [유사사건 비교] |
+--------------------------------------------------+
```

---

# 7. Component Library

역할, Props, 호출 API, 사용 화면을 정의한다. 총 33개 컴포넌트다.

## 7.1 레이아웃/공통

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| Header | 로고, 알림 아이콘, 프로필 메뉴 | `user`, `unreadCount` | - | 전체 |
| Sidebar | 역할별 메뉴 네비게이션 | `role`, `activeRoute` | - | HUG, 아이엔, 관리자 |
| ProgressStepper | 위험진단 단계 표시(1~4단계) | `currentStep`, `steps[]` | - | TEN-01~04 |
| RoleGuard | 역할 기반 라우트 접근 제어 | `allowedRoles[]`, `children` | 세션 role 클레임 | 전체 |
| LoadingSpinner | 버튼/영역 로딩 표시 | `size`, `label` | - | 전체 |
| Toast | 성공/오류/경고 알림 팝업 | `type`, `message`, `duration` | - | 전체 |
| Modal | 확인/입력 다이얼로그 | `title`, `onConfirm`, `onCancel` | - | 전체 |
| Notification | 알림 리스트 아이템 | `notification`, `onClick` | `GET /api/v1/notifications` | COMMON-01 |
| Pagination | 목록 페이지네이션 | `page`, `totalPages`, `onChange` | - | ADV-00, HUG-01, ADM-00~03 |

## 7.2 주소/계약 입력

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| AddressSearch | 주소 검색 및 후보 선택 | `onSelect`, `value` | `POST /api/v1/address/normalize` | TEN-01 |
| ContractInputForm | 보증금/기간/임대인유형 입력 폼(RHF+Zod) | `defaultValues`, `onSubmit` | - | TEN-01 |
| APIProgressList | 외부 API 조회 단계별 상태 리스트 | `steps[]`(name, status) | `POST /api/v1/risk/diagnose` | TEN-02 |
| FallbackAlert | API 실패 시 재시도/업로드/Mock 전환 안내 | `apiName`, `onRetry`, `onUpload`, `onMock` | - | TEN-02, 전체 조회 화면 |

## 7.3 위험진단/증빙

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| RiskCard | 위험등급, 근거, 출처, 모델버전 표시 | `riskGrade`, `reasons[]`, `dataSource`, `modelVersion` | `GET /api/v1/risk/{case_id}` | TEN-03 |
| RiskBadge | 위험등급 색상 배지(HIGH/MEDIUM/LOW) | `grade` | - | TEN-03, HUG-01, HUG-02 |
| RAGEvidenceList | 유사 상담사례/근거 문서 리스트 | `chunks[]` | `POST /api/v1/rag/search` | TEN-03, ADV-01 |
| EvidenceUploader | 파일 드래그앤드롭 업로드 | `onUpload`, `accept`, `maxSizeMB` | `POST /api/v1/evidence` | LAND-01 |
| EvidenceRequestCard | 보완요청 사유/마감/상태 카드 | `request` | - | TEN-04, LAND-01 |
| VerificationStatusChip | VerificationStatus 색상 칩 | `status` | - | TEN-04, LAND-02, ADV-02 |
| ReferralBanner | 전문가 이관 필요 배너 | `reasons[]` | - | TEN-03, ADV-01 |

## 7.4 타임라인/블록체인

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| Timeline | 세로형 이벤트 타임라인 | `events[]` | `GET /api/v1/contracts/{id}/timeline` | TEN-05, HUG-02 |
| StatusChip | ContractStatus 등 공통 상태 칩 | `status`, `statusGroup` | - | 전체 |
| BlockchainBadge | BlockchainStatus(Pending/Confirmed/Failed) 배지 + tx 링크 | `status`, `txHash` | `GET /api/v1/blockchain/{tx_id}` | TEN-05, ADM-02, BlockchainTxDetail |
| ContractCard | 계약 요약 카드(contract_id, 상태, 물건정보) | `contract` | - | TEN-00, TEN-05 |

## 7.5 D-90/사고

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| D90CountdownCard | D-90 카운트다운, 응답상태, 조기경보 | `dueDate`, `responseStatus` | `GET /api/v1/contracts/{id}/return-plan` | TEN-06 |
| IncidentForm | 사고 접수 폼(RHF+Zod) | `contractId`, `onSubmit` | `POST /api/v1/incidents` | TEN-07 |

## 7.6 HUG/관리자

| Component | 역할 | Props | 호출 API | 사용 화면 |
|---|---|---|---|---|
| ResultCard | ML 모델 결과 공통 카드(분류/회귀 겸용) | `modelType`, `result`, `isMock` | 모델 1/2/3 API | ADV-01, HUG-02 |
| RecoveryCard | 회수율/회수등급 표시 | `expectedRecoveryRate`, `recoveryGrade`, `topFactors[]` | `GET /api/v1/recovery-predictions/{id}` | HUG-02 |
| CaseSummaryCard | 사건 요약(사고사유, 지역, 접수일) | `incident` | `GET /api/v1/incidents/{id}` | HUG-02 |
| EntityRiskCard | 법인 집단위험 신호 카드 | `entityGroup` | `GET /api/v1/entity-risk-groups/{id}` | HUG-04 |
| Chart | Recharts 래퍼(분포/추이 차트) | `type`, `data`, `xKey`, `yKey` | - | HUG-01 |
| DataSourceFooter | 조회시각/출처/모델버전/블록체인상태 공통 표기 | `fetchedAt`, `source`, `modelVersion`, `blockchainStatus` | - | RiskCard, ResultCard, RecoveryCard 내부 |
| MockBadge | `is_mock: true` 결과에 대한 시각적 구분 배지 | `isMock` | - | RiskCard, ResultCard, RecoveryCard |

컴포넌트 총 개수는 표 6개 그룹 합산 **33개**다(DurationCard는 ResultCard의 `modelType="duration"` variant로 흡수해 별도 컴포넌트로 만들지 않는다).

---

# 8. API Mapping

화면별 호출 흐름을 데이터수집가이드 1장 데이터 흐름도, 개발설계보고서 9장 아키텍처와 정합성 있게 정리한다. Backend 전체 REST 계약은 Backend_API_명세서_260714.md에서 확정되므로, 여기서는 Frontend가 알아야 하는 "무엇을 언제 호출하는지"만 정의한다.

## 8.1 위험진단 흐름 (TEN-01 → TEN-04)

```
AddressSearch
   ↓ POST /api/v1/address/normalize   (데이터수집가이드 부록A, MVP)
표준주소 확정
   ↓ POST /api/v1/risk/diagnose       (데이터수집가이드 부록A, MVP)
     내부: CODEF(또는 Mock) -> 건축물대장 -> 실거래가 -> 공시가격(Mock) -> 사업자/DART
   ↓ Backend Feature 생성 -> Rule Engine -> ML(상담모델은 미해당, 위험진단은 규칙엔진 중심)
Risk 결과 저장
   ↓ GET /api/v1/risk/{case_id}       (데이터수집가이드 부록A)
RiskCard 렌더링
   ↓ POST /api/v1/rag/search          (데이터수집가이드 부록A)
RAGEvidenceList 렌더링
   ↓ (보완 필요 시) EvidenceRequest 생성 -> TEN-04에서 조회
   ↓ (검증 완료 시) Blockchain Adapter -> tx_hash -> TimelineEvent
```

## 8.2 상담 분류 흐름 (ADV-00 → ADV-03)

```
상담 현황 조회 [확정 필요]
   ↓
ADV-01 상담 상세
   ↓ 모델 1 추론 (ML개발가이드 20.3절 계약, 정확한 Path는 Backend 확정 필요)
   Request: {region, deposit_range, housing_type, counsel_text}
   Response: {predicted_dispute_type, dispute_type_confidence, expert_referral, model_version, is_mock}
   ↓ POST /api/v1/rag/search
   유사 상담사례 검색 (similar_case_query = 모델1 출력 필드)
   ↓ expert_referral=true 인 경우
ADV-03 전문가 이관
```

## 8.3 회수·처리기간 흐름 (HUG-01 → HUG-03)

```
사고 접수(TEN-07) -> Backend 자동 인계
   ↓
모델 2(회수) 추론 (ML개발가이드 20.3절 계약)
   Request: {product_name, claim_amount, region, housing_type, landlord_type}
   Response: {expected_recovery_rate, recovery_grade, top_factors, model_version, is_mock}
   ↓
모델 3(처리기간) 추론 (ML개발가이드 20.3절 계약)
   Request: {procedure_type, claim_amount, region}
   Response: {expected_days, delay_risk, top_factors, model_version, is_mock}
   ↓
HUG-01 대시보드 집계 표시 -> HUG-02 사건 상세 -> HUG-03 유사사건 비교
```

## 8.4 블록체인 흐름 (TEN-05, ADM-02)

```
검증 완료 / 계약버전 확정 / D-90 이벤트 / 사고 인계
   ↓
Backend -> POST /api/v1/blockchain/anchor  (데이터수집가이드 부록A)
   ↓
Polygon Amoy 또는 Mock chain -> tx_hash 반환
   ↓
BlockchainStatus: Pending -> Confirmed/Failed
   ↓
TEN-05 Timeline, ADM-02 블록체인 로그에 반영
```

## 8.5 화면별 API 매핑 요약표

| 화면 ID | 주 호출 API | Mock 대응 |
|---|---|---|
| TEN-01 | `POST /address/normalize` | `mock_address.json` |
| TEN-02 | `POST /risk/diagnose` | 등기부 3종, 실거래가없음, 사업자폐업 등 |
| TEN-03 | `GET /risk/{case_id}`, `POST /rag/search` | `is_mock` 필드 |
| TEN-04 | `GET /evidence-requests`[확정 필요] | mock evidence status |
| TEN-05 | `GET /contracts/{id}/timeline`[확정 필요], `GET /blockchain/{tx_id}`[확정 필요] | `mock_blockchain_tx_success.json` |
| TEN-06 | `GET /contracts/{id}/return-plan`[확정 필요] | mock D-90 |
| TEN-07 | `POST /incidents`[확정 필요] | mock 접수 |
| LAND-01~03 | `POST /evidence`, `GET /verifications/{id}`, `POST /return-plans`[확정 필요] | mock 증빙/검증 |
| ADV-00~03 | 상담 현황[확정 필요], 모델1 추론, `POST /rag/search`, `POST /verifications/{id}/decision`[확정 필요], `POST /referrals`[확정 필요] | `is_mock` + mock 상담 현황 |
| HUG-01~04 | HUG 대시보드[확정 필요], 모델2·3 추론, 유사사건[확정 필요], 법인집단[확정 필요] | `mock_scenario_1~10.json` |
| ADM-00~03 | 사용자관리/API상태/블록체인로그/시스템로그[확정 필요], `GET /health` | mock 상태 |

---

# 9. 상태 정의

화면 단위로 Loading, Success, Partial, Error, Empty, Unauthorized, NotFound, API Timeout, Mock 9가지 상태를 정의한다. 공통 규칙과 화면별 특이사항으로 나눈다.

## 9.1 공통 규칙

| 상태 | 공통 처리 |
|---|---|
| Loading | Skeleton UI(데이터 형태를 반영한 회색 블록), 300ms 미만이면 표시하지 않음(깜빡임 방지) |
| Success | 정상 데이터 렌더링, `DataSourceFooter`에 조회시각·출처 표기 |
| Partial | `APIResultStatus=Partial` 배지 표시, 캐시/일부 데이터임을 명시 |
| Error | Toast + 인라인 오류 메시지, 재시도 버튼 제공 |
| Empty | 일러스트 없는 텍스트 안내 + 다음 행동 버튼(가능한 경우) |
| Unauthorized | `/unauthorized` 리다이렉트, 홈으로 돌아가기 버튼 |
| NotFound | 404 페이지, 목록으로 돌아가기 버튼 |
| API Timeout | 타임아웃 안내 + 자동 재시도(최대 2회) 후 실패 처리 |
| Mock | `MockBadge` 표시, "시연용 데이터" 텍스트 명시(ML개발가이드 23.1절 `is_mock` 필드 연동) |

## 9.2 화면별 특이 상태

| 화면 | 특이 상태 처리 |
|---|---|
| TEN-02 | 개별 API별 상태를 독립적으로 관리(전체 Loading이 아니라 API 단위 상태 배열) |
| TEN-03 | `ModelResultStatus=RuleOnlyFallback`일 때 별도 경고 배너("모델 추론 실패, 규칙 기반 결과만 표시") |
| TEN-03 | `ModelResultStatus=InsufficientData`일 때 "판단에 필요한 정보가 부족합니다" + 추가 입력 유도 |
| TEN-05 | `BlockchainStatus=Failed`여도 DB 상태는 별도로 유지, 온체인 기록만 실패로 표시 |
| ADV-02 | verifier 권한 없는 사용자는 Unauthorized가 아니라 "읽기 전용" 상태(액션 버튼 disabled) |
| HUG-01 | 모델 결과가 전혀 없는 사건은 "수동 우선순위 필요" Empty 변형 상태 |
| HUG-03 | `sample_size`가 임계값(예: 10) 미만이면 Partial 취급하고 경고 문구 추가 |

---

# 10. UX 원칙

## 10.1 위험등급 색상/Badge

| 등급 | 색상 토큰(의미) | 사용처 |
|---|---|---|
| HIGH | danger(적색 계열) | RiskBadge, HUG-01 필터 |
| MEDIUM | warning(주황 계열) | RiskBadge |
| LOW | success(녹색 계열) | RiskBadge |
| 회수등급 HIGH/MEDIUM/LOW | success/warning/danger 역방향 매핑 명시(회수등급은 높을수록 긍정) | RecoveryCard |
| delay_risk HIGH/MEDIUM/LOW | danger/warning/success | DurationCard(ResultCard variant) |

색상은 shadcn/ui 테마 토큰(semantic color)만 사용하고 하드코딩 HEX를 컴포넌트에 직접 넣지 않는다.

## 10.2 Progress

위험진단 4단계(TEN-01~04)는 `ProgressStepper`로 항상 현재 단계를 노출한다. API 조회 단계(TEN-02)는 단계별 진행률과 개별 API 상태를 동시에 보여주어 "무엇이 왜 지연되는지" 숨기지 않는다(데이터수집가이드 5장 실패 대응 원칙과 정합).

## 10.3 Toast / Dialog / Alert 기준

Toast는 3초 이내 자동 소멸하는 비파괴적 알림(저장 완료, 새로고침 완료)에만 사용한다. Dialog(Modal)는 되돌릴 수 없는 액션(제출, 이관 확정, 계정 비활성화) 확인에만 사용한다. Alert(인라인 배너)는 화면 상태에 지속적으로 영향을 주는 경고(RuleOnlyFallback, Partial, 권한 제한)에 사용하며 사용자가 닫아도 상태가 남아 있으면 다시 노출한다.

## 10.4 근거·투명성 우선 원칙 (개발설계보고서 12.4절 계승)

모든 위험/예측 결과 카드는 점수보다 근거와 다음 행동을 먼저 배치한다. 해결 가능한 위험과 해결 불가능한 위험은 레이아웃상 별도 컬럼/섹션으로 분리한다. 모든 조회 결과에는 조회시각, 데이터 출처, 모델 버전, 블록체인 상태를 표시한다. 블록체인 상태는 Pending/Confirmed/Failed 3단계로만 표시하고 "법적 효력이 있다"는 문구를 사용하지 않는다. SHAP 기반 근거는 ML개발가이드 부록 F의 금지 표현("실제 사고확률" 등)을 UI 문구에 사용하지 않는다.

---

# 11. Responsive

Desktop을 기준으로 설계하고 Tablet은 주요 기능 유지, Mobile은 임차인·임대인 화면(TEN-*, LAND-*)만 우선 지원한다. HUG·아이엔·관리자 화면은 업무용 데스크톱 사용을 전제로 Tablet까지만 지원한다.

| Breakpoint | 대상 | 지원 범위 |
|---|---|---|
| Desktop (>=1280px) | 전체 화면 | 전체 기능 완전 지원, 대시보드 다단 레이아웃 |
| Tablet (768~1279px) | 전체 화면 | Sidebar 축소(아이콘형), 카드 1~2열 재배치, 표는 가로 스크롤 |
| Mobile (<768px) | TEN-*, LAND-*, 공통(로그인/알림) | 단일 컬럼, ProgressStepper는 상단 고정 축약형, 하단 고정 CTA 버튼 |
| Mobile 미지원 | ADV-*, HUG-*, ADM-* | "데스크톱에서 이용해주세요" 안내 화면으로 대체 |

---

# 12. Accessibility

| 항목 | 기준 |
|---|---|
| ARIA | 모든 상태 배지(StatusChip, RiskBadge, BlockchainBadge)에 `aria-label`로 상태 텍스트 명시. Modal은 `role="dialog"`, `aria-modal="true"` |
| Keyboard | 모든 인터랙션 요소는 Tab 순서로 접근 가능해야 하며, EvidenceUploader의 드래그앤드롭은 파일 선택 버튼 대체 수단 제공. Modal은 Esc로 닫기, Focus trap 적용 |
| Contrast | 텍스트 대비 WCAG AA(4.5:1) 이상. RiskBadge 색상은 색상만으로 구분하지 않고 텍스트/아이콘 병기(색맹 대응) |
| Focus | 라우트 전환 시 포커스를 페이지 제목(h1)으로 이동. Toast 등장 시 포커스를 가로채지 않음 |
| 폼 | React Hook Form 오류 메시지는 `aria-describedby`로 입력 필드와 연결 |

---

# 13. 상태관리 (React Query / Zustand)

## 13.1 React Query로 관리하는 서버 상태

| Query Key | 대상 | 사용 화면 |
|---|---|---|
| `['address', keyword]` | 주소 검색 결과 | TEN-01 |
| `['riskDiagnosis', propertyId]` | 외부 API 조회 진행 상태 | TEN-02 |
| `['riskResult', caseId]` | 위험진단 결과 | TEN-03 |
| `['ragSearch', query]` | RAG 검색 결과 | TEN-03, ADV-01 |
| `['evidenceRequests', caseId]` | 보완요청 목록 | TEN-04, LAND-01 |
| `['verification', verificationId]` | 검증 상태 | TEN-04, LAND-02, ADV-02 |
| `['timeline', contractId]` | 계약 타임라인 | TEN-05 |
| `['blockchainTx', txId]` | 블록체인 트랜잭션 상태 | TEN-05, ADM-02 |
| `['returnPlan', contractId]` | D-90 반환계획 | TEN-06, LAND-03 |
| `['counselQueue', filters]` | 상담 현황 목록 | ADV-00 |
| `['counselDetail', counselId]` | 상담 상세 + 모델1 결과 | ADV-01 |
| `['hugDashboard', filters]` | HUG 대시보드 집계 | HUG-01 |
| `['incident', incidentId]` | 사건 상세 + 모델2·3 결과 | HUG-02 |
| `['similarCases', incidentId, criteria]` | 유사사건 비교 | HUG-03 |
| `['entityRiskGroup', entityId]` | 법인 집단위험 | HUG-04 |
| `['apiHealth']` | 외부 API/모델 상태(짧은 staleTime, polling) | ADM-01 |
| `['notifications']` | 알림 목록 | COMMON-01 |

React Query 공통 정책: `staleTime`은 조회 성격에 따라 차등(주소 검색 0, 위험결과 5분, HUG 대시보드 1분polling), 실패 시 자동 재시도는 2회로 제한하고 이후는 `FallbackAlert`로 사용자에게 위임한다(자동 무한 재시도 금지, 데이터수집가이드 5장과 정합).

## 13.2 Zustand로 관리하는 전역 클라이언트 상태

| Store | 관리 대상 | 사용 범위 |
|---|---|---|
| `useSessionStore` | 로그인 사용자, role, 세션 만료 여부 | 전체(RoleGuard가 참조) |
| `useRiskWizardStore` | TEN-01~02 위저드 임시 입력값(주소, 계약조건), 현재 단계 | TEN-01, TEN-02 |
| `useUIStore` | Sidebar collapse 여부, 활성 Modal, Toast 큐 | 전체 |
| `useMockModeStore` | 발표/데모 모드 강제 Mock 전환 스위치(관리자 전용) | ADM-01, 시연 시나리오 전환 |
| `useSelectedCaseStore` | HUG-02~04, ADV-01~03에서 현재 작업 중인 caseId/incidentId 공유 | HUG-*, ADV-* |
| `useFilterStore` | 목록 화면(ADV-00, HUG-01, ADM-00~03)의 필터/정렬 상태 유지(뒤로가기 시 복원) | 목록형 화면 |

React Query는 "서버가 갖고 있는 데이터"만 담당하고, Zustand는 "화면 간 공유되는 UI/입력 상태"만 담당한다는 경계를 지킨다. 서버 데이터를 Zustand에 복제해 캐시 두 곳을 유지하지 않는다.

---

# 14. 폴더 구조

```
frontend/
├── app/                     # Next.js App Router 라우트, 화면별 page.tsx/layout.tsx
│   ├── (auth)/login/
│   ├── (common)/notifications/, unauthorized/, blockchain/[txId]/
│   ├── tenant/
│   ├── landlord/
│   ├── advisor/
│   ├── hug/
│   └── admin/
├── components/              # 7장 Component Library, 재사용 UI 컴포넌트
│   ├── common/               # Header, Sidebar, Toast, Modal 등
│   ├── risk/                 # RiskCard, RiskBadge, RAGEvidenceList 등
│   ├── evidence/              # EvidenceUploader, EvidenceRequestCard 등
│   └── hug/                   # ResultCard, RecoveryCard, Chart 등
├── features/                 # 화면 단위 기능 모듈(로컬 상태+UI 조합), Route 폴더와 1:1 매핑
│   ├── tenant-risk-check/
│   ├── landlord-evidence/
│   ├── advisor-counsel/
│   └── hug-dashboard/
├── hooks/                     # useRiskDiagnosis, useTimeline 등 React Query 커스텀 훅
├── lib/                       # 공통 유틸(포맷터, 상수, RoleGuard 로직)
├── services/                   # API client(fetch wrapper), 화면별 API 함수 모음
├── types/                      # 공통 식별자/상태(개발설계보고서 10장) 타입 정의, Zod 스키마
├── stores/                     # Zustand store 정의(13.2절)
├── styles/                     # Tailwind 전역 설정, globals.css
└── public/                     # 정적 자산
```

각 폴더 역할은 다음과 같다. `app/`은 라우팅과 서버 컴포넌트 진입점만 담당하고 로직은 최소화한다. `components/`는 여러 화면에서 재사용되는 순수 UI다. `features/`는 특정 화면 전용 조합 로직(폼 상태, 위저드 흐름)을 담아 `app/`과 `components/` 사이를 연결한다. `hooks/`는 13.1절 React Query 키를 캡슐화한다. `services/`는 `[확정 필요]` API를 포함해 Backend_API_명세서 확정 후 갱신될 유일한 지점으로, 나머지 코드는 이 계층을 통해서만 API를 호출한다. `types/`는 개발설계보고서 10장 공통 식별자·상태를 TypeScript 타입/Zod 스키마로 1:1 매핑해 문서-코드 불일치를 방지한다.

---

# 15. 개발 순서

개발설계보고서 14장(6개 문서를 활용하는 개발 순서)의 7번 항목("Frontend UI/UX 명세서 작성")을 세분화한다.

```
공통 Layout (Header, Sidebar, RoleGuard, Toast, Modal)
   ↓
Login (AUTH-01, 세션/역할 분기)
   ↓
Tenant (TEN-00~02: 홈, 주소·계약입력, API조회)
   ↓
Risk (TEN-03: 위험진단 결과, RiskCard/RAGEvidenceList)
   ↓
Evidence (TEN-04, LAND-01~02: 증빙 요청/제출/검증)
   ↓
Timeline (TEN-05~07: 타임라인, D-90, 사고접수 + LAND-03)
   ↓
HUG (HUG-01~04: 대시보드, 사건상세, 유사사건, 법인집단)
   ↓
Admin (ADM-00~03) + Advisor (ADV-00~03, HUG와 병행 가능)
```

모든 단계는 Mock API 기반으로 먼저 구현하고(개발설계보고서 표 27, 7단계 "Mock API 기반 Frontend 구현"), Backend 구현 완료 후 `services/` 계층의 엔드포인트만 교체한다.

---

# 16. TODO

- [ ] `types/` 폴더에 공통 식별자 16종(10.4절 Backend 참조표 기준) TypeScript 타입 정의
- [ ] `types/` 폴더에 공통 상태 5종(ContractStatus 등) Union 타입 및 Zod enum 정의
- [ ] Next.js App Router 라우트 28개 스캐폴딩(2장 기준)
- [ ] RoleGuard 미들웨어 구현 및 6개 역할 접근 테스트
- [ ] Component Library 28개 shadcn/ui 기반 구현
- [ ] React Query 17개 Query Key 및 커스텀 훅 구현
- [ ] Zustand Store 6개 구현
- [ ] Mock API 서버 또는 MSW 기반 Mock Handler 11종+ 연결(데이터수집가이드 6.1절 Mock JSON과 매핑)
- [ ] `services/` API client에 `[확정 필요]` 엔드포인트 스텁 작성(Backend 확정 시 일괄 교체)
- [ ] TEN-01~07 화면 구현 및 위저드 흐름 통합 테스트
- [ ] LAND-01~03 화면 구현
- [ ] ADV-00~03 화면 구현
- [ ] HUG-01~04 화면 구현 및 Recharts 연동
- [ ] ADM-00~03 화면 구현
- [ ] 반응형 브레이크포인트 3종 QA(11장)
- [ ] 접근성 체크리스트(12장) 스크린리더/키보드 테스트
- [ ] `is_mock`, `ModelResultStatus`, `APIResultStatus`, `BlockchainStatus` 배지 전체 화면 일관성 점검
- [ ] 발표용 시나리오(개발설계보고서 표 29, 6개) 기준 E2E 리허설

---

# 17. Definition of Done

화면 단위 완료 기준은 다음 5개 항목을 모두 충족해야 한다.

| 기준 | 세부 조건 |
|---|---|
| API 연결 | 5장에 정의된 호출 API가 실제(또는 Mock) 응답과 연결되어 있고, `[확정 필요]` 항목은 Mock으로 우선 대체되어 있다. |
| Loading/Error/Empty | 9장에 정의된 9개 상태(Loading/Success/Partial/Error/Empty/Unauthorized/NotFound/Timeout/Mock) 중 해당 화면에 적용 가능한 상태가 모두 UI로 구현되어 있다. |
| Responsive | 11장 기준 Desktop에서 완전 동작하고, 지원 대상 화면은 Tablet/Mobile에서도 레이아웃 깨짐 없이 동작한다. |
| Accessibility | 12장 기준 키보드 전용 조작이 가능하고, 주요 상태 배지에 대비/텍스트 대체 수단이 있다. |
| 상태 배지 일관성 | RiskBadge/StatusChip/BlockchainBadge/MockBadge가 10장 색상 규칙과 화면 간 동일한 의미로 표시된다. |

---

# 18. 제외사항

본 문서에는 CSS 코드, React 컴포넌트 구현 코드, Figma 파일, 이미지 목업을 포함하지 않는다. 6장 Wireframe은 레이아웃 골격을 나타내는 ASCII 표기이며 픽셀 단위 디자인 스펙이 아니다. 내부 REST API의 정확한 Path·Request/Response DTO·오류코드·인증 방식은 Backend_API_명세서_260714.md에서 정의하며, 본 문서의 `[확정 필요]` 표기는 해당 문서 작성 후 일괄 갱신 대상이다. Solidity 컨트랙트 함수·이벤트·배포 스크립트는 Blockchain_설계서_260714.md에서 정의한다. ML 모델의 Feature Engineering, 학습·평가 방식은 ML개발가이드_260714.md를 따르며 본 문서는 Frontend가 소비하는 입출력 계약만 인용한다.

---

*본 문서는 개발설계보고서_260714_수정보완.docx, 데이터수집_및_API가이드_260714.md, ML개발가이드_260714.md를 선행 문서로 확인한 뒤 Frontend 관점에서 재정리하여 작성했다. `[확정 필요]`로 표시된 API 경로는 Backend_API_명세서_260714.md 작성 후 갱신한다.*
