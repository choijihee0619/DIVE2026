import { apiClient } from "@/services/apiClient";
import type { EsignSession, EsignVerifyResult } from "@/types/esign";

/** /esign — 전자계약 공동세션(생성·참여·특약·서명·앵커 검증, 시안 2-4). */
export const esignService = {
  /** 임차인 전용. 동일 계약의 활성 세션이 있으면 그 세션을 그대로 돌려준다(멱등). */
  createSession: (contractId: string) =>
    apiClient.post<EsignSession>("/esign/sessions", { contract_id: contractId }),
  /** 임대인 전용. 세션 초대 코드로 참여. */
  join: (sessionCode: string) =>
    apiClient.post<EsignSession>("/esign/sessions/join", { session_code: sessionCode }),
  /** 상태 폴링(접속·특약·서명·앵커). */
  get: (sessionId: string) => apiClient.get<EsignSession>(`/esign/sessions/${sessionId}`),
  proposeTerm: (sessionId: string, text: string) =>
    apiClient.post<EsignSession>(`/esign/sessions/${sessionId}/terms`, { text }),
  actOnTerm: (sessionId: string, termId: string, action: "agree" | "withdraw") =>
    apiClient.post<EsignSession>(`/esign/sessions/${sessionId}/terms/${termId}`, { action }),
  sign: (sessionId: string) => apiClient.post<EsignSession>(`/esign/sessions/${sessionId}/sign`),
  /** tampered_fields 지정 시 변조 시나리오 검증(불일치 데모). */
  verify: (contractId: string, tamperedFields?: Record<string, unknown>) =>
    apiClient.post<EsignVerifyResult>(`/esign/contracts/${contractId}/verify`, {
      tampered_fields: tamperedFields ?? null,
    }),
};
