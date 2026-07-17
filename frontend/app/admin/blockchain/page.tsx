"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { blockchainService } from "@/services/blockchainService";
import { ApiError } from "@/services/apiClient";
import type { BlockchainTransaction } from "@/types/blockchain";
import { BLOCKCHAIN_STATUS_LABEL } from "@/lib/domain-labels";

/** ADM-02 블록체인 로그: GET /blockchain(system_admin 전용) 실데이터. */
export default function AdminBlockchainPage() {
  const [transactions, setTransactions] = useState<BlockchainTransaction[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    blockchainService
      .list()
      .then((data) => setTransactions(data.items))
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "블록체인 로그를 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>블록체인 기록 로그</CardTitle>
      </CardHeader>
      <CardContent>
        {errorMessage ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Button
              variant="outline"
              onClick={() => {
                setTransactions(null);
                setErrorMessage(null);
                load();
              }}
            >
              다시 시도
            </Button>
          </div>
        ) : transactions === null ? (
          <Skeleton className="h-32 w-full" />
        ) : transactions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            기록된 트랜잭션이 없습니다. 증빙 승인 등 이벤트가 발생하면 해시가 기록됩니다.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>이벤트</TableHead>
                <TableHead>참조 ID</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>기록 시각</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {transactions.map((tx) => (
                <TableRow key={tx.blockchain_tx_id}>
                  <TableCell className="font-medium">{tx.event_type}</TableCell>
                  <TableCell className="font-mono text-xs">{tx.reference_id}</TableCell>
                  <TableCell>
                    <Badge variant={tx.blockchain_status === "Failed" ? "destructive" : "secondary"}>
                      {BLOCKCHAIN_STATUS_LABEL[tx.blockchain_status] ?? tx.blockchain_status}
                      {tx.is_mock ? " · Mock" : ""}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {tx.created_at.slice(0, 16).replace("T", " ")}
                  </TableCell>
                  <TableCell>
                    <Link href={`/blockchain/${tx.blockchain_tx_id}`} className="text-xs text-primary underline">
                      상세
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
