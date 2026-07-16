interface BlockchainTxDetailPageProps {
  params: Promise<{ txId: string }>;
}

/** BlockchainTxDetail 공용 화면. 실제 조회는 GET /api/v1/blockchain/{tx_id} 연동 단계에서 구현한다. */
export default async function BlockchainTxDetailPage({ params }: BlockchainTxDetailPageProps) {
  const { txId } = await params;

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-lg font-semibold">블록체인 트랜잭션 상세</h1>
      <p className="text-sm text-muted-foreground">tx_id: {txId}</p>
      <p className="mt-4 text-sm text-muted-foreground">상세 조회는 다음 단계에서 연동됩니다.</p>
    </main>
  );
}
