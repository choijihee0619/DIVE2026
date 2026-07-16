"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { contractService } from "@/services/contractService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import { ContractStatus } from "@/types/enums";
import type { Contract } from "@/types/contract";
import {
  CONTRACT_STATUS_LABEL,
  contractStatusBadgeVariant,
  formatDeposit,
  hugCasePriority,
} from "@/lib/contract-labels";

const FILTER_TABS: { value: string; label: string }[] = [
  { value: "all", label: "전체" },
  { value: ContractStatus.INCIDENT_REPORTED, label: "사고 접수" },
  { value: ContractStatus.TRANSFERRED_TO_HUG, label: "HUG 이관" },
  { value: ContractStatus.RECOVERY_IN_PROGRESS, label: "회수 진행" },
  { value: ContractStatus.AT_RISK, label: "위험" },
];

const SUMMARY_CARDS: { status: ContractStatus; label: string }[] = [
  { status: ContractStatus.INCIDENT_REPORTED, label: "사고 접수" },
  { status: ContractStatus.TRANSFERRED_TO_HUG, label: "HUG 이관" },
  { status: ContractStatus.RECOVERY_IN_PROGRESS, label: "회수 진행" },
  { status: ContractStatus.AT_RISK, label: "위험" },
];

/** HUG-01 채권관리 대시보드: GET /contracts(관리 역할 전체 조회) 실데이터. */
export default function HugDashboardPage() {
  const router = useRouter();
  const clearSession = useSessionStore((state) => state.clearSession);

  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  const load = useCallback(() => {
    // 데모 규모(수십 건)라 한 번에 받아 요약 카드·필터를 클라이언트에서 처리한다.
    contractService
      .list({ size: 100 })
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
  }, [clearSession, router]);

  useEffect(() => {
    load();
  }, [load]);

  const sorted = useMemo(() => {
    if (!contracts) return [];
    return [...contracts].sort(
      (a, b) =>
        hugCasePriority(a.contract_status) - hugCasePriority(b.contract_status) ||
        b.deposit - a.deposit,
    );
  }, [contracts]);

  const visible = useMemo(
    () => (filter === "all" ? sorted : sorted.filter((c) => c.contract_status === filter)),
    [sorted, filter],
  );

  const countByStatus = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of contracts ?? []) {
      counts.set(c.contract_status, (counts.get(c.contract_status) ?? 0) + 1);
    }
    return counts;
  }, [contracts]);

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">전체 계약</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {contracts ? `${contracts.length}건` : "—"}
          </CardContent>
        </Card>
        {SUMMARY_CARDS.map(({ status, label }) => (
          <Card key={status}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">
              {contracts ? `${countByStatus.get(status) ?? 0}건` : "—"}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-3">
          <CardTitle>사건 우선순위 목록</CardTitle>
          <Tabs value={filter} onValueChange={(value) => setFilter(String(value))}>
            <TabsList>
              {FILTER_TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </CardHeader>
        <CardContent>
          {errorMessage ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <p className="text-sm text-destructive">{errorMessage}</p>
              <Button
                variant="outline"
                onClick={() => {
                  setContracts(null);
                  setErrorMessage(null);
                  load();
                }}
              >
                다시 시도
              </Button>
            </div>
          ) : contracts === null ? (
            <div className="flex flex-col gap-2" aria-label="목록 불러오는 중">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : visible.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {filter === "all" ? "표시할 사건이 없습니다." : "해당 상태의 사건이 없습니다."}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>계약 ID</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead className="text-right">보증금</TableHead>
                  <TableHead>계약 기간</TableHead>
                  <TableHead>최근 변경</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((contract) => (
                  <TableRow key={contract.contract_id}>
                    <TableCell className="font-mono text-xs">{contract.contract_id}</TableCell>
                    <TableCell>
                      <Badge variant={contractStatusBadgeVariant(contract.contract_status)}>
                        {CONTRACT_STATUS_LABEL[contract.contract_status] ?? contract.contract_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{formatDeposit(contract.deposit)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {contract.contract_start_date} ~ {contract.contract_end_date}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {contract.updated_at.slice(0, 10)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
