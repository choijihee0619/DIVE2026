"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Contract } from "@/types/contract";
import { CONTRACT_STATUS_LABEL, contractStatusBadgeVariant, formatDeposit } from "@/lib/contract-labels";

interface ContractTableProps {
  /** null이면 로딩 스켈레톤을 표시한다. */
  contracts: Contract[] | null;
  errorMessage: string | null;
  onRetry: () => void;
  emptyMessage?: string;
}

/** 계약 목록 테이블 + 로딩/빈/오류 상태(Tenant 홈·HUG 대시보드 공용). */
export function ContractTable({
  contracts,
  errorMessage,
  onRetry,
  emptyMessage = "표시할 계약이 없습니다.",
}: ContractTableProps) {
  if (errorMessage) {
    return (
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <p className="text-sm text-destructive">{errorMessage}</p>
        <Button variant="outline" onClick={onRetry}>
          다시 시도
        </Button>
      </div>
    );
  }

  if (contracts === null) {
    return (
      <div className="flex flex-col gap-2" aria-label="목록 불러오는 중">
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (contracts.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
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
        {contracts.map((contract) => (
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
            <TableCell className="text-sm text-muted-foreground">{contract.updated_at.slice(0, 10)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
