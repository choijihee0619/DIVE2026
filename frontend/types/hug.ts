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
