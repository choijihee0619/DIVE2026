/**
 * GET /hug/dashboard/* 응답 타입. 백엔드 hug_dashboard 라우터 실응답(260721 확인) 기준.
 * 모든 응답의 basis에 "합성데이터 기준 시뮬레이션" 문구가 담겨 화면 라벨로 노출한다.
 */

export type RecoveryGrade = "HIGH" | "MED" | "LOW";

export interface HugSummary {
  portfolio_count: number;
  claimed_total_won: number;
  expected_recovery_total_won: number;
  median_pred_recovery_ratio: number;
  median_pred_days: number;
  grade_counts: Record<RecoveryGrade, number>;
  by_product: { product_name: string; cnt: number; claimed_sum_won: number }[];
  priority_weights: Record<string, number>;
  basis: string;
}

export interface PriorityBond {
  source_row_id: string;
  product_name: string;
  claim_type: string;
  claimed_amount: number;
  pred_recovery_ratio: number;
  pred_recovery_grade: RecoveryGrade;
  pred_days_to_dividend: number;
  expected_recovery_won: number;
  priority_score: number;
  /** "발생금액=4.8억(+0.129); 채권구분=구상채권(-0.052); ..." 형태 문자열. */
  top_factors: string;
  basis: string;
}

export interface PriorityListData {
  items: PriorityBond[];
  pagination: { page: number; size: number; total: number; total_pages: number };
  basis: string;
}

export interface RegionRiskRow {
  sido: string;
  accident_cnt: number;
  accident_amt_won: number;
  accident_rate_pct: number;
}

/** region-risk 응답의 시군구 상세 행(코로플레스 조인 키 adm_cd 포함, §19.5). */
export interface RegionSigunguRow {
  adm_cd: string;
  sido: string;
  sigungu: string;
  accident_cnt: number;
  accident_amt_won: number;
  accident_rate_pct: number;
}

export interface RegionRiskData {
  sido_summary: RegionRiskRow[];
  sigungu: RegionSigunguRow[];
  basis?: string;
}

export interface IssuancePoint {
  yyyymm: string;
  issue_cnt: number;
  /** 원본 집계 버그로 문자열 연결이 깨져 있음 — 사용 금지, issue_cnt만 사용. */
  issue_amt_won: string;
}

export interface IssuanceData {
  series: IssuancePoint[];
}

export interface VictimRow {
  year: number;
  sido_short: string;
  sigungu: string;
  victim_house_cnt: number;
}

export interface VictimsData {
  items: VictimRow[];
}

/* ── 통합 대시보드 overview (260723 백엔드) ───────────────────── */

/** GET /hug/dashboard/overview — 업무대장 KPI + 파이프라인 단계별 건수. */
export interface OperationalRegister {
  guarantee_contract_count: number;
  pre_incident_active_contract_count: number;
  high_risk_action_needed_contract_count: number;
  performance_claim_in_progress_count: number;
  /** RecoveryService.summary 병합 필드 */
  managed_claim_count: number;
  closed_claim_count: number;
  principal_balance_won: number;
  subrogation_principal_balance_won: number;
  total_balance_won: number;
  expected_recovery_total_won: number;
  weighted_expected_recovery_ratio: number | null;
  predicted_balance_coverage_won: number;
  stage_counts: Record<string, number>;
  grade_counts: Record<string, number>;
  pipeline_counts: {
    prevention_action_needed: number;
    accident_notified: number;
    performance_review: number;
    handover_waiting: number;
    subrogation_paid: number;
    recovery_active: number;
  };
  selected_data_mode: "LIVE" | "DEMO";
  selected_document_count: number;
  data_mode_breakdown: { DEMO: number; LIVE: number };
}

export interface HugOverview {
  operational_register: OperationalRegister;
  reference_portfolio: Partial<HugSummary> & { status: "AVAILABLE" | "UNAVAILABLE" };
  public_aggregate: Record<string, unknown>;
}

/** GET /hug/dashboard/issuance-incident-trend — 연도 단위 발급·사고 결합 시계열. */
export interface IssuanceIncidentPoint {
  year: number;
  issue_cnt: number;
  issue_amt_won: number;
  accident_cnt: number | null;
  accident_amt_won: number | null;
  accident_rate_pct: number | null;
}

export interface IssuanceIncidentTrend {
  status: string;
  series: IssuanceIncidentPoint[];
}
