"use client";

import { Check, CircleAlert, Eye, FileText, Landmark, RefreshCw, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ContractStatus } from "@/types/enums";
import { CONTRACT_STATUS_LABEL } from "@/lib/contract-labels";

interface ChipStyle {
  className: string;
  icon: LucideIcon;
}

const DEFAULT_STYLE: ChipStyle = { className: "bg-hug-sky text-hug-blue", icon: FileText };

/** 260721 목업 계약 목록의 상태 칩(✓ 진단 완료 / ⚠ 위험 / 👁 모니터링) 톤. */
const STYLE: Partial<Record<ContractStatus, ChipStyle>> = {
  [ContractStatus.DRAFT]: { className: "bg-neutral-200 text-neutral-600", icon: FileText },
  [ContractStatus.DIAGNOSED]: { className: "bg-hug-mint text-hug-green-deep", icon: Check },
  [ContractStatus.VERIFIED]: { className: "bg-hug-mint text-hug-green-deep", icon: ShieldCheck },
  [ContractStatus.CONTRACT_FINALIZED]: { className: "bg-hug-sky text-hug-blue", icon: ShieldCheck },
  [ContractStatus.MONITORING]: { className: "bg-warning-100 text-warning-700", icon: Eye },
  [ContractStatus.AT_RISK]: { className: "bg-danger-100 text-danger-600", icon: CircleAlert },
  [ContractStatus.INCIDENT_REPORTED]: { className: "bg-danger-100 text-danger-600", icon: CircleAlert },
  [ContractStatus.TRANSFERRED_TO_HUG]: { className: "bg-danger-100 text-danger-600", icon: Landmark },
  [ContractStatus.RECOVERY_IN_PROGRESS]: { className: "bg-hug-sky text-hug-blue", icon: RefreshCw },
  [ContractStatus.CLOSED]: { className: "bg-neutral-200 text-neutral-600", icon: Check },
};

interface StatusChipProps {
  status: ContractStatus;
  className?: string;
}

export function StatusChip({ status, className }: StatusChipProps) {
  const { className: tone, icon: Icon } = STYLE[status] ?? DEFAULT_STYLE;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold whitespace-nowrap",
        tone,
        className,
      )}
    >
      <Icon size={12} strokeWidth={2.5} />
      {CONTRACT_STATUS_LABEL[status]}
    </span>
  );
}
