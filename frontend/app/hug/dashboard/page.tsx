"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { ContractStatus } from "@/types/enums";
import { hugCasePriority } from "@/lib/contract-labels";

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
  const { contracts, errorMessage, reload } = useContractList();
  const [filter, setFilter] = useState<string>("all");

  const sorted = useMemo(() => {
    if (!contracts) return null;
    return [...contracts].sort(
      (a, b) =>
        hugCasePriority(a.contract_status) - hugCasePriority(b.contract_status) ||
        b.deposit - a.deposit,
    );
  }, [contracts]);

  const visible = useMemo(() => {
    if (!sorted) return null;
    return filter === "all" ? sorted : sorted.filter((c) => c.contract_status === filter);
  }, [sorted, filter]);

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
          <ContractTable
            contracts={visible}
            errorMessage={errorMessage}
            onRetry={reload}
            emptyMessage={filter === "all" ? "표시할 사건이 없습니다." : "해당 상태의 사건이 없습니다."}
          />
        </CardContent>
      </Card>
    </div>
  );
}
