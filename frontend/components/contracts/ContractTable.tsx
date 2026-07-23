"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ScrollText } from "lucide-react";
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
import { formatDeposit } from "@/lib/contract-labels";
import { StatusChip } from "@/components/viz/StatusChip";

interface ContractTableProps {
  /** null이면 로딩 스켈레톤을 표시한다. */
  contracts: Contract[] | null;
  errorMessage: string | null;
  onRetry: () => void;
  emptyMessage?: string;
  /** 지정하면 행 클릭 시 호출(행에 pointer 커서 표시). */
  onRowClick?: (contract: Contract) => void;
}

/** 계약 목록 테이블 + 로딩/빈/오류 상태(Tenant 홈·HUG 대시보드 공용). */
export function ContractTable({
  contracts,
  errorMessage,
  onRetry,
  emptyMessage = "표시할 계약이 없습니다.",
  onRowClick,
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
        <TableRow className="border-b border-line hover:bg-transparent">
          <TableHead className="text-xs font-bold text-muted-foreground">계약</TableHead>
          <TableHead className="text-xs font-bold text-muted-foreground">상태</TableHead>
          <TableHead className="text-right text-xs font-bold text-muted-foreground">보증금</TableHead>
          <TableHead className="text-xs font-bold text-muted-foreground">계약 기간</TableHead>
          <TableHead className="text-xs font-bold text-muted-foreground">최근 변경</TableHead>
          <TableHead className="text-xs font-bold text-muted-foreground">등기부</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {contracts.map((contract, index) => (
          <motion.tr
            key={contract.contract_id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: index * 0.05, ease: "easeOut" }}
            className={
              "border-b border-line/70 transition-colors last:border-b-0 hover:bg-neutral-100 " +
              (onRowClick ? "cursor-pointer" : "")
            }
            onClick={onRowClick ? () => onRowClick(contract) : undefined}
          >
            <TableCell className="max-w-56">
              {contract.address_summary ? (
                <span className="block truncate text-sm font-semibold">{contract.address_summary}</span>
              ) : (
                <span className="font-mono text-xs">{contract.contract_id}</span>
              )}
            </TableCell>
            <TableCell>
              <StatusChip status={contract.contract_status} />
            </TableCell>
            <TableCell className="text-right font-semibold tnum">{formatDeposit(contract.deposit)}</TableCell>
            <TableCell className="text-sm text-muted-foreground tnum">
              {contract.contract_start_date} ~ {contract.contract_end_date}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground tnum">
              {contract.updated_at.slice(0, 10)}
            </TableCell>
            <TableCell>
              <Link
                href={`/registry/${contract.property_id}`}
                onClick={(event) => event.stopPropagation()}
                className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-xs font-bold text-hug-blue transition-colors hover:bg-hug-sky"
              >
                <ScrollText size={12} />
                열람
              </Link>
            </TableCell>
          </motion.tr>
        ))}
      </TableBody>
    </Table>
  );
}
