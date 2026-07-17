/** backend/app/schemas/risk.py 그대로(화면에서 쓰는 필드만). */

export interface RiskFactor {
  code: string;
  title: string;
  severity: "low" | "medium" | "high";
  description: string;
}

export interface RiskAssessment {
  diagnosis_id: string;
  case_id: string;
  risk_assessment_id: string;
  contract_id: string | null;
  property_id: string;
  risk_grade: string;
  risk_reasons: string[];
  resolvable_risks: string[];
  unresolvable_risks: string[];
  data_sources: string[];
  risk_score: number;
  confidence: number;
  data_completeness: number;
  risk_factors: RiskFactor[];
  positive_factors: RiskFactor[];
  missing_fields: string[];
  required_documents: string[];
  recommended_actions: string[];
  source_status: Record<string, string>;
  created_at: string;
  blockchain_tx_id: string | null;
}

export interface RiskDiagnoseRequest {
  property_id: string;
  deposit: number;
  contract_start_date: string;
  contract_end_date: string;
  landlord_type: string;
  housing_type: string;
  landlord_id?: string | null;
  contract_id?: string | null;
}
