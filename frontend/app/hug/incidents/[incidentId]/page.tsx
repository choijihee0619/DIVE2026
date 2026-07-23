"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, ExternalLink, FilePlus2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useSessionStore } from "@/stores/useSessionStore";
import { performanceClaimService } from "@/services/performanceClaimService";
import { ApiError } from "@/services/apiClient";
import type { ClaimEvent, HugIncidentDetail } from "@/types/performanceClaim";
import { ContractStepper } from "@/components/viz/ContractStepper";
import { TimelineList } from "@/components/viz/TimelineList";
import {
  AUCTION_STAGE_FLOW,
  CLAIM_DOCUMENT_TYPE_LABEL,
  CLAIM_STAGE_LABEL,
  CLAIM_STAGE_TONE,
  DOCUMENT_STATUS_LABEL,
  DOCUMENT_STATUS_TONE,
  NONRETURN_STAGE_FLOW,
  OFFICIAL_ACCIDENT_TYPE_LABEL,
  SLA_STATUS_LABEL,
  SLA_STATUS_TONE,
  STAGE_PROGRESS_ALIAS,
  formatDate,
  formatDateTime,
  formatRemaining,
  formatWonShort,
  type ClaimDocumentStatus,
  type SlaStatus,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none tnum placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

/** workflow별 필수서류 (backend _REQUIRED_DOCUMENTS와 동일). */
const REQUIRED_DOCUMENTS: Record<string, string[]> = {
  JEONSE_RETURN_NONRETURN: ["CONTRACT_DOCUMENT", "CONTRACT_TERMINATION_PROOF", "TENANT_RIGHTS_PROOF"],
  JEONSE_AUCTION_PUBLIC_SALE: ["CONTRACT_DOCUMENT", "TENANT_RIGHTS_PROOF", "AUCTION_DISTRIBUTION_PROOF"],
};

/** 감사 이벤트 액션 → 한국어 요약 (backend performance_claim_service의 action 명과 1:1). */
const EVENT_ACTION_LABEL: Record<string, string> = {
  CLAIM_RECEIVED: "이행청구 접수",
  DOCUMENTS_REQUESTED: "서류 요청",
  DOCUMENT_SUBMITTED: "서류 제출",
  DOCUMENT_VERIFY: "서류 검증",
  DOCUMENT_REJECT: "서류 반려",
  DOCUMENT_WAIVE: "서류 면제",
  SUPPLEMENT_REQUESTED: "보완 요청",
  REVIEW_STARTED: "심사 시작",
  CLAIM_APPROVE: "이행 승인",
  CLAIM_ON_HOLD: "심사 유보",
  CLAIM_REJECT: "이행 거절",
  HANDOVER_SCHEDULED: "명도 일정 등록",
  HANDOVER_COMPLETED: "명도 완료",
  SUBROGATION_PAYMENT_RECORDED: "대위변제 지급",
  RECOVERY_CLAIM_REGISTERED: "구상채권 등록",
  TRANSFERRED_TO_RECOVERY: "채권관리 인계",
};

/** 사고접수·보증이행 사건 상세 — 단계 Stepper와 서류·심사·명도·지급·채권등록 업무 액션. */
export default function HugIncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const user = useSessionStore((state) => state.user);
  const [detail, setDetail] = useState<HugIncidentDetail | null>(null);
  const [events, setEvents] = useState<ClaimEvent[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

  /* 액션 폼 상태 */
  const [claimAmount, setClaimAmount] = useState("");
  const [approvedAmount, setApprovedAmount] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [checklistDone, setChecklistDone] = useState(false);
  const [moveoutDate, setMoveoutDate] = useState("");
  const [settlementDone, setSettlementDone] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [registerType, setRegisterType] = useState("RECOURSE_STANDARD");
  const [registerPrincipal, setRegisterPrincipal] = useState("");
  const [transferNextAction, setTransferNextAction] = useState("재산조사 착수");

  const claim = detail?.performance_claim ?? null;

  const load = useCallback(() => {
    performanceClaimService
      .getIncident(incidentId)
      .then((data) => {
        setDetail(data);
        setErrorMessage(null);
        /* 폼 기본값 — 비어 있을 때만 원장값으로 채운다. */
        if (data.deposit_amount) setClaimAmount((prev) => prev || String(data.deposit_amount));
        const loadedClaim = data.performance_claim;
        if (loadedClaim) {
          setApprovedAmount((prev) => prev || String(loadedClaim.claim_amount));
          if (loadedClaim.approved_amount) {
            setPaymentAmount((prev) => prev || String(loadedClaim.approved_amount));
          }
          if (loadedClaim.paid_amount) {
            setRegisterPrincipal((prev) => prev || String(loadedClaim.paid_amount));
          }
          performanceClaimService
            .listEvents(loadedClaim.performance_claim_id)
            .then((result) => setEvents(result.items))
            .catch(() => setEvents([]));
        } else {
          setEvents([]);
        }
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "사건 정보를 불러오지 못했습니다."),
      );
  }, [incidentId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = (action: () => Promise<unknown>, successMessage: string) => {
    if (isActing) return;
    setIsActing(true);
    action()
      .then(() => {
        toast.success(successMessage);
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "요청 처리에 실패했습니다."),
      )
      .finally(() => setIsActing(false));
  };

  const claimId = claim?.performance_claim_id ?? "";
  const stage = claim?.stage ?? null;

  const stageFlow = useMemo(
    () =>
      claim?.workflow_type === "JEONSE_AUCTION_PUBLIC_SALE" ? AUCTION_STAGE_FLOW : NONRETURN_STAGE_FLOW,
    [claim],
  );

  const stepperCurrent = useMemo(() => {
    if (!stage) return 0;
    if (stage === "Rejected") return stageFlow.indexOf("UnderReview");
    const effective = STAGE_PROGRESS_ALIAS[stage] ?? stage;
    const index = stageFlow.indexOf(effective);
    return index >= 0 ? index : 0;
  }, [stage, stageFlow]);

  /** 아직 요청되지 않은 필수서류 목록. */
  const missingRequiredDocs = useMemo(() => {
    if (!claim) return [];
    const requested = new Set(claim.documents.map((doc) => doc.document_type));
    return (REQUIRED_DOCUMENTS[claim.workflow_type] ?? []).filter((type) => !requested.has(type));
  }, [claim]);

  const requestRequiredDocs = () =>
    runAction(
      () =>
        performanceClaimService.requestDocuments(
          claimId,
          missingRequiredDocs.map((type) => ({
            document_type: type,
            reason: `${CLAIM_DOCUMENT_TYPE_LABEL[type] ?? type} 제출 요청`,
            required: true,
          })),
        ),
      "필수서류 제출을 요청했습니다.",
    );

  const decideDocument = (documentId: string, decision: "VERIFY" | "REJECT" | "WAIVE") => {
    const reason =
      decision === "VERIFY"
        ? "담당자 검토 결과 적합"
        : decision === "REJECT"
          ? "보완 필요 — 재제출 요청"
          : "제출 면제 처리";
    runAction(
      () => performanceClaimService.decideDocument(claimId, documentId, { decision, reason }),
      decision === "VERIFY" ? "서류를 검증했습니다." : decision === "REJECT" ? "서류를 반려했습니다." : "서류를 면제 처리했습니다.",
    );
  };

  if (errorMessage) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-sm text-destructive">{errorMessage}</p>
        <Link href="/hug/incidents" className="text-sm font-bold text-hug-blue hover:underline">
          ← 사건 목록으로
        </Link>
      </div>
    );
  }

  /** 현 단계에서 가능한 업무 액션 패널. */
  const renderActionPanel = () => {
    if (!detail) return null;

    /* 1) 이행청구 미생성 — 신규 통지 */
    if (!claim) {
      if (detail.status !== "Received") {
        return (
          <p className="py-6 text-center text-sm text-muted-foreground">
            이행청구 없이 종결된 통지입니다.
          </p>
        );
      }
      const inferable =
        detail.incident_type === "DEPOSIT_NOT_RETURNED" || detail.incident_type === "AUCTION_STARTED";
      return (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            runAction(
              () =>
                performanceClaimService.createClaim(incidentId, {
                  claim_amount: Number(claimAmount) || 0,
                  ...(inferable
                    ? {}
                    : {
                        official_accident_type: "CONTRACT_END_NONRETURN",
                        workflow_type: "JEONSE_RETURN_NONRETURN",
                      }),
                }),
              "보증이행청구를 접수했습니다.",
            );
          }}
        >
          <p className="text-sm text-muted-foreground">
            신고내용·계약·보증 유효성을 확인한 뒤 이행청구 원장을 생성합니다.
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="claim-amount">청구금액 (원)</Label>
            <input
              id="claim-amount"
              type="number"
              min={1}
              value={claimAmount}
              onChange={(e) => setClaimAmount(e.target.value)}
              className={inputClass}
              required
            />
          </div>
          {!inferable ? (
            <p className="rounded-xl bg-warning-100 px-3 py-2 text-xs text-warning-700">
              의심 신고 유형입니다 — 계약종료 후 미반환 절차로 접수되며, 심사 과정에서 사고유형을
              확정합니다.
            </p>
          ) : null}
          <Button type="submit" disabled={isActing} className="rounded-xl font-bold">
            <FilePlus2 size={14} />
            이행청구 접수
          </Button>
        </form>
      );
    }

    /* 2) 단계별 액션 */
    switch (stage) {
      case "ClaimReceived":
      case "SupplementRequested":
      case "OnHold":
        return (
          <div className="flex flex-col gap-3">
            {missingRequiredDocs.length > 0 ? (
              <>
                <p className="text-sm text-muted-foreground">
                  필수서류 {missingRequiredDocs.length}종이 아직 요청되지 않았습니다.
                </p>
                <Button disabled={isActing} onClick={requestRequiredDocs} className="rounded-xl font-bold">
                  필수서류 일괄 요청
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                필수서류가 모두 검증되면 심사를 시작할 수 있습니다.
              </p>
            )}
            <Button
              variant="outline"
              disabled={isActing}
              onClick={() =>
                runAction(
                  () => performanceClaimService.startReview(claimId, "필수서류 검증 완료"),
                  "심사를 시작했습니다.",
                )
              }
              className="rounded-xl font-bold"
            >
              심사 시작
            </Button>
          </div>
        );
      case "UnderReview":
        return (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="approved-amount">승인금액 (원)</Label>
              <input
                id="approved-amount"
                type="number"
                min={1}
                value={approvedAmount}
                onChange={(e) => setApprovedAmount(e.target.value)}
                className={inputClass}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="decision-reason">결정 사유</Label>
              <textarea
                id="decision-reason"
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                rows={2}
                placeholder="사고성립·계약종료·권리·금액 심사 결과"
                className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>
            <label className="flex items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                checked={checklistDone}
                onChange={(e) => setChecklistDone(e.target.checked)}
                className="size-4 accent-[var(--color-hug-blue)]"
              />
              심사 체크리스트 확인 완료
            </label>
            <div className="grid grid-cols-3 gap-2">
              <Button
                disabled={isActing}
                onClick={() =>
                  runAction(
                    () =>
                      performanceClaimService.decide(claimId, {
                        decision: "APPROVE",
                        approved_amount: Number(approvedAmount) || 0,
                        reason: decisionReason || "심사 결과 승인",
                        checklist_completed: checklistDone,
                      }),
                    "이행청구를 승인했습니다.",
                  )
                }
                className="rounded-xl font-bold"
              >
                승인
              </Button>
              <Button
                variant="outline"
                disabled={isActing}
                onClick={() =>
                  runAction(
                    () =>
                      performanceClaimService.decide(claimId, {
                        decision: "ON_HOLD",
                        reason: decisionReason || "추가 확인 필요 — 심사 유보",
                      }),
                    "심사를 유보했습니다.",
                  )
                }
                className="rounded-xl font-bold"
              >
                유보
              </Button>
              <Button
                variant="outline"
                disabled={isActing}
                onClick={() =>
                  runAction(
                    () =>
                      performanceClaimService.decide(claimId, {
                        decision: "REJECT",
                        reason: decisionReason || "보증 이행 요건 미충족",
                        checklist_completed: checklistDone,
                      }),
                    "이행청구를 거절했습니다.",
                  )
                }
                className="rounded-xl font-bold text-danger-600"
              >
                거절
              </Button>
            </div>
          </div>
        );
      case "Approved":
        if (claim.handover_required) {
          return (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="moveout-date">이사(명도) 예정일</Label>
                <input
                  id="moveout-date"
                  type="date"
                  value={moveoutDate}
                  onChange={(e) => setMoveoutDate(e.target.value)}
                  className={inputClass}
                />
              </div>
              <Button
                disabled={isActing || !moveoutDate}
                onClick={() =>
                  runAction(
                    () =>
                      performanceClaimService.handover(claimId, {
                        action: "SCHEDULE",
                        moveout_due_at: `${moveoutDate}T18:00:00+09:00`,
                        reason: "임차인과 이사일 협의 완료",
                      }),
                    "명도 일정을 등록했습니다.",
                  )
                }
                className="rounded-xl font-bold"
              >
                명도 일정 등록
              </Button>
            </div>
          );
        }
        return renderPaymentForm();
      case "HandoverScheduled":
        return (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground tnum">
              명도 예정일 {formatDate(claim.moveout_due_at)} — 빈집·인도 상태와 관리비·공과금 정산을
              확인합니다.
            </p>
            <label className="flex items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                checked={settlementDone}
                onChange={(e) => setSettlementDone(e.target.checked)}
                className="size-4 accent-[var(--color-hug-blue)]"
              />
              관리비·공과금 정산 확인
            </label>
            <Button
              disabled={isActing || !settlementDone}
              onClick={() =>
                runAction(
                  () =>
                    performanceClaimService.handover(claimId, {
                      action: "COMPLETE",
                      settlement_confirmed: settlementDone,
                      reason: "주택 인도·정산 확인 완료",
                    }),
                  "명도를 완료 처리했습니다.",
                )
              }
              className="rounded-xl font-bold"
            >
              명도 완료
            </Button>
          </div>
        );
      case "HandoverCompleted":
        return renderPaymentForm();
      case "SubrogationPaid":
        return (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="register-type">채권 구분</Label>
              <select
                id="register-type"
                value={registerType}
                onChange={(e) => setRegisterType(e.target.value)}
                className={inputClass}
              >
                <option value="RECOURSE_STANDARD">구상채권</option>
                <option value="RECOURSE_NEW_PRODUCT">구상채권(신상품)</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="register-principal">구상원금 (원)</Label>
              <input
                id="register-principal"
                type="number"
                min={1}
                value={registerPrincipal}
                onChange={(e) => setRegisterPrincipal(e.target.value)}
                className={inputClass}
              />
            </div>
            <Button
              disabled={isActing}
              onClick={() =>
                runAction(
                  () =>
                    performanceClaimService.registerRecoveryClaim(claimId, {
                      claim_type: registerType,
                      principal: Number(registerPrincipal) || 0,
                      incurred_amount: Number(registerPrincipal) || 0,
                      incurred_date: new Date().toISOString().slice(0, 10),
                    }),
                  "구상채권을 등록했습니다.",
                )
              }
              className="rounded-xl font-bold"
            >
              구상채권 등록
            </Button>
          </div>
        );
      case "RecoveryClaimRegistered":
        return (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="transfer-next">인계 후 다음 조치</Label>
              <input
                id="transfer-next"
                value={transferNextAction}
                onChange={(e) => setTransferNextAction(e.target.value)}
                className={inputClass}
              />
            </div>
            <Button
              disabled={isActing || !user}
              onClick={() =>
                runAction(
                  () =>
                    performanceClaimService.transfer(claimId, {
                      assignee_user_id: user?.user_id ?? "",
                      next_action: transferNextAction || "재산조사 착수",
                      reason: "대위변제·채권등록 완료에 따른 회수업무 인계",
                    }),
                  "채권관리 담당자에게 인계했습니다.",
                )
              }
              className="rounded-xl font-bold"
            >
              채권관리 인계
            </Button>
          </div>
        );
      case "TransferredToRecovery":
        return (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              회수업무로 인계된 사건입니다. 등록 채권은 채권관리 화면에서 관리합니다.
            </p>
            {claim.recovery_claims.map((registered) => (
              <Link
                key={registered.recovery_claim_id}
                href={`/hug/recovery/${registered.recovery_claim_id}`}
                className="flex items-center justify-between rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm font-bold text-hug-blue transition-colors hover:bg-hug-sky"
              >
                등록 채권 보기
                <ExternalLink size={14} />
              </Link>
            ))}
          </div>
        );
      case "Rejected":
        return (
          <p className="py-4 text-sm text-muted-foreground">
            거절 종결된 사건입니다. {claim.decision_reason ? `사유: ${claim.decision_reason}` : ""}
          </p>
        );
      default:
        return null;
    }
  };

  function renderPaymentForm() {
    if (!claim) return null;
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm text-muted-foreground tnum">
          승인금액 {claim.approved_amount ? `${formatWonShort(claim.approved_amount)} 원` : "—"} 중 누적
          지급 {formatWonShort(claim.paid_amount)} 원
        </p>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="payment-amount">지급금액 (원)</Label>
          <input
            id="payment-amount"
            type="number"
            min={1}
            value={paymentAmount}
            onChange={(e) => setPaymentAmount(e.target.value)}
            className={inputClass}
          />
        </div>
        <Button
          disabled={isActing}
          onClick={() =>
            runAction(
              () =>
                performanceClaimService.paySubrogation(claimId, {
                  payment_reference: `PAY-${Date.now()}`,
                  paid_amount: Number(paymentAmount) || 0,
                  paid_at: new Date().toISOString().slice(0, 10),
                  reason: "임차인 앞 보증금 지급",
                }),
              "대위변제 지급을 기록했습니다.",
            )
          }
          className="rounded-xl font-bold"
        >
          대위변제 지급
        </Button>
      </div>
    );
  }

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      {/* 헤더 */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-start gap-3">
        <Link
          href="/hug/incidents"
          className="mt-1 flex size-9 items-center justify-center rounded-xl border border-line bg-card text-muted-foreground transition-colors hover:bg-neutral-100"
        >
          <ArrowLeft size={16} />
        </Link>
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold tracking-tight">
            {detail?.incident_type_label ?? "이행 사건"}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            {claim ? (
              <>
                <span>{OFFICIAL_ACCIDENT_TYPE_LABEL[claim.official_accident_type]}</span>
                <span aria-hidden>·</span>
                <span className="tnum">청구 {formatWonShort(claim.claim_amount)} 원</span>
              </>
            ) : (
              <span>{detail?.description ?? ""}</span>
            )}
            {detail?.contract_id ? (
              <>
                <span aria-hidden>·</span>
                <Link
                  href={`/contracts/${detail.contract_id}/manage`}
                  className="font-bold text-hug-blue hover:underline"
                >
                  계약 상세 보기
                </Link>
              </>
            ) : null}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {stage ? (
            <span className={cn("rounded-full px-3 py-1 text-xs font-bold", CLAIM_STAGE_TONE[stage])}>
              {CLAIM_STAGE_LABEL[stage]}
            </span>
          ) : null}
          {claim ? (
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-bold",
                SLA_STATUS_TONE[claim.sla.status as SlaStatus],
              )}
            >
              {SLA_STATUS_LABEL[claim.sla.status as SlaStatus]}
              {claim.sla.status !== "COMPLETED"
                ? ` · ${
                    claim.sla.remaining_seconds >= 0
                      ? `${formatRemaining(claim.sla.remaining_seconds)} 남음`
                      : `${formatRemaining(claim.sla.remaining_seconds)} 초과`
                  }`
                : ""}
            </span>
          ) : null}
        </div>
      </motion.div>

      {detail === null ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : (
        <>
          {/* 단계 Stepper */}
          {claim ? (
            <motion.div variants={fadeUp}>
              <Card className="rounded-2xl border-line shadow-card">
                <CardContent className="overflow-x-auto pt-6">
                  <ContractStepper
                    steps={stageFlow.map((step) => ({
                      label: CLAIM_STAGE_LABEL[step],
                      caption:
                        step === "HandoverCompleted" && !claim.handover_required ? "해당 없음" : undefined,
                    }))}
                    current={stepperCurrent}
                    className="min-w-[640px]"
                  />
                  {stage === "SupplementRequested" || stage === "OnHold" || stage === "Rejected" ? (
                    <p className="mt-3 text-xs font-semibold text-warning-700">
                      현재 {CLAIM_STAGE_LABEL[stage]} 상태 —{" "}
                      {stage === "Rejected"
                        ? "심사 결과 거절로 종결되었습니다."
                        : "요건이 해소되면 다음 단계로 진행합니다."}
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            </motion.div>
          ) : null}

          {/* 요약 지표 */}
          {claim ? (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              {[
                { label: "청구금액", value: `${formatWonShort(claim.claim_amount)} 원` },
                {
                  label: "승인금액",
                  value: claim.approved_amount ? `${formatWonShort(claim.approved_amount)} 원` : "심사 전",
                },
                {
                  label: "대위변제 지급액",
                  value: claim.paid_amount ? `${formatWonShort(claim.paid_amount)} 원` : "—",
                },
                {
                  label: "필수서류",
                  value: `${claim.document_summary.verified_or_waived}/${claim.document_summary.required} 검증`,
                },
              ].map((item) => (
                <motion.div key={item.label} variants={fadeUp}>
                  <Card className="h-full rounded-2xl border-line shadow-card">
                    <CardContent className="pt-6">
                      <p className="text-xs font-semibold text-muted-foreground">{item.label}</p>
                      <p className="mt-1 text-xl font-extrabold tnum">{item.value}</p>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          ) : null}

          <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-5">
            {/* 좌측 — 서류·신고 내용 */}
            <motion.div variants={fadeUp} className="flex flex-col gap-5 xl:col-span-3">
              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">신고 내용</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="rounded-xl bg-neutral-100 p-3.5 text-sm">
                    <p className="font-semibold">{detail.description}</p>
                    <p className="mt-1.5 text-xs text-muted-foreground tnum">
                      발생일 {formatDate(detail.occurred_date)} · 접수일 {formatDate(detail.created_at)}
                      {detail.deposit_amount ? ` · 신고 보증금 ${formatWonShort(detail.deposit_amount)} 원` : ""}
                    </p>
                  </div>
                </CardContent>
              </Card>

              {claim ? (
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between text-base font-extrabold">
                      청구 서류
                      <span className="text-xs font-semibold text-muted-foreground tnum">
                        검증·면제 {claim.document_summary.verified_or_waived} / 필수{" "}
                        {claim.document_summary.required}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-x-auto">
                    {claim.documents.length === 0 ? (
                      <p className="py-8 text-center text-sm text-muted-foreground">
                        요청된 서류가 없습니다. 우측에서 필수서류를 요청하세요.
                      </p>
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                            <th className="py-2 pr-2">서류</th>
                            <th className="px-2">상태</th>
                            <th className="px-2">제출일</th>
                            <th className="px-2 text-right">처리</th>
                          </tr>
                        </thead>
                        <tbody>
                          {claim.documents.map((doc) => (
                            <tr key={doc.document_id} className="border-b border-line/70 last:border-b-0">
                              <td className="py-2.5 pr-2">
                                <span className="font-semibold">
                                  {CLAIM_DOCUMENT_TYPE_LABEL[doc.document_type] ?? doc.document_type}
                                </span>
                                {doc.required ? (
                                  <span className="ml-1.5 rounded-full bg-danger-100 px-1.5 py-0.5 text-[10px] font-bold text-danger-600">
                                    필수
                                  </span>
                                ) : null}
                              </td>
                              <td className="px-2">
                                <span
                                  className={cn(
                                    "rounded-full px-2 py-0.5 text-xs font-bold",
                                    DOCUMENT_STATUS_TONE[doc.verification_status as ClaimDocumentStatus],
                                  )}
                                >
                                  {DOCUMENT_STATUS_LABEL[doc.verification_status as ClaimDocumentStatus]}
                                </span>
                              </td>
                              <td className="px-2 text-xs text-muted-foreground tnum">
                                {formatDate(doc.submitted_at)}
                              </td>
                              <td className="px-2 text-right">
                                {doc.verification_status === "Submitted" ? (
                                  <span className="flex justify-end gap-1">
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full px-2.5 text-xs"
                                      disabled={isActing}
                                      onClick={() => decideDocument(doc.document_id, "VERIFY")}
                                    >
                                      검증
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full px-2.5 text-xs text-danger-600"
                                      disabled={isActing}
                                      onClick={() => decideDocument(doc.document_id, "REJECT")}
                                    >
                                      반려
                                    </Button>
                                  </span>
                                ) : doc.verification_status === "Requested" ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full px-2.5 text-xs"
                                    disabled={isActing}
                                    onClick={() => decideDocument(doc.document_id, "WAIVE")}
                                  >
                                    면제
                                  </Button>
                                ) : null}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </CardContent>
                </Card>
              ) : null}

              {claim && claim.subrogation_payments.length > 0 ? (
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader>
                    <CardTitle className="text-base font-extrabold">대위변제 지급 내역</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                          <th className="py-2 pr-2">지급일</th>
                          <th className="px-2">지급 참조</th>
                          <th className="px-2 text-right">금액</th>
                        </tr>
                      </thead>
                      <tbody>
                        {claim.subrogation_payments.map((payment) => (
                          <tr key={payment.payment_id} className="border-b border-line/70 last:border-b-0">
                            <td className="py-2.5 pr-2 tnum">{formatDate(payment.paid_at)}</td>
                            <td className="px-2 font-mono text-xs text-muted-foreground">
                              {payment.payment_reference}
                            </td>
                            <td className="px-2 text-right font-bold tnum">
                              {formatWonShort(payment.paid_amount)} 원
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </CardContent>
                </Card>
              ) : null}
            </motion.div>

            {/* 우측 — 업무 액션 + 감사 타임라인 */}
            <motion.div variants={fadeUp} className="flex flex-col gap-5 xl:col-span-2">
              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">
                    {claim ? "다음 업무 액션" : "이행청구 접수"}
                  </CardTitle>
                </CardHeader>
                <CardContent>{renderActionPanel()}</CardContent>
              </Card>

              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">처리 이력</CardTitle>
                </CardHeader>
                <CardContent>
                  {events === null ? (
                    <Skeleton className="h-32 w-full" />
                  ) : events.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">기록된 이력이 없습니다.</p>
                  ) : (
                    <TimelineList
                      items={events
                        .slice()
                        .reverse()
                        .map((event) => ({
                          time: formatDateTime(event.occurred_at),
                          title: EVENT_ACTION_LABEL[event.action] ?? event.action,
                          trailing: event.reason ? (
                            <span className="max-w-40 truncate text-muted-foreground" title={event.reason}>
                              {event.reason}
                            </span>
                          ) : undefined,
                          level:
                            event.action === "CLAIM_REJECT" || event.action === "DOCUMENT_REJECT"
                              ? "danger"
                              : event.action === "CLAIM_APPROVE" ||
                                  event.action === "SUBROGATION_PAYMENT_RECORDED" ||
                                  event.action === "DOCUMENT_VERIFY"
                                ? "ok"
                                : "info",
                        }))}
                    />
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </div>
        </>
      )}
    </motion.div>
  );
}
