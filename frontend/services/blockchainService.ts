import { apiClient } from "@/services/apiClient";
import type { BlockchainTransaction, BlockchainTransactionListData } from "@/types/blockchain";

export const blockchainService = {
  get: (txId: string) => apiClient.get<BlockchainTransaction>(`/blockchain/${txId}`),
  /** GET /blockchain — system_admin 전용 전체 로그. */
  list: (size = 100) => apiClient.get<BlockchainTransactionListData>(`/blockchain?page=1&size=${size}`),
};
