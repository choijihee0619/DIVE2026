import { apiClient } from "@/services/apiClient";
import type {
  HugSummary,
  IssuanceData,
  PriorityListData,
  RegionRiskData,
  VictimsData,
} from "@/types/hug";

/** GET /hug/dashboard/* — HOUSTA 실집계 + 합성데이터 ML 시뮬레이션(HUG-01). */
export const hugService = {
  summary: () => apiClient.get<HugSummary>("/hug/dashboard/summary"),
  priority: (size = 8, page = 1) =>
    apiClient.get<PriorityListData>(`/hug/dashboard/priority?page=${page}&size=${size}`),
  regionRisk: (sido?: string) =>
    apiClient.get<RegionRiskData>(`/hug/dashboard/region-risk${sido ? `?sido=${encodeURIComponent(sido)}` : ""}`),
  issuance: () => apiClient.get<IssuanceData>("/hug/dashboard/issuance"),
  victims: (year?: number) => apiClient.get<VictimsData>(`/hug/dashboard/victims${year ? `?year=${year}` : ""}`),
};
