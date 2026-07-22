"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FilePlus2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { contractPhase, type ContractPhase } from "@/lib/contract-labels";
import { fadeUp, staggerContainer } from "@/lib/motion";

/**
 * 사이드바 "내 계약" 목록 화면 — GET /contracts 실데이터.
 *
 * MODIFIED 2026-07-22 (README §19.1): 계약 상태 축을 진행중/관리중(계약 후) 2탭으로 분리.
 * 진행중 행은 기존 계약 상세(진단·증빙 요청)로, 관리중 행은 3자 공동 열람
 * 계약 후 관리 화면(/contracts/{id}/manage)으로 이동한다.
 */
export default function TenantContractsPage() {
  const router = useRouter();
  const { contracts, errorMessage, reload } = useContractList();
  const [phase, setPhase] = useState<ContractPhase>("in_progress");

  const byPhase = useMemo(() => {
    const inProgress = (contracts ?? []).filter((c) => contractPhase(c.contract_status) === "in_progress");
    const managed = (contracts ?? []).filter((c) => contractPhase(c.contract_status) === "managed");
    return { in_progress: inProgress, managed };
  }, [contracts]);

  const visible = contracts === null ? null : byPhase[phase];

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-extrabold tracking-tight">내 계약</h1>
        <p className="mt-1.5 text-muted-foreground">보증 계약 현황을 확인하고 안전한 전세 생활을 시작하세요.</p>
      </motion.div>
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-col gap-3">
            <div className="flex flex-row items-center justify-between">
              <CardTitle className="text-lg font-extrabold">전체 계약</CardTitle>
              <Link href="/tenant/contracts/new" className={cn(buttonVariants({ size: "sm" }), "rounded-full")}>
                <FilePlus2 size={14} />
                계약 등록
              </Link>
            </div>
            <Tabs value={phase} onValueChange={(value) => setPhase(value as ContractPhase)}>
              <TabsList>
                <TabsTrigger value="in_progress">
                  진행중{contracts ? ` ${byPhase.in_progress.length}` : ""}
                </TabsTrigger>
                <TabsTrigger value="managed">
                  관리중 (계약 후){contracts ? ` ${byPhase.managed.length}` : ""}
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <p className="text-xs text-muted-foreground">
              {phase === "in_progress"
                ? "계약 체결 전 단계 — 위험진단·증빙 요청·전자계약을 진행합니다."
                : "계약 확정 이후 — 반환 D-day·증빙 현황·특약 이행을 임차인·임대인·HUG가 함께 확인합니다."}
            </p>
          </CardHeader>
          <CardContent>
            <ContractTable
              contracts={visible}
              errorMessage={errorMessage}
              onRetry={reload}
              emptyMessage={
                phase === "in_progress"
                  ? "진행 중인 계약이 없습니다. 계약 등록으로 시작해 보세요."
                  : "관리중(계약 후) 계약이 없습니다. 계약이 확정되면 이 탭에서 관리됩니다."
              }
              onRowClick={(contract) =>
                router.push(
                  contractPhase(contract.contract_status) === "managed"
                    ? `/contracts/${contract.contract_id}/manage`
                    : `/tenant/contracts/${contract.contract_id}`,
                )
              }
            />
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
