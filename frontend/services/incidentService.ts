import { apiClient } from "@/services/apiClient";
import type { Incident, IncidentCreate, IncidentListData, IncidentStatus } from "@/types/incident";

/** /incidents — 사고 접수(임차인)·큐 관리(HUG). */
export const incidentService = {
  create: (payload: IncidentCreate) => apiClient.post<Incident>("/incidents", payload),
  list: (size = 50) => apiClient.get<IncidentListData>(`/incidents?page=1&size=${size}`),
  get: (incidentId: string) => apiClient.get<Incident>(`/incidents/${incidentId}`),
  /** HUG 전용 상태 전이. */
  updateStatus: (incidentId: string, status: IncidentStatus, note?: string) =>
    apiClient.patch<Incident>(`/incidents/${incidentId}/status`, { status, note: note ?? null }),
};
