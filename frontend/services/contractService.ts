import { apiClient } from "@/services/apiClient";
import type { ContractListData } from "@/types/contract";

interface ContractListParams {
  contractStatus?: string;
  page?: number;
  size?: number;
}

export const contractService = {
  /** GET /contracts — tenant/landlord는 본인 계약, hug_admin/system_admin은 전체 계약. */
  list: ({ contractStatus, page = 1, size = 20 }: ContractListParams = {}) => {
    const query = new URLSearchParams({ page: String(page), size: String(size) });
    if (contractStatus) query.set("contract_status", contractStatus);
    return apiClient.get<ContractListData>(`/contracts?${query.toString()}`);
  },
};
