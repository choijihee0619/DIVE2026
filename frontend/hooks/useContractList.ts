"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { contractService } from "@/services/contractService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { Contract } from "@/types/contract";

/**
 * GET /contracts 목록 조회 공용 훅(Tenant 홈·HUG 대시보드).
 * - contracts === null 이면서 error가 없으면 로딩 중.
 * - 401은 세션 정리 후 /login, 403은 /unauthorized로 보낸다.
 */
export function useContractList(size = 100) {
  const router = useRouter();
  const clearSession = useSessionStore((state) => state.clearSession);

  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    contractService
      .list({ size })
      .then((data) => {
        setContracts(data.items);
        setErrorMessage(null);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.httpStatus === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        if (error instanceof ApiError && error.httpStatus === 403) {
          router.replace("/unauthorized");
          return;
        }
        setErrorMessage(
          error instanceof ApiError ? `${error.message} (${error.errorCode})` : "목록을 불러오지 못했습니다.",
        );
      });
  }, [clearSession, router, size]);

  useEffect(() => {
    load();
  }, [load]);

  /** 오류 화면의 "다시 시도" 버튼용: 로딩 상태로 되돌린 뒤 재조회한다. */
  const reload = useCallback(() => {
    setContracts(null);
    setErrorMessage(null);
    load();
  }, [load]);

  return { contracts, errorMessage, reload };
}
