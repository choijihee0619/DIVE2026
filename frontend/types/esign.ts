/** backend/app/schemas/esign.py와 1:1. 전자계약 공동세션(시안 2-4). */

export type EsignStatus = "TermsAgreement" | "Signing" | "Anchored" | "Cancelled";
export type TermStatus = "proposed" | "agreed" | "withdrawn";
export type PartyRole = "tenant" | "landlord";

export interface SpecialTerm {
  term_id: string;
  text: string;
  source: "ai_recommend" | PartyRole;
  rationale: string | null;
  status: TermStatus;
  agreed_by: PartyRole[];
}

export interface Participant {
  role: PartyRole;
  user_id: string | null;
  display_name: string | null;
  joined: boolean;
  signed: boolean;
  signed_at: string | null;
}

export interface EsignContractSummary {
  property_id: string;
  deposit: number;
  contract_start_date: string;
  contract_end_date: string;
  landlord_type: string;
  housing_type: string;
}

export interface EsignSession {
  session_id: string;
  session_code: string;
  contract_id: string;
  status: EsignStatus;
  participants: Participant[];
  special_terms: SpecialTerm[];
  contract_summary: EsignContractSummary;
  contract_hash: string | null;
  blockchain_tx_id: string | null;
  tx_hash: string | null;
  anchored_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EsignVerifyResult {
  contract_id: string;
  stored_hash: string;
  recomputed_hash: string;
  match: boolean;
  tampered_fields: Record<string, unknown> | null;
  tx_hash: string | null;
  blockchain_status: string | null;
  verified_at: string;
}
