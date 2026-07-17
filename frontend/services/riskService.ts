import { apiClient } from "@/services/apiClient";
import type { RiskAssessment, RiskDiagnoseRequest } from "@/types/risk";

export const riskService = {
  /** POST /risk/diagnose — 규칙 기반 위험진단(tenant 전용, 즉시 결과 반환). */
  diagnose: (payload: RiskDiagnoseRequest) => apiClient.post<RiskAssessment>("/risk/diagnose", payload),
  /** GET /risk/{case_id} — case_id 또는 risk_assessment_id로 조회. */
  get: (caseId: string) => apiClient.get<RiskAssessment>(`/risk/${caseId}`),
};
