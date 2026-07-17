"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { blockchainService } from "@/services/blockchainService";
import { ApiError } from "@/services/apiClient";
import type { BlockchainTransaction } from "@/types/blockchain";
import { BLOCKCHAIN_STATUS_LABEL } from "@/lib/domain-labels";

/** BlockchainTxDetail 공용 화면: GET /blockchain/{tx_id} 실데이터. */
export default function BlockchainTxDetailPage() {
  const { txId } = useParams<{ txId: string }>();
  const [tx, setTx] = useState<BlockchainTransaction | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    blockchainService
      .get(txId)
      .then(setTx)
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "트랜잭션 정보를 불러오지 못했습니다."),
      );
  }, [txId]);

  return (
    <main className="mx-auto w-full max-w-2xl p-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>블록체인 트랜잭션 상세</CardTitle>
          {tx ? (
            <div className="flex gap-2">
              {tx.is_mock ? <Badge variant="outline">Mock 체인</Badge> : <Badge variant="secondary">온체인</Badge>}
              <Badge variant={tx.blockchain_status === "Failed" ? "destructive" : "secondary"}>
                {BLOCKCHAIN_STATUS_LABEL[tx.blockchain_status] ?? tx.blockchain_status}
              </Badge>
            </div>
          ) : null}
        </CardHeader>
        <CardContent>
          {errorMessage ? (
            <p className="py-6 text-center text-sm text-destructive">{errorMessage}</p>
          ) : tx === null ? (
            <Skeleton className="h-40 w-full" />
          ) : (
            <dl className="flex flex-col gap-3 text-sm">
              {[
                ["트랜잭션 ID", tx.blockchain_tx_id],
                ["이벤트 유형", tx.event_type],
                ["참조 ID", tx.reference_id],
                ["결과 해시", tx.result_hash],
                ["체인 tx 해시", tx.tx_hash ?? "-"],
                ["체인 ID", tx.chain_id !== null ? String(tx.chain_id) : "-"],
                ["컨트랙트 주소", tx.contract_address ?? "-"],
                ["기록 시각", tx.created_at],
                ["확정 시각", tx.confirmed_at ?? "-"],
              ].map(([label, value]) => (
                <div key={label} className="flex flex-col gap-0.5">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="break-all font-mono text-xs">{value}</dd>
                </div>
              ))}
            </dl>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
