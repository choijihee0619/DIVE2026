import type { Pagination } from "@/types/contract";

/** backend/app/schemas/evidence.py 그대로. */

export interface EvidenceRequest {
  evidence_request_id: string;
  contract_id: string;
  risk_assessment_id: string | null;
  reason: string;
  evidence_type: string;
  due_date: string | null;
  verification_status: string;
  latest_evidence_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceRequestListData {
  items: EvidenceRequest[];
  pagination: Pagination;
}

export interface EvidenceRequestCreate {
  contract_id: string;
  reason: string;
  evidence_type: string;
  risk_assessment_id?: string | null;
  due_date?: string | null;
}

export interface Evidence {
  evidence_id: string;
  evidence_request_id: string;
  file_name: string;
  document_hash: string;
  verification_status: string;
  submitted_at: string;
}

export interface Verification {
  verification_id: string;
  evidence_id: string;
  verification_status: string;
  reviewer_comment: string | null;
  resubmission_required: boolean;
  blockchain_tx_id: string | null;
}

export interface VerificationDecision {
  decision: "approve" | "reject" | "hold";
  reviewer_comment?: string;
}
