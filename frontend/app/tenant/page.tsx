"use client";

import { useMemo } from "react";
import Link from "next/link";
import { MessageCircleQuestion } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { ATTENTION_STATUSES } from "@/lib/contract-labels";

/** TEN-00 임차인 홈: GET /contracts(본인 계약) 실데이터. */
export default function TenantHomePage() {
  const { contracts, errorMessage, reload } = useContractList();

  const attentionCount = useMemo(
    () => (contracts ?? []).filter((c) => ATTENTION_STATUSES.includes(c.contract_status)).length,
    [contracts],
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">내 계약</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {contracts ? `${contracts.length}건` : "—"}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">주의 필요</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {contracts ? (
              <span className={attentionCount > 0 ? "text-destructive" : undefined}>{attentionCount}건</span>
            ) : (
              "—"
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">AI 전세 상담</CardTitle>
          </CardHeader>
          <CardContent>
            <Link href="/tenant/counsel" className={cn(buttonVariants({ variant: "outline", size: "sm" }))}>
              <MessageCircleQuestion size={14} />
              질문하러 가기
            </Link>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>진행 계약 목록</CardTitle>
        </CardHeader>
        <CardContent>
          <ContractTable
            contracts={contracts}
            errorMessage={errorMessage}
            onRetry={reload}
            emptyMessage="진행 중인 계약이 없습니다. 계약 진단을 시작해 보세요."
          />
        </CardContent>
      </Card>
    </div>
  );
}
