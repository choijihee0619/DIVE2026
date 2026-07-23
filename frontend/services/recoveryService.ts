import { apiClient } from "@/services/apiClient";
import { withModeFallback, type HugDataMode } from "@/services/hugDataMode";
import type {
  RecoveryClaimDetail,
  RecoveryClaimListData,
  RecoveryPredictionRecord,
  RecoverySummary,
} from "@/types/recovery";

export interface RecoveryClaimListParams {
  page?: number;
  size?: number;
  lifecycle?: "active" | "closed" | "all";
  recovery_stage?: string;
  claim_type?: string;
  collection_route?: string;
  sort_by?: "updated_at" | "created_at" | "priority_score" | "balance" | "due_at";
  descending?: boolean;
}

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");
  return query ? `?${query}` : "";
}

/** 간단한 멱등키 생성 — 채권 ID + 액션 + 시각. */
export function idempotencyKey(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** GET·POST /hug/recovery/* — 등록채권 KPI·목록·상세·원장·사건·예측·종결. */
export const recoveryService = {
  summary: (mode: HugDataMode = "LIVE") =>
    apiClient.get<RecoverySummary>(`/hug/recovery/summary?data_mode=${mode}`),

  /** LIVE 업무대장이 비어 있으면 별도 업무대장으로 자동 폴백해 KPI를 조회한다. */
  summaryWithFallback: () =>
    withModeFallback(
      (mode) => recoveryService.summary(mode),
      (data) => data.managed_claim_count + data.closed_claim_count === 0,
    ),

  listClaims: (params: RecoveryClaimListParams = {}, mode: HugDataMode = "LIVE") =>
    apiClient.get<RecoveryClaimListData>(
      `/hug/recovery/claims${toQuery({ size: 50, ...params, data_mode: mode })}`,
    ),

  listClaimsWithFallback: (params: RecoveryClaimListParams = {}) =>
    withModeFallback(
      (mode) => recoveryService.listClaims(params, mode),
      (data) => data.pagination.total_elements === 0,
    ),

  detail: (claimId: string) =>
    apiClient.get<RecoveryClaimDetail>(`/hug/recovery/claims/${claimId}`),

  addEvent: (
    claimId: string,
    payload: { event_type: string; status_axis?: string; after?: string; note?: string },
  ) =>
    apiClient.post(`/hug/recovery/claims/${claimId}/events`, {
      ...payload,
      idempotency_key: idempotencyKey(`ev-${claimId}`),
    }),

  addLedgerEntry: (
    claimId: string,
    payload: {
      entry_type: string;
      amount_won: number;
      allocations?: Record<string, number>;
      note?: string;
    },
  ) =>
    apiClient.post(`/hug/recovery/claims/${claimId}/ledger-entries`, {
      allocations: {},
      ...payload,
      idempotency_key: idempotencyKey(`lg-${claimId}`),
    }),

  predict: (claimId: string, payload: { auction_filed_date?: string; assumption_reason?: string } = {}) =>
    apiClient.post<RecoveryPredictionRecord>(`/hug/recovery/claims/${claimId}/predict`, {
      ...payload,
      idempotency_key: idempotencyKey(`pr-${claimId}`),
    }),

  predictions: (claimId: string) =>
    apiClient.get<{ items: RecoveryPredictionRecord[]; total: number }>(
      `/hug/recovery/claims/${claimId}/predictions`,
    ),

  close: (claimId: string, payload: { reason: string; note?: string }) =>
    apiClient.post(`/hug/recovery/claims/${claimId}/close`, {
      ...payload,
      confirm: true,
      idempotency_key: idempotencyKey(`cl-${claimId}`),
    }),
};
