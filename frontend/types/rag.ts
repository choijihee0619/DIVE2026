/** backend/app/schemas/rag.py 그대로. */

export interface RagChunk {
  chunk_id: string;
  source: string | null;
  topic: string | null;
  consultation_stage: string | null;
  region: string | null;
  excerpt: string;
  pii_removed: boolean;
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
  sources: RagChunk[];
  disclaimer: string;
  rag_search_log_id: string;
}
