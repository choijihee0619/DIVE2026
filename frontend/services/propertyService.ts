import { apiClient } from "@/services/apiClient";
import type { PropertyListData } from "@/types/property";

export const propertyService = {
  list: (size = 100) => apiClient.get<PropertyListData>(`/properties?page=1&size=${size}`),
};
