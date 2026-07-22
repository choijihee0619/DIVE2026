/**
 * 중앙 용어 사전 (README §19.7) — 화면에 노출되는 전문용어의 단일 소스.
 * `<Term>`(점선 밑줄 팝오버)·`<TermHelp>`(ⓘ 아이콘)가 이 사전을 공유한다.
 * short = 호버 1~2줄 요약, long = 클릭/상세 설명(선택).
 */

export type GlossaryAudience = "tenant" | "landlord" | "advisor" | "hug" | "common";

export interface GlossaryEntry {
  /** 화면 표기 용어 */
  term: string;
  /** 호버 1~2줄 요약 */
  short: string;
  /** 상세 설명(선택) — 팝오버 하단에 구분선과 함께 표시 */
  long?: string;
  /** 우선 노출 대상 역할 */
  audience: GlossaryAudience[];
}

export const GLOSSARY = {
  /* ── 임차인 우선 ─────────────────────────────── */
  subrogation: {
    term: "대위변제",
    short: "임대인이 보증금을 못 돌려줄 때 HUG가 임차인에게 먼저 대신 지급하는 것.",
    long: "지급 후 HUG는 그 금액을 임대인에게 청구(구상)합니다. HUG 화면의 '채권'은 대부분 이 대위변제금을 돌려받을 권리입니다.",
    audience: ["tenant", "hug"],
  },
  mortgage: {
    term: "근저당",
    short: "집을 담보로 잡힌 빚이 등기부에 표시된 것. 내 보증금보다 먼저 갚아야 할 돈일 수 있습니다.",
    long: "근저당 금액과 내 보증금의 합이 집값에 가까울수록 보증금을 떼일 위험이 커집니다. 계약 전 말소(삭제) 여부를 확인하는 것이 안전합니다.",
    audience: ["tenant", "common"],
  },
  fixedDate: {
    term: "확정일자",
    short: "계약서에 공적 기관이 날짜를 확인해 주는 절차. 보증금을 돌려받는 순번을 확보합니다.",
    long: "전입신고와 함께 갖추면 우선변제권이 생겨, 집이 경매로 넘어가도 후순위 채권자보다 먼저 배당받을 수 있습니다.",
    audience: ["tenant"],
  },
  jeonseGuarantee: {
    term: "전세보증금반환보증",
    short: "임대인이 보증금을 돌려주지 않으면 HUG가 대신 돌려주는 보증 상품.",
    audience: ["tenant", "landlord"],
  },
  seniorClaims: {
    term: "선순위",
    short: "내 보증금보다 먼저 변제받는 권리(근저당 대출, 체납 세금 등). 많을수록 보증금 회수가 위험합니다.",
    audience: ["tenant"],
  },
  priorityRepayment: {
    term: "우선변제권",
    short: "전입신고 + 확정일자를 갖춘 임차인이 후순위 채권자보다 먼저 보증금을 배당받는 권리.",
    audience: ["tenant"],
  },
  leaseRegistration: {
    term: "임차권등기",
    short: "이사를 가더라도 대항력·우선변제권을 유지하기 위해 법원에 신청하는 등기.",
    audience: ["tenant"],
  },
  moveInReport: {
    term: "전입신고",
    short: "이사 후 주민센터에 거주 사실을 신고하는 것. 대항력이 생기는 출발점입니다.",
    long: "전입신고(대항력) + 확정일자(우선변제권)를 함께 갖춰야 집이 경매로 넘어가도 보증금을 지킬 수 있습니다.",
    audience: ["tenant"],
  },
  opposingPower: {
    term: "대항력",
    short: "집주인이 바뀌어도 계약 기간 동안 거주하며 보증금을 요구할 수 있는 힘. 전입신고 + 실거주로 생깁니다.",
    audience: ["tenant"],
  },
  seizure: {
    term: "압류·가압류",
    short: "법원·세무서 등이 재산 처분을 금지해 둔 상태. 등기부에 있으면 보증금 회수에 큰 위험 신호입니다.",
    audience: ["tenant", "common"],
  },
  threePartyView: {
    term: "3자 공동 열람",
    short: "임차인·임대인·HUG가 각자 화면에서 열어도 같은 원본(계약 내용·변경 이력·증빙 상태)을 보는 방식.",
    long: "동시 접속 없이도 세 주체가 항상 같은 정보를 보므로, 변경·증빙을 둘러싼 오해와 분쟁을 줄입니다. 모든 변경은 변경 이력에 기록됩니다.",
    audience: ["common"],
  },

  /* ── 임대인 우선 ─────────────────────────────── */
  guaranteeAccident: {
    term: "보증사고",
    short: "계약이 끝났는데도 임차인이 보증금을 돌려받지 못한 상황.",
    audience: ["landlord", "hug"],
  },
  guaranteeEnrollment: {
    term: "보증가입",
    short: "전세보증금반환보증에 가입하는 것. 임차인 불안을 줄이고 계약 신뢰도를 높입니다.",
    audience: ["landlord"],
  },
  indemnityRight: {
    term: "구상권",
    short: "HUG가 임차인에게 대신 지급한 보증금을 임대인에게 청구할 권리. 그 대상 금액이 구상채권입니다.",
    audience: ["landlord", "hug"],
  },

  /* ── HUG 우선 ────────────────────────────────── */
  recoveryRate: {
    term: "회수율",
    short: "대신 지급한(대위변제) 금액 중 되받을 것으로 예상되는 비율.",
    audience: ["hug"],
  },
  priorityScore: {
    term: "회수 우선순위 점수",
    short: "예상 회수율과 회수 속도를 가중 합산해 0~100으로 만든 점수. 높을수록 먼저 착수할 채권입니다.",
    long: "기본 가중치는 회수율 60% · 속도 40%입니다.",
    audience: ["hug"],
  },
  recoveryGrade: {
    term: "회수등급",
    short: "예상 회수율을 HIGH(높음) · MED(보통) · LOW(낮음) 3단계로 나눈 등급.",
    audience: ["hug"],
  },
  dividend: {
    term: "배당",
    short: "경매·공매로 판 돈을 채권자 순위대로 나눠주는 절차. HUG가 실제로 돈을 회수하는 시점입니다.",
    audience: ["hug"],
  },
  daysToDividend: {
    term: "예상 소요일",
    short: "배당(실제 회수)까지 걸릴 것으로 예측되는 일수.",
    audience: ["hug"],
  },
  bond: {
    term: "채권",
    short: "받을 권리가 있는 돈. 여기서는 HUG가 대위변제 후 임대인에게 청구하는 회수 대상 금액입니다.",
    audience: ["hug"],
  },
  auction: {
    term: "경공매",
    short: "법원 경매와 공공기관 공매. 담보 부동산을 강제 매각해 채권을 회수하는 절차.",
    audience: ["hug", "tenant"],
  },
  lawsuitAdvance: {
    term: "소송대지급금",
    short: "임차인이 소송으로 승소해 HUG가 대신 지급한 금액에 대한 채권 구분.",
    long: "일반 대위변제(구상채권)와 달리 판결을 거쳐 지급된 건이라 회수 절차·양상이 다릅니다.",
    audience: ["hug"],
  },
  claimIndemnity: {
    term: "구상채권",
    short: "HUG가 임차인에게 대신 지급(대위변제)한 보증금을 임대인에게 청구하는 채권 — 회수 채권의 기본 형태.",
    audience: ["hug"],
  },
  claimIndemnityNew: {
    term: "구상채권(신상품)",
    short: "전세보증금반환보증 등 새 보증상품에서 발생한 구상채권 구분.",
    long: "기존 구상채권과 발생 시기·회수 양상이 달라 별도 구분으로 관리하며, 예측 모델도 다른 회수 패턴을 학습합니다.",
    audience: ["hug"],
  },
  shap: {
    term: "요인 분석",
    short: "예측이 왜 그렇게 나왔는지, 입력값 하나하나가 결과를 올렸는지(▲) 내렸는지(▼) 수치로 보여주는 설명 기법.",
    long: "게임이론의 섀플리 값에 기반한 SHAP 기법을 사용합니다. 화면에는 회수율 예측에 가장 크게 기여한 요인 Top 3를 표시합니다.",
    audience: ["hug"],
  },
  recoveryModel: {
    term: "회수 예측 모델",
    short: "과거 채권 회수 실적을 학습해 예상 회수율·소요일을 자동 산정하는 머신러닝 모델.",
    long: "트리 기반 LightGBM 회귀 모델 2종(회수율·배당 소요일)을 실시간 호출하며, 판단 근거는 SHAP 요인 분석으로 함께 제공합니다.",
    audience: ["hug"],
  },

  /* ── 공통·상담(아이엔) ───────────────────────── */
  anchoring: {
    term: "블록체인 앵커링",
    short: "서류의 디지털 지문(SHA-256 해시)을 블록체인에 기록해 위·변조를 검증할 수 있게 하는 것.",
    long: "원본 파일은 올리지 않고 지문만 기록하므로 개인정보 노출 없이 무결성을 증명합니다.",
    audience: ["common"],
  },
  ragEvidence: {
    term: "RAG 근거",
    short: "AI 답변이 어떤 법령·공식자료 조각에서 나왔는지 보여주는 출처.",
    long: "법령·안심전세포털 공식자료·FAQ 1,230개 조각을 검색해 답변과 함께 근거를 제시합니다.",
    audience: ["advisor"],
  },
  disputeType: {
    term: "분쟁유형",
    short: "상담 내용을 보증금 미반환·근저당 등 분쟁 카테고리로 AI가 자동 분류한 결과.",
    long: "비식별 상담 데이터를 학습한 분류 모델이 판별하며, 상담사 큐 라우팅과 유사사례 검색에 사용됩니다.",
    audience: ["advisor"],
  },
  counselStage: {
    term: "진행단계",
    short: "상담이 어느 국면인지(초기 문의·검토·분쟁 진행 등) AI가 자동 분류한 결과. 응대 우선순위에 활용합니다.",
    audience: ["advisor"],
  },
} as const satisfies Record<string, GlossaryEntry>;

