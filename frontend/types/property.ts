import type { Pagination } from "@/types/contract";

/** backend/app/schemas/property.py 그대로. */
export interface Property {
  property_id: string;
  address: {
    road_address?: string;
    jibun_address?: string | null;
    dong?: string | null;
    ho?: string | null;
    [key: string]: unknown;
  };
  housing_type: string | null;
  source_system: string;
  created_at: string;
  updated_at: string;
}

export interface PropertyListData {
  items: Property[];
  pagination: Pagination;
}

/** backend registry_service.parse_register_detail 결과 — 등기부 원문 표시용 표 구조. */
export interface RegisterSection {
  section: string; // 표제부 | 갑구 | 을구
  title: string;
  headers: string[];
  rows: { cells: string[]; canceled: boolean }[];
}

export interface RegisterDetail {
  doc_title: string;
  realty: string;
  publish_date: string;
  publish_office: string;
  unique_no: string;
  competent_office: string;
  sections: RegisterSection[];
}

/** backend registry_service._to_summary 그대로. */
export interface RegistrySnapshot {
  registry_snapshot_id: string;
  property_id: string;
  source_system: "api_live" | "mock" | "demo_scenario";
  provider: string | null;
  demo_scenario: string | null;
  demo_notice: string | null;
  fallback_reason: string | null;
  query_address: string | null;
  features: {
    has_seizure?: boolean;
    seizure_rows_active?: number;
    mortgage_count?: number;
    mortgage_max_total_won?: number;
    mortgage_to_deposit_ratio?: number;
    rights_keywords?: Record<string, number>;
    publish_date?: string;
    [key: string]: unknown;
  };
  register_detail: RegisterDetail | null;
  created_at: string;
}
