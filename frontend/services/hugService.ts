import { apiClient } from "@/services/apiClient";
import type {
  HugOverview,
  HugSummary,
  IssuanceData,
  IssuanceIncidentTrend,
  PriorityListData,
  RegionRiskData,
  VictimsData,
} from "@/types/hug";

/** GET /hug/dashboard/* — 통합 KPI(overview) + HOUSTA 실집계 + 참조 포트폴리오. */
export const hugService = {
  overview: () => apiClient.get<HugOverview>("/hug/dashboard/overview"),
  issuanceIncidentTrend: () =>
    apiClient.get<IssuanceIncidentTrend>("/hug/dashboard/issuance-incident-trend"),
  summary: () => apiClient.get<HugSummary>("/hug/dashboard/summary"),
  priority: (size = 8, page = 1) =>
    apiClient.get<PriorityListData>(`/hug/dashboard/priority?page=${page}&size=${size}`),
  regionRisk: (sido?: string) =>
    apiClient.get<RegionRiskData>(`/hug/dashboard/region-risk${sido ? `?sido=${encodeURIComponent(sido)}` : ""}`),
  issuance: () => apiClient.get<IssuanceData>("/hug/dashboard/issuance"),
  victims: (year?: number) => apiClient.get<VictimsData>(`/hug/dashboard/victims${year ? `?year=${year}` : ""}`),
  /** §20.3 원클릭 리셋 — 기준 업무대장을 purge 후 재생성한다(MOCK_MODE 전용). */
  resetDemoData: () =>
    apiClient.post<{ template_version: string; purge_counts: Record<string, number> | null }>(
      "/hug/demo/seed",
      { use_model: true, purge: true },
    ),
};
