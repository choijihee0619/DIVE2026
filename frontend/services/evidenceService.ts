import { apiClient } from "@/services/apiClient";
import type {
  Evidence,
  EvidenceRequest,
  EvidenceRequestCreate,
  EvidenceRequestListData,
  Verification,
  VerificationDecision,
} from "@/types/evidence";

interface EvidenceRequestListParams {
  contractId?: string;
  page?: number;
  size?: number;
}

export const evidenceService = {
  listRequests: ({ contractId, page = 1, size = 50 }: EvidenceRequestListParams = {}) => {
    const query = new URLSearchParams({ page: String(page), size: String(size) });
    if (contractId) query.set("contract_id", contractId);
    return apiClient.get<EvidenceRequestListData>(`/evidence-requests?${query.toString()}`);
  },
  createRequest: (payload: EvidenceRequestCreate) =>
    apiClient.post<EvidenceRequest>("/evidence-requests", payload),
  /** POST /evidence — multipart 파일 업로드(landlord 전용). */
  submitEvidence: (evidenceRequestId: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.post<Evidence>(
      `/evidence?evidence_request_id=${encodeURIComponent(evidenceRequestId)}`,
      undefined,
      { rawBody: formData },
    );
  },
  getVerification: (evidenceId: string) => apiClient.get<Verification>(`/verifications/${evidenceId}`),
  decide: (evidenceId: string, payload: VerificationDecision) =>
    apiClient.post<Verification>(`/verifications/${evidenceId}/decision`, payload),
};
