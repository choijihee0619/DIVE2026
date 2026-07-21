import { apiClient } from "@/services/apiClient";
import type {
  CounselQueueItem,
  CounselQueueListData,
  CounselSource,
  CounselStatus,
} from "@/types/counsel";

/** /counsel-queue — 상담 요청 접수(임차인·임대인)와 큐 처리(상담사 이상). 접수 시 자동분류 포함. */
export const counselService = {
  create: (payload: { text: string; source?: CounselSource; contract_id?: string | null; region_sido?: string | null }) =>
    apiClient.post<CounselQueueItem>("/counsel-queue", payload),
  list: (params?: { priority?: "high" | "normal"; page?: number; size?: number }) => {
    const query = new URLSearchParams();
    if (params?.priority) query.set("priority", params.priority);
    query.set("page", String(params?.page ?? 1));
    query.set("size", String(params?.size ?? 50));
    return apiClient.get<CounselQueueListData>(`/counsel-queue?${query.toString()}`);
  },
  get: (counselId: string) => apiClient.get<CounselQueueItem>(`/counsel-queue/${counselId}`),
  update: (counselId: string, status: CounselStatus, answerNote?: string) =>
    apiClient.patch<CounselQueueItem>(`/counsel-queue/${counselId}`, {
      status,
      answer_note: answerNote ?? null,
    }),
};
