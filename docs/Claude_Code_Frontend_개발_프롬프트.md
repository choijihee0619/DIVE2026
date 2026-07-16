# Claude Code용 프롬프트 — HUG 안심전세 체인 Frontend 개발

아래 내용을 Claude Code에 그대로 붙여넣어 시작할 것. `[프로젝트 루트]`는 실제 로컬 경로로 치환.

---

## 0. 프로젝트 컨텍스트

`[프로젝트 루트]/backend`에 FastAPI 백엔드가 이미 구현·테스트 완료 상태다(health/auth/users/properties/landlords/contracts/evidence/risk/rag/blockchain 8개 도메인, pytest 31건 통과). `[프로젝트 루트]/docs`에 전체 설계 문서가 있고, `[프로젝트 루트]/웹사이트 UI 디자인 요청`에 4개 역할(Tenant/Landlord/Advisor/HUG)별 인터랙티브 화면 목업(.dc.html)이 이미 만들어져 있다.

이번 작업은 `[프로젝트 루트]/frontend`에 **새 Next.js 프로젝트를 만들어** 이 목업들을 참고해서 실제 백엔드와 연동되는 프론트엔드를 구현하는 것이다.

먼저 아래 파일들을 읽고 계획을 세운 뒤 작업을 시작할 것:

1. `docs/Frontend_UIUX_명세서_260714.md` — 전체 스펙(라우트, 화면 24개, 컴포넌트, 상태관리, 개발순서, TODO, Definition of Done)
2. `backend/README.md` — 백엔드 실행 방법, Mock 모드 설명, **API_Contract와 실제 구현 사이의 의도적 차이 5건**(8절)
3. `backend/app/schemas/*.py`, `backend/app/api/v1/endpoints/*.py`, `backend/app/api/v1/router.py` — 실제 구현된 API의 정확한 요청/응답 스키마와 등록된 엔드포인트 목록
4. `웹사이트 UI 디자인 요청/ds/styles.css` — 디자인 토큰(색상/간격/폰트)
5. `웹사이트 UI 디자인 요청/*-Interactive.dc.html` (Tenant-Web, Landlord, Advisor, HUG) — 화면 레이아웃·카피·인터랙션 흐름 참고용

## 1. 절대 원칙

**API 타입의 유일한 기준은 `backend/app/schemas/*.py` 코드다.** `docs/API_Contract_260714.yaml`이 아니다. 둘 사이에 5개의 의도적 차이가 있다(`backend/README.md` 8절 확인): `/risk/diagnose`는 202 비동기가 아니라 200 즉시 응답, 위험등급은 A/B/C가 아니라 `LOW/MEDIUM/HIGH`, `/verifications/{id}`는 `verification_id`가 아니라 `evidence_id`, `/auth/signup`은 계약에 없는 추가 엔드포인트, `/blockchain/anchor`를 advisor/hug_admin/system_admin이 직접 호출 가능. 이 차이를 모르고 YAML만 보고 타입을 만들면 반드시 어긋난다.

**`.dc.html` 목업은 코드로 재사용하지 않는다. 레이아웃/카피/흐름 참고 자료로만 쓴다.** 이 파일들은 `support.js`라는 자체 템플릿 런타임(`sc-if`/`sc-for`/`{{ }}` 바인딩) 위에서 동작하고, 모든 데이터가 하드코딩된 mock이며 실제 API 호출이 없다. 역할별로 파일이 분리돼 있고(로그인 기반 라우팅 없음), 화면 전환도 실제 URL 라우팅이 아니라 한 페이지 안에서의 상태 토글이다. 이 파일을 열어서 화면 구조·문구·인터랙션 순서를 참고해 Next.js/shadcn 코드로 새로 작성하되, 그대로 복사하지 않는다.
예외적으로 TEN-02(외부 API 조회 진행 화면)는 목업의 단일 progress bar 구조를 따르지 말 것 — 실제로는 5개 외부 API(도로명주소/실거래가/건축물대장/사업자등록/DART)가 각각 성공/실패/mock 상태를 가지므로, 개별 상태를 보여주는 구조로 새로 설계한다(UX원칙 10.2절 근거).

**색상/간격 토큰은 `웹사이트 UI 디자인 요청/ds/styles.css`에 정의된 값을 그대로 Tailwind theme에 이식한다.** 임의로 색을 바꾸지 않는다. `--color-accent`, `--color-accent-2`, `--color-neutral-*`, `--space-*` 등을 `tailwind.config.ts`의 `theme.extend`에 매핑하고, shadcn 컴포넌트의 semantic 토큰(danger/warning/success 등, UX원칙 10.1절)으로 연결한다.

**위험/예측 결과 문구는 개발설계보고서 12.4절 계승 원칙(UX원칙 10.4절)을 따른다.** 블록체인 상태는 Pending/Confirmed/Failed 3단계로만 표시하고 "법적 효력이 있다"는 문구 금지. ML 결과에 ML개발가이드 부록 F의 금지 표현("실제 사고확률" 등) 사용 금지. 위험 카드는 점수보다 근거·다음행동을 먼저 배치.

