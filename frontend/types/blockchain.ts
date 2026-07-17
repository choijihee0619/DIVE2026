import type { Pagination } from "@/types/contract";

/** backend/app/schemas/blockchain.py 그대로. */
export interface BlockchainTransaction {
  blockchain_tx_id: string;
  event_type: string;
  reference_id: string;
  result_hash: string;
  tx_hash: string | null;
  chain_id: number | null;
  contract_address: string | null;
  blockchain_status: string;
  is_mock: boolean;
  created_at: string;
  confirmed_at: string | null;
}

export interface BlockchainTransactionListData {
  items: BlockchainTransaction[];
  pagination: Pagination;
}
