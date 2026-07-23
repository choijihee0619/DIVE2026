"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleDashed, FileUp, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { performanceClaimService } from "@/services/performanceClaimService";
import { ApiError } from "@/services/apiClient";
import type { PerformanceClaimDetail } from "@/types/performanceClaim";
import {
  CLAIM_DOCUMENT_TYPE_LABEL,
  CLAIM_STAGE_LABEL,
  CLAIM_STAGE_TONE,
  formatDate,
  type PerformanceClaimStage,
} from "@/lib/hug-labels";
import { cn } from "@/lib/utils";

/** 이행 진행 대표 경로(§20.5 P3) — 접수부터 채권관리 인계까지의 기준 Stepper 단계. */
const STAGE_PATH: PerformanceClaimStage[] = [
  "ClaimReceived",
  "UnderReview",
  "Approved",
  "HandoverCompleted",
  "SubrogationPaid",
  "RecoveryClaimRegistered",
];

/** 우회 단계 → Stepper 상 표시 위치(보완요청·유보는 심사 구간, 명도예정은 명도 구간). */
const STAGE_POSITION: Record<string, number> = {
  ClaimReceived: 0,
  SupplementRequested: 1,
  UnderReview: 1,
  OnHold: 1,
  Rejected: 1,
  Approved: 2,
  HandoverScheduled: 3,
  HandoverCompleted: 3,
  SubrogationPaid: 4,
  RecoveryClaimRegistered: 5,
  TransferredToRecovery: 5,
};

async function sha256Hex(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

const DOC_STATUS_BADGE: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  Requested: { label: "제출 필요", variant: "destructive" },
  Submitted: { label: "제출됨 · 확인 중", variant: "secondary" },
  Verified: { label: "확인 완료", variant: "default" },
  Rejected: { label: "반려 · 재제출 필요", variant: "destructive" },
  Waived: { label: "제출 면제", variant: "outline" },
};

interface ClaimProgressPanelProps {
  claimId: string;
  /** 청구인(임차인) 본인 여부 — true면 요청 서류에 제출 버튼이 붙는다. */
  canSubmit: boolean;
}

/** 임차인 이행 진행 Stepper + 청구 서류 제출(§20.5 P3). manage 이행 탭과 임차인 사고 화면 공용. */
export function ClaimProgressPanel({ claimId, canSubmit }: ClaimProgressPanelProps) {
  const [claim, setClaim] = useState<PerformanceClaimDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadingId, setUploadingId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingDocumentId = useRef<string | null>(null);

  const load = useCallback(() => {
    performanceClaimService
      .getClaim(claimId)
      .then(setClaim)
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "이행 진행 정보를 불러오지 못했습니다."),
      );
  }, [claimId]);

  useEffect(() => {
    load();
  }, [load]);

  const pickFile = (documentId: string) => {
    pendingDocumentId.current = documentId;
    fileInputRef.current?.click();
  };

  const onFileChosen = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    const documentId = pendingDocumentId.current;
    event.target.value = "";
    if (!file || !documentId) return;
    setUploadingId(documentId);
    try {
      const documentHash = await sha256Hex(file);
      await performanceClaimService.submitDocument(claimId, documentId, {
        file_name: file.name,
        document_hash: documentHash,
        object_uri: null,
        note: "임차인 직접 제출",
      });
      toast.success("서류를 제출했습니다. 확인 결과가 알림으로 안내됩니다.");
      load();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "서류 제출에 실패했습니다.");
    } finally {
      setUploadingId(null);
    }
  };

  if (errorMessage) {
    return <p className="py-4 text-sm text-destructive">{errorMessage}</p>;
  }
  if (!claim) {
    return <Skeleton className="h-40 w-full rounded-2xl" />;
  }

  const position = STAGE_POSITION[claim.stage] ?? 0;
  const stageLabel = CLAIM_STAGE_LABEL[claim.stage as PerformanceClaimStage] ?? claim.stage;
  const isDetour = ["SupplementRequested", "OnHold", "Rejected", "HandoverScheduled"].includes(claim.stage);

  return (
    <div className="flex flex-col gap-4">
      {/* 진행 Stepper */}
      <ol className="flex flex-wrap items-center gap-y-2">
        {STAGE_PATH.map((step, index) => {
          const reached = index <= position;
          const isCurrent = index === position;
          return (
            <li key={step} className="flex items-center">
              <span
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold",
                  isCurrent
                    ? CLAIM_STAGE_TONE[claim.stage as PerformanceClaimStage] ?? "bg-hug-navy text-white"
                    : reached
                      ? "text-hug-green-deep"
                      : "text-neutral-400",
                )}
              >
                {reached ? <CheckCircle2 size={13} /> : <CircleDashed size={13} />}
                {isCurrent ? stageLabel : CLAIM_STAGE_LABEL[step]}
              </span>
              {index < STAGE_PATH.length - 1 ? (
                <span className={cn("mx-0.5 h-px w-4", reached && index < position ? "bg-hug-green-deep" : "bg-line")} />
              ) : null}
            </li>
          );
        })}
      </ol>
      {isDetour ? (
        <p className="rounded-xl bg-warning-100 px-3.5 py-2.5 text-xs font-semibold text-warning-700">
          현재 <b>{stageLabel}</b> 상태입니다.
          {claim.stage === "SupplementRequested" ? " 아래 요청 서류를 제출하면 심사가 이어집니다." : null}
          {claim.stage === "Rejected" ? " 거절 사유를 확인하고 상담 채널로 문의하세요." : null}
        </p>
      ) : null}

      {/* 요청 서류 체크리스트 */}
      {claim.documents.length > 0 ? (
        <div>
          <p className="mb-2 text-xs font-bold text-muted-foreground">
            요청 서류 {claim.document_summary.verified_or_waived}/{claim.document_summary.required} 확인 완료
          </p>
          <ul className="flex flex-col gap-2">
            {claim.documents.map((document) => {
              const badge = DOC_STATUS_BADGE[document.verification_status] ?? {
                label: document.verification_status,
                variant: "outline" as const,
              };
              const submittable =
                canSubmit && ["Requested", "Rejected"].includes(document.verification_status);
              return (
                <li
                  key={document.document_id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line p-3 text-sm"
                >
                  <Badge variant={badge.variant}>{badge.label}</Badge>
                  <span className="font-semibold">
                    {CLAIM_DOCUMENT_TYPE_LABEL[document.document_type] ?? document.document_type}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-muted-foreground">
                    {document.due_at ? `기한 ${formatDate(document.due_at)}` : document.reason ?? ""}
                  </span>
                  {submittable ? (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={uploadingId === document.document_id}
                      onClick={() => pickFile(document.document_id)}
                    >
                      {uploadingId === document.document_id ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <FileUp size={14} />
                      )}
                      제출
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">아직 요청된 서류가 없습니다.</p>
      )}
      <input ref={fileInputRef} type="file" className="hidden" onChange={onFileChosen} />
    </div>
  );
}
