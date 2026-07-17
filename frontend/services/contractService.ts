import { apiClient } from "@/services/apiClient";
import type {
  Contract,
  ContractCreate,
  ContractListData,
  ContractTimeline,
  ReturnPlan,
  ReturnPlanCreate,
} from "@/types/contract";

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
  get: (contractId: string) => apiClient.get<Contract>(`/contracts/${contractId}`),
  timeline: (contractId: string) => apiClient.get<ContractTimeline>(`/contracts/${contractId}/timeline`),
  returnPlan: (contractId: string) => apiClient.get<ReturnPlan>(`/contracts/${contractId}/return-plan`),
  create: (payload: ContractCreate) => apiClient.post<Contract>("/contracts", payload),
  submitReturnPlan: (payload: ReturnPlanCreate) => apiClient.post<ReturnPlan>("/return-plans", payload),
};
