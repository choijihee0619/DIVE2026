import { apiClient } from "@/services/apiClient";
import type { PropertyListData, Property, RegistrySnapshot } from "@/types/property";

interface RegistryRefreshParams {
  deposit?: number;
  dong?: string;
  ho?: string;
}

export const propertyService = {
  list: (size = 100) => apiClient.get<PropertyListData>(`/properties?page=1&size=${size}`),
  get: (propertyId: string) => apiClient.get<Property>(`/properties/${propertyId}`),
  /** POST /properties/{id}/registry/refresh — CODEF 등기부 실조회(동·호수 지정 시 매물 주소에 저장). */
  refreshRegistry: (propertyId: string, { deposit, dong, ho }: RegistryRefreshParams = {}) => {
    const query = new URLSearchParams();
    if (deposit && deposit > 0) query.set("deposit", String(deposit));
    if (dong?.trim()) query.set("dong", dong.trim());
    if (ho?.trim()) query.set("ho", ho.trim());
    const qs = query.toString();
    return apiClient.post<RegistrySnapshot>(
      `/properties/${propertyId}/registry/refresh${qs ? `?${qs}` : ""}`,
    );
  },
  /** GET /properties/{id}/registry/latest — 최신 등기부 스냅샷(원문 포함). 없으면 404. */
  latestRegistry: (propertyId: string) =>
    apiClient.get<RegistrySnapshot>(`/properties/${propertyId}/registry/latest`),
};
