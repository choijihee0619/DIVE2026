/** backend/app/schemas/rag.py 그대로. */

/** 답변 화면용 참고 사례 — 내부 저장명 없이 LLM이 질문 맥락으로 변환한 요약만 담긴다. */
export interface RagSource {
  label: string;
  topic: string | null;
  consultation_stage: string | null;
  region: string | null;
  summary: string;
  /** PII 마스킹된 상담 원문(팝업 확인용). */
  transcript: string;
  score: number | null;
}

export interface RagAnswerRequest {
  topic: string;
  question: string;
  region?: string;
  consultation_stage?: "계약전" | "계약중" | "사고후";
  top_k?: number;
}

export interface RagAnswerData {
  answer: string;
  is_mock: boolean;
  sources: RagSource[];
  disclaimer: string;
  rag_search_log_id: string;
}
