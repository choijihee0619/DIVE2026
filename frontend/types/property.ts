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
