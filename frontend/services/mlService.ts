import { apiClient } from "@/services/apiClient";
import type { CounselClassifyResult, RecoveryPredictRequest, RecoveryPredictResult } from "@/types/ml";

/** /ml — 회수율 예측(HUG)·상담 자동분류(상담사 이상). 전 응답에 합성데이터 basis 문구 포함. */
export const mlService = {
  recoveryPredict: (payload: RecoveryPredictRequest) =>
    apiClient.post<RecoveryPredictResult>("/ml/recovery/predict", payload),
  classify: (text: string) => apiClient.post<CounselClassifyResult>("/ml/counsel/classify", { text }),
};
