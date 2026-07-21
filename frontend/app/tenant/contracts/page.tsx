"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { FilePlus2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { fadeUp, staggerContainer } from "@/lib/motion";

/** 사이드바 "내 계약" 목록 화면 — GET /contracts 실데이터. */
export default function TenantContractsPage() {
  const router = useRouter();
  const { contracts, errorMessage, reload } = useContractList();

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-extrabold tracking-tight">내 계약</h1>
        <p className="mt-1.5 text-muted-foreground">보증 계약 현황을 확인하고 안전한 전세 생활을 시작하세요.</p>
      </motion.div>
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-extrabold">전체 계약</CardTitle>
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
              emptyMessage="등록된 계약이 없습니다."
              onRowClick={(contract) => router.push(`/tenant/contracts/${contract.contract_id}`)}
            />
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
