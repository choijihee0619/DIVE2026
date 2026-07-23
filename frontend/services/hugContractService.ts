import { apiClient } from "@/services/apiClient";
import { withModeFallback, type HugDataMode } from "@/services/hugDataMode";
import type {
  AccidentPrediction,
  ContractPreventionData,
  HugContractDetail,
  HugContractListData,
  PredictionRefreshBatchResult,
  PreventionSweepResult,
  PreventiveAction,
} from "@/types/hugContract";

export interface HugContractListParams {
  page?: number;
  size?: number;
  contract_status?: string;
  prediction_status?: string;
  min_risk_percentile?: number;
  prevention_status?: string;
  checkpoint?: string;
  region?: string;
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const query = Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");
  return query ? `?${query}` : "";
}

/** GET /hug/contracts — 사고접수 전 계약 목록·상세·예측·예방 액션. */
export const hugContractService = {
  list: (params: HugContractListParams = {}, mode: HugDataMode = "LIVE") =>
    apiClient.get<HugContractListData>(
      `/hug/contracts${toQuery({ ...params, data_mode: mode })}`,
    ),

  /** LIVE 업무대장이 비어 있으면 별도 업무대장으로 자동 폴백해 목록을 조회한다. */
  listWithFallback: (params: HugContractListParams = {}) =>
    withModeFallback(
      (mode) => hugContractService.list(params, mode),
      (data) => data.pagination.total_elements === 0,
    ),

  get: (contractId: string) =>
    apiClient.get<HugContractDetail>(`/hug/contracts/${contractId}`),

  latestPrediction: (contractId: string) =>
    apiClient.get<AccidentPrediction>(`/hug/contracts/${contractId}/prediction`),

  refreshPrediction: (contractId: string) =>
    apiClient.post<AccidentPrediction>(`/hug/contracts/${contractId}/prediction/refresh`),

  refreshPredictions: (mode: HugDataMode, contractIds?: string[]) =>
    apiClient.post<PredictionRefreshBatchResult>("/hug/contracts/predictions/refresh", {
      contract_ids: contractIds ?? null,
      data_mode: mode,
    }),

  prevention: (contractId: string) =>
    apiClient.get<ContractPreventionData>(`/hug/contracts/${contractId}/prevention`),

  createAction: (
    contractId: string,
    payload: {
      action_type: string;
      target_role: "tenant" | "landlord" | "hug_admin";
      due_at?: string;
      note?: string;
    },
  ) => apiClient.post<PreventiveAction>(`/hug/contracts/${contractId}/preventive-actions`, payload),

  updateAction: (actionId: string, payload: { status: string; note?: string }) =>
    apiClient.patch<PreventiveAction>(`/preventive-actions/${actionId}`, payload),

  sweep: (mode: HugDataMode) =>
    apiClient.post<PreventionSweepResult>("/hug/contracts/prevention/sweep", { data_mode: mode }),
};
