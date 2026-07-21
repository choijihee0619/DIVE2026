import type { Pagination } from "@/types/contract";

/** backend/app/schemas/counsel.py와 1:1. 상담사 큐(시안 4-1). */

export type CounselStatus = "Waiting" | "InProgress" | "Answered" | "Closed";
export type CounselSource = "chatbot_escalation" | "direct" | "incident_followup";
export type CounselPriority = "high" | "normal";

export const COUNSEL_STATUS_LABEL: Record<CounselStatus, string> = {
  Waiting: "대기",
  InProgress: "상담 중",
  Answered: "답변 완료",
  Closed: "종결",
};

export const COUNSEL_SOURCE_LABEL: Record<CounselSource, string> = {
  chatbot_escalation: "챗봇 이관",
  direct: "직접 접수",
  incident_followup: "사고 후속",
};

/** 접수 시 백엔드가 자동으로 분쟁유형·진행단계를 분류해 담아준다. */
export interface CounselClassification {
  dispute_type: string | null;
  dispute_confidence: number | null;
  consultation_stage: string | null;
  stage_confidence: number | null;
  classified: boolean;
}

export interface CounselQueueItem {
  counsel_id: string;
  requester_user_id: string;
  text: string;
  source: CounselSource;
  contract_id: string | null;
  region_sido: string | null;
  classification: CounselClassification;
  priority: CounselPriority;
  status: CounselStatus;
  assignee_user_id: string | null;
  answer_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CounselQueueListData {
  items: CounselQueueItem[];
  pagination: Pagination;
}
