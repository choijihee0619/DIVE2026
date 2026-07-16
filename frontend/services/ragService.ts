import { apiClient } from "@/services/apiClient";
import type { RagAnswerData, RagAnswerRequest } from "@/types/rag";

export const ragService = {
  /** POST /rag/answer — 판례·상담 지식 기반 AI 답변(tenant/advisor 전용). */
  answer: (payload: RagAnswerRequest) => apiClient.post<RagAnswerData>("/rag/answer", payload),
};