export type GlossaryKey = keyof typeof GLOSSARY;

/** HUG 채권구분 원본값 → 용어 키 (테이블 셀·선택 패널에서 값 자체에 툴팁을 달 때 사용). */
export const CLAIM_TYPE_TERM_KEY: Record<string, GlossaryKey> = {
  구상채권: "claimIndemnity",
  "구상채권(신상품)": "claimIndemnityNew",
  소송대지급금: "lawsuitAdvance",
};

/**
 * `<GlossaryText>` 자동 매칭 표면형 → 용어 키. 데이터 문자열(위험 요인·특약·권장 조치 등)
 * 안의 전문용어를 자동으로 `<Term>`으로 감싼다. 매칭은 긴 표면형 우선.
 * 일반 단어와 겹치기 쉬운 용어(채권·배당 등)는 오탐 방지를 위해 제외.
 */
export const AUTO_GLOSSARY_TERMS: [string, GlossaryKey][] = [
  ["전세보증금반환보증", "jeonseGuarantee"],
  ["구상채권(신상품)", "claimIndemnityNew"],
  ["소송대지급금", "lawsuitAdvance"],
  ["우선변제권", "priorityRepayment"],
  ["임차권등기", "leaseRegistration"],
  ["압류·가압류", "seizure"],
  ["확정일자", "fixedDate"],
  ["전입신고", "moveInReport"],
  ["대위변제", "subrogation"],
  ["구상채권", "claimIndemnity"],
  ["근저당권", "mortgage"],
  ["보증사고", "guaranteeAccident"],
  ["대항력", "opposingPower"],
  ["근저당", "mortgage"],
  ["선순위", "seniorClaims"],
  ["구상권", "indemnityRight"],
  ["경공매", "auction"],
];
