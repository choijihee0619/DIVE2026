import { apiClient } from "@/services/apiClient";
import type {
  ClaimEvent,
  HugIncidentDetail,
  HugIncidentListData,
  PerformanceClaimDetail,
} from "@/types/performanceClaim";

export interface HugIncidentListParams {
  page?: number;
  size?: number;
  status?: string;
  incident_type?: string;
  stage?: string;
  sla_status?: string;
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");
  return query ? `?${query}` : "";
}

/** 사고통지 큐(GET /hug/incidents) + 이행청구 원장(performance-claims) 업무 액션. */
export const performanceClaimService = {
  listIncidents: (params: HugIncidentListParams = {}) =>
    apiClient.get<HugIncidentListData>(`/hug/incidents${toQuery({ size: 100, ...params })}`),

  getIncident: (incidentId: string) =>
    apiClient.get<HugIncidentDetail>(`/hug/incidents/${incidentId}`),

  createClaim: (
    incidentId: string,
    payload: {
      claim_amount: number;
      official_accident_type?: string;
      workflow_type?: string;
    },
  ) => apiClient.post<PerformanceClaimDetail>(`/hug/incidents/${incidentId}/claims`, payload),

  getClaim: (claimId: string) =>
    apiClient.get<PerformanceClaimDetail>(`/performance-claims/${claimId}`),

  listEvents: (claimId: string) =>
    apiClient.get<{ items: ClaimEvent[]; total: number }>(`/performance-claims/${claimId}/events`),

  requestDocuments: (
    claimId: string,
    documents: { document_type: string; reason: string; due_at?: string; required?: boolean }[],
  ) =>
    apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/documents/request`, {
      documents,
    }),

  decideDocument: (
    claimId: string,
    documentId: string,
    payload: { decision: "VERIFY" | "REJECT" | "WAIVE"; reason: string },
  ) =>
    apiClient.post<PerformanceClaimDetail>(
      `/performance-claims/${claimId}/documents/${documentId}/decision`,
      payload,
    ),

  /** 청구 서류 제출 — 당사자(청구인) 허용(§20.5 P3). 해시는 클라이언트에서 SHA-256 산출. */
  submitDocument: (
    claimId: string,
    documentId: string,
    payload: { file_name: string; document_hash: string; object_uri?: string | null; note?: string | null },
  ) =>
    apiClient.post<PerformanceClaimDetail>(
      `/performance-claims/${claimId}/documents/${documentId}/submit`,
      payload,
    ),

  startReview: (claimId: string, note?: string) =>
    apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/review/start`, { note }),

  decide: (
    claimId: string,
    payload: {
      decision: "APPROVE" | "ON_HOLD" | "REJECT";
      approved_amount?: number;
      reason: string;
      checklist_completed?: boolean;
    },
  ) => apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/decision`, payload),

  handover: (
    claimId: string,
    payload: {
      action: "SCHEDULE" | "COMPLETE";
      moveout_due_at?: string;
      settlement_confirmed?: boolean;
      reason: string;
    },
  ) => apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/handover`, payload),

  paySubrogation: (
    claimId: string,
    payload: { payment_reference: string; paid_amount: number; paid_at: string; reason: string },
  ) =>
    apiClient.post<PerformanceClaimDetail>(
      `/performance-claims/${claimId}/subrogation-payment`,
      payload,
    ),

  registerRecoveryClaim: (
    claimId: string,
    payload: {
      claim_type: string;
      principal: number;
      incurred_amount: number;
      incurred_date: string;
      product_name?: string;
    },
  ) =>
    apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/recovery-claims`, payload),

  transfer: (
    claimId: string,
    payload: { assignee_user_id: string; next_action: string; reason: string },
  ) => apiClient.post<PerformanceClaimDetail>(`/performance-claims/${claimId}/transfer`, payload),
};
