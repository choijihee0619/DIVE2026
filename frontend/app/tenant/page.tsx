"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FilePlus2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { ATTENTION_STATUSES } from "@/lib/contract-labels";
import { useSessionStore } from "@/stores/useSessionStore";
import { StatPill } from "@/components/viz/StatPill";
import { AnimatedNumber } from "@/components/viz/AnimatedNumber";
import { staggerContainer, fadeUp } from "@/lib/motion";

/** TEN-00 임차인 홈(260721 목업 3번): 인사말 + KPI 필 3종 + 진행 계약 목록. GET /contracts 실데이터. */
export default function TenantHomePage() {
  const router = useRouter();
  const user = useSessionStore((state) => state.user);
  const { contracts, errorMessage, reload } = useContractList();

  const attentionCount = useMemo(
    () => (contracts ?? []).filter((c) => ATTENTION_STATUSES.includes(c.contract_status)).length,
    [contracts],
  );

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-8">
      <motion.div variants={fadeUp}>
        <h1 className="text-3xl font-extrabold tracking-tight">
          안녕하세요, {user?.display_name ?? "임차인"}님 !
        </h1>
        <p className="mt-2 text-muted-foreground">안심전세를 위한 계약 항목을 한눈에 확인하세요.</p>
      </motion.div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3">
        <StatPill label="내 계약" tone="cyan" onClick={() => router.push("/tenant/contracts")}>
          {contracts ? (
            <>
              <AnimatedNumber value={contracts.length} />
              <span className="ml-0.5 text-xl font-bold">건</span>
            </>
          ) : (
            "—"
          )}
        </StatPill>
        <StatPill label="주의 필요" tone="lime" onClick={() => router.push("/tenant/contracts")}>
          {contracts ? (
            <>
              <AnimatedNumber value={attentionCount} />
              <span className="ml-0.5 text-xl font-bold">건</span>
            </>
          ) : (
            "—"
          )}
        </StatPill>
        <StatPill label="궁금한 내용은 !" tone="cyan" onClick={() => router.push("/tenant/counsel")}>
          AI
        </StatPill>
      </div>

      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-extrabold">진행 계약 목록</CardTitle>
            <Link href="/tenant/contracts/new" className={cn(buttonVariants({ size: "sm" }), "rounded-full")}>
              <FilePlus2 size={14} />
              계약 등록
            </Link>
          </CardHeader>
          <CardContent>
            <ContractTable
              contracts={contracts}
              errorMessage={errorMessage}
              onRetry={reload}
              emptyMessage="진행 중인 계약이 없습니다. 계약 등록으로 시작해 보세요."
              onRowClick={(contract) => router.push(`/tenant/contracts/${contract.contract_id}`)}
            />
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