## 2. 기술 스택 (Frontend_UIUX_명세서 0.4절 그대로)

Next.js(App Router) · TypeScript strict · TailwindCSS(유틸리티 클래스만) · shadcn/ui(Radix 기반) · React Query(서버 상태) · Zustand(클라이언트 상태) · React Hook Form + Zod(폼/검증) · Lucide Icons · Framer Motion(전환 애니메이션) · Recharts(HUG 대시보드 차트)

## 3. 백엔드 연동 방식

- 개발 서버: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload` (Swagger: `http://localhost:8000/docs`, OpenAPI JSON: `http://localhost:8000/openapi.json`)
- `.env`의 `CORS_ALLOW_ORIGINS`에 프론트 개발 서버 origin(`http://localhost:3000`)이 등록돼 있는지 먼저 확인하고, 없으면 backend 쪽에 추가를 요청할 것(직접 backend 코드를 함부로 고치지 말고 필요하면 알려줄 것).
- 데모 계정: `tenant01/landlord01/advisor01/hugadmin01/sysadmin01@example.com`, 공통 비밀번호 `P@ssw0rd!` (`backend/scripts/seed_demo_users.py`로 시드됨).
- API 타입은 가능하면 `openapi.json`을 기준으로 자동 생성하는 도구(`openapi-typescript` 등)를 검토하되, 위 1절의 5가지 차이를 실제로 반영하고 있는지 생성 후 반드시 수동 대조할 것.

## 4. 화면-목업 대응표 (참고용, 코드 재사용 아님)

| 목업 파일 | 대응 화면 (Frontend_UIUX_명세서 5장) |
|---|---|
| `Tenant-Web-Interactive.dc.html`, `Tenant-Mobile-Interactive.dc.html` | TEN-00~07 (홈, 주소·계약입력, API조회, 위험진단결과, 증빙·검증, 타임라인, D-90, 사고접수) |
| `Landlord-Interactive.dc.html` | LAND-01~03 (증빙요청 확인·제출, 검증상태 확인, 반환계획 제출) |
| `Advisor-Interactive.dc.html` | ADV-00~03 (상담큐, 상담상세+RAG근거, 증빙검토, 전문가이관) |
| `HUG-Interactive.dc.html` | HUG-01~04 (채권관리 대시보드, 사건상세, 유사사건비교, 법인집단위험) |

## 5. 개발 순서 (Frontend_UIUX_명세서 15장 + 백엔드 현재 구현 상태 반영)

1. **공통 골격** — Layout(Header/Sidebar/Toast/Modal), Login(AUTH-01, 세션/역할 분기), RoleGuard 미들웨어. 이 부분은 이후 모든 화면이 의존하므로 가장 먼저, 가장 꼼꼼히.
2. **실제 백엔드가 있는 화면부터** — TEN-01~07, LAND-01~03. Mock 없이 바로 실제 API 연결. TEN-02는 위 1절 예외 규칙대로 개별 API 상태 구조로 설계.
3. **백엔드가 아직 없는 화면은 MSW로** — ADV-00~03, HUG-01~04, ADM-00~03은 대응하는 백엔드 라우터가 아직 없다(`/counsel-queue`, `/hug/dashboard`, `/incidents`, `/notifications`, `/admin/*`, `/ml/*` 등 미구현). Mock Service Worker로 화면 뼈대만 먼저 만들어두고, 백엔드가 채워지면 `services/` 계층의 엔드포인트만 교체.
4. **화면 완성 시마다 즉시 DoD 검증** — 아래 6절 기준 통과 여부 확인 후 다음 화면으로.

## 6. Definition of Done (Frontend_UIUX_명세서 17장)

화면 하나가 완료되려면 다음 5개를 모두 충족해야 한다: (1) 정의된 API가 실제 또는 Mock 응답과 연결됨, (2) Loading/Success/Partial/Error/Empty/Unauthorized/NotFound/Timeout/Mock 9개 상태 중 해당 화면에 적용되는 상태가 모두 UI로 구현됨, (3) Desktop 완전 동작 + 지원 대상은 Tablet/Mobile도 레이아웃 안 깨짐, (4) 키보드 전용 조작 가능 + 주요 상태 배지에 대비/텍스트 대체 수단 있음, (5) RiskBadge/StatusChip/BlockchainBadge/MockBadge가 화면 간 동일한 색상 규칙으로 표시됨.

## 7. 진행 방식 요청

- 큰 단위 작업(스캐폴딩, 공통 골격, 화면 그룹 단위) 전에는 먼저 계획을 제시하고 확인받은 뒤 진행할 것.
- 화면 하나 완료할 때마다 6절 DoD 기준 충족 여부를 짧게 보고할 것.
- 위 1절의 "절대 원칙"과 어긋나는 선택을 해야 하는 상황이 생기면(예: 목업 코드 일부를 그대로 쓰고 싶은 유혹이 드는 경우, YAML과 실제 코드가 또 다른 경우) 임의로 판단하지 말고 먼저 알릴 것.
