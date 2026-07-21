import type { RecoveryGrade } from "@/types/hug";

/** POST /ml/recovery/predict 입력(backend/app/schemas/ml.py 검증 규칙 포함). */
export const ML_PRODUCTS = ["전세보증금반환보증", "개인임대사업자임대보증금보증"] as const;
export const ML_CLAIM_TYPES = ["소송대지급금", "구상채권(신상품)", "구상채권"] as const;

export interface RecoveryPredictRequest {
  product_name: string;
  claim_type: string;
  claimed_amount: number;
  incurred_amount: number;
  auction_filed_date: string;
  incurred_date: string;
}

export interface RecoveryFactor {
  feature: string;
  label: string;
  value: string;
  shap: number;
  direction: "up" | "down";
}

export interface RecoveryPredictResult {
  pred_recovery_ratio: number;
  pred_recovery_grade: RecoveryGrade;
  pred_days_to_dividend: number;
  expected_recovery_won: number;
  priority_score: number;
  priority_weights: Record<string, number>;
  portfolio_size: number;
  top_factors: RecoveryFactor[];
  basis: string;
}

/** POST /ml/counsel/classify 응답(advisor 이상 권한). */
export interface ClassifyDimension {
  label: string;
  confidence: number;
  top3: { label: string; prob: number }[];
}

export interface CounselClassifyResult {
  dispute_type: ClassifyDimension;
  consultation_stage: ClassifyDimension;
  basis: string;
}
