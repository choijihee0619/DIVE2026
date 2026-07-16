import { UserRole } from "@/types/enums";

export const ROLE_LABEL: Record<UserRole, string> = {
  [UserRole.TENANT]: "임차인",
  [UserRole.LANDLORD]: "임대인",
  [UserRole.ADVISOR]: "아이엔",
  [UserRole.HUG_ADMIN]: "HUG",
  [UserRole.SYSTEM_ADMIN]: "시스템 관리자",
  [UserRole.VERIFIER]: "검증 담당",
};
