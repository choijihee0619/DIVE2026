"use client";

/**
 * COMMON 계약 후 관리 화면 (README §19.1) — 3자(임차인·임대인·HUG) 공동 열람 라우트.
 *
 * 어느 역할 화면에서 진입해도 같은 원본(계약 내용·변경 이력·증빙 상태)을 보여 주는
 * 공용 페이지. 실제 화면은 ContractManagementView가 그린다. 작성일 2026-07-22.
 */

import { useParams } from "next/navigation";
import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { ContractManagementView } from "@/components/contracts/ContractManagementView";
import { UserRole } from "@/types/enums";

/** 백엔드 GET /contracts/{id} 허용 역할과 동일하게 맞춘다. */
const VIEWER_ROLES = [
  UserRole.TENANT,
  UserRole.LANDLORD,
  UserRole.HUG_ADMIN,
  UserRole.ADVISOR,
  UserRole.SYSTEM_ADMIN,
];

export default function ContractManagePage() {
  const { contractId } = useParams<{ contractId: string }>();

  return (
    <RoleGuard allowedRoles={VIEWER_ROLES}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-5xl flex-1 px-6 pb-12 pt-2">
          <ContractManagementView contractId={contractId} />
        </main>
      </div>
    </RoleGuard>
  );
}
