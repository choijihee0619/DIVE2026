import type { ContractStatus } from "@/types/enums";

/** backend/app/schemas/common.py::Pagination 그대로. */
export interface Pagination {
  page: number;
  size: number;
  total_elements: number;
  total_pages: number;
}

/** backend/app/schemas/contract.py::ContractResponse 그대로. */
export interface Contract {
  contract_id: string;
  property_id: string;
  tenant_user_id: string;
  landlord_user_id: string | null;
  landlord_id: string | null;
  contract_status: ContractStatus;
  deposit: number;
  contract_start_date: string;
  contract_end_date: string;
  landlord_type: string;
  housing_type: string;
  risk_assessment_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractListData {
  items: Contract[];
  pagination: Pagination;
}
