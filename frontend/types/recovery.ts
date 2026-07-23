/**
 * HUG 사고 후 채권관리 API 응답 타입.
 * backend/app/services/recovery_service.py 실응답(260723) 기준.
 */

import type {
  AuctionStatus,
  BalanceStatus,
  CloseReason,
  CollectionRoute,
  LegalStatus,
  RecoveryStage,
  RepaymentPlanStatus,
} from "@/lib/hug-labels";

export interface ClaimBalances {
  principal: number;
  legal_cost: number;
  delay_damage: number;
  enforcement_cost: number;
  total: number;
}

export interface RecoveryPredictionResult {
  pred_recovery_ratio: number;
  pred_recovery_grade: "HIGH" | "MED" | "LOW";
  pred_days_to_dividend: number;
  expected_recovery_on_current_balance_won: number;
  current_balance_won: number;
  priority_score: number;
  priority_rank: number;
  priority_portfolio_size: number;
  priority_components?: Record<string, number>;
  top_factors?: { label: string; value: string | number; shap: number }[];
  [key: string]: unknown;
}

/** 등록채권 예측 이력 문서 — POST predict 응답 · GET predictions 항목. */
export interface RecoveryPredictionRecord {
  _id?: string;
  recovery_claim_id: string;
  result: RecoveryPredictionResult;
  input_snapshot: Record<string, unknown>;
  model_version: string;
  prediction_status: string;
  delta_from_previous: {
    pred_recovery_ratio: number;
    pred_days_to_dividend: number;
    expected_recovery_on_current_balance_won: number;
    priority_score: number;
  } | null;
  predicted_by: string;
  predicted_at: string;
}

/** GET /hug/recovery/claims 목록 행 · 상세 claim 공통. */
export interface RecoveryClaim {
  recovery_claim_id: string;
  performance_claim_id?: string;
  contract_id?: string;
  claim_type: string;
  claim_type_label: string;
  product_name: string;
  product_name_label: string;
  principal?: number;
  incurred_amount?: number;
  incurred_date?: string;
  balances: ClaimBalances;
  balance: number;
  recovery_stage?: RecoveryStage;
  collection_route?: CollectionRoute;
  legal_status?: LegalStatus;
  auction_status?: AuctionStatus;
  repayment_plan_status?: RepaymentPlanStatus;
  balance_status?: BalanceStatus;
  axis_status?: Partial<{
    recovery_stage: RecoveryStage;
    collection_route: CollectionRoute;
    legal_status: LegalStatus;
    auction_status: AuctionStatus;
    repayment_plan_status: RepaymentPlanStatus;
    balance_status: BalanceStatus;
  }>;
  latest_prediction?: RecoveryPredictionResult | null;
  pred_recovery_ratio?: number;
  pred_recovery_grade?: "HIGH" | "MED" | "LOW";
  pred_days_to_dividend?: number;
  expected_recovery_won?: number;
  priority_score?: number;
  priority_rank?: number;
  priority_portfolio_size?: number;
  priority_components?: Record<string, number>;
  auction_filed_date?: string | null;
  assignee_user_id?: string | null;
  is_closed: boolean;
  closure?: { reason: CloseReason; note?: string | null; closed_at?: string } | null;
  closed_at?: string | null;
  version?: number;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface RecoverySummary {
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
  data_mode_filter: "LIVE" | "DEMO";
  data_mode_breakdown: { DEMO: number; LIVE: number };
}

export interface RecoveryClaimListData {
  items: RecoveryClaim[];
  pagination: { page: number; size: number; total_elements: number; total_pages: number };
  data_mode_filter: "LIVE" | "DEMO";
}

export interface RecoveryEvent {
  _id?: string;
  recovery_claim_id: string;
  event_type: string;
  status_axis: string | null;
  before?: string | null;
  after: string | null;
  note: string | null;
  actor_role?: string;
  occurred_at: string;
}

export interface RecoveryLedgerEntry {
  _id?: string;
  recovery_claim_id: string;
  entry_type: string;
  amount_won: number;
  allocations: Record<string, number>;
  note: string | null;
  sequence?: number;
  balance_after?: ClaimBalances;
  occurred_at: string;
}

export interface LegalCase {
  legal_case_id: string;
  recovery_claim_id: string;
  case_type: string;
  court: string;
  case_number: string;
  filing_date: string;
  status: string;
  claimed_amount_won: number;
  legal_cost_won: number;
  judgment_amount_won: number | null;
  judgment: string | null;
  note: string | null;
  version?: number;
}

export interface AuctionCase {
  auction_case_id: string;
  recovery_claim_id: string;
  auction_type: string;
  case_number: string;
  filing_date: string;
  status: string;
  appraisal_won: number;
  sale_date: string | null;
  dividend_date: string | null;
  dividend_amount_won: number;
  note: string | null;
  version?: number;
}

export interface RecoveryClaimDetail {
  claim: RecoveryClaim;
  events: RecoveryEvent[];
  ledger_entries: RecoveryLedgerEntry[];
  predictions: RecoveryPredictionRecord[];
  legal_cases: LegalCase[];
  auction_cases: AuctionCase[];
}
