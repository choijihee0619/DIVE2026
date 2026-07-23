"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Siren } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { performanceClaimService } from "@/services/performanceClaimService";
import { ApiError } from "@/services/apiClient";
import type { HugIncidentRow } from "@/types/performanceClaim";
import {
  CLAIM_STAGE_LABEL,
  CLAIM_STAGE_TONE,
  SLA_STATUS_LABEL,
  SLA_STATUS_TONE,
  formatDate,
  formatRemaining,
  formatWonShort,
  type PerformanceClaimStage,
  type SlaStatus,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const FILTER_TABS = [
  { value: "all", label: "전체" },
  { value: "notified", label: "신규 사고통지" },
  { value: "supplement", label: "보완대기" },
  { value: "review", label: "심사중" },
  { value: "handover", label: "명도" },
  { value: "paid", label: "대위변제" },
  { value: "registered", label: "채권등록·인계" },
  { value: "closed", label: "거절·종결" },
] as const;

type FilterValue = (typeof FILTER_TABS)[number]["value"];

function stageOf(row: HugIncidentRow): PerformanceClaimStage | null {
  return (row.performance_claim?.stage as PerformanceClaimStage) ?? null;
}

function matchesFilter(row: HugIncidentRow, filter: FilterValue): boolean {
  const stage = stageOf(row);
  switch (filter) {
    case "notified":
      return !stage && row.status === "Received";
    case "supplement":
      return stage === "SupplementRequested";
    case "review":
      return stage === "ClaimReceived" || stage === "UnderReview" || stage === "OnHold";
    case "handover":
      return stage === "Approved" || stage === "HandoverScheduled" || stage === "HandoverCompleted";
    case "paid":
      return stage === "SubrogationPaid";
    case "registered":
      return stage === "RecoveryClaimRegistered" || stage === "TransferredToRecovery";
    case "closed":
      return stage === "Rejected" || (!stage && row.status === "Closed");
    default:
      return true;
  }
}

/** 현재 행에서 담당자가 해야 할 다음 액션 한 가지. */
function nextActionOf(row: HugIncidentRow): string {
  const stage = stageOf(row);
  if (!stage) return row.status === "Received" ? "이행청구 접수" : "—";
  switch (stage) {
    case "ClaimReceived":
      return "필수서류 확인·심사 시작";
    case "SupplementRequested":
      return "보완서류 확인";
    case "UnderReview":
      return "심사 결정";
    case "OnHold":
      return "유보 사유 해소 확인";
    case "Approved":
      return "명도 일정 등록";
    case "HandoverScheduled":
      return "명도 완료 확인";
    case "HandoverCompleted":
      return "대위변제 지급";
    case "SubrogationPaid":
      return "구상채권 등록";
    case "RecoveryClaimRegistered":
      return "채권관리 인계";
    case "TransferredToRecovery":
      return "인계 완료";
    case "Rejected":
      return "종결";
    default:
      return "—";
  }
}

/** 사고접수·보증이행 큐 — 사고통지부터 채권등록·인계까지 단계·기한 중심 업무 목록. */
export default function HugIncidentsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<HugIncidentRow[] | null>(null);
  const [filter, setFilter] = useState<FilterValue>("all");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    performanceClaimService
      .listIncidents({ size: 100 })
      .then((data) => {
        setRows(data.items);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "사고 큐를 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(
    () => (rows ?? []).filter((row) => matchesFilter(row, filter)),
    [rows, filter],
  );

  const counts = useMemo(() => {
    const map = new Map<FilterValue, number>();
    for (const tab of FILTER_TABS) {
      map.set(tab.value, (rows ?? []).filter((row) => matchesFilter(row, tab.value)).length);
    }
    return map;
  }, [rows]);

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
            <Siren size={22} className="text-danger-500" />
            사고접수·보증이행
          </h1>
          <p className="mt-1.5 text-muted-foreground">
            임차인 사고통지부터 이행청구, 서류·심사, 명도, 대위변제, 구상채권 등록·인계까지 단계별로
            처리합니다.
          </p>
        </div>
        <div className="ml-auto flex flex-wrap gap-1.5">
          <span className="rounded-full bg-danger-100 px-2.5 py-1 text-xs font-bold text-danger-600 tnum">
            신규 통지 {counts.get("notified") ?? 0}
          </span>
          <span className="rounded-full bg-warning-100 px-2.5 py-1 text-xs font-bold text-warning-700 tnum">
            심사 대기 {counts.get("review") ?? 0}
          </span>
          <span className="rounded-full bg-hug-sky px-2.5 py-1 text-xs font-bold text-hug-blue tnum">
            명도 {counts.get("handover") ?? 0}
          </span>
          <span className="rounded-full bg-hug-mint px-2.5 py-1 text-xs font-bold text-hug-green-deep tnum">
            대위변제 {counts.get("paid") ?? 0}
          </span>
        </div>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-col gap-3">
            <CardTitle className="text-base font-extrabold">
              이행 사건 목록 {rows ? `· ${visible.length}건` : ""}
            </CardTitle>
            <Tabs value={filter} onValueChange={(value) => setFilter(value as FilterValue)}>
              <TabsList>
                {FILTER_TABS.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value}>
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            {rows === null ? (
              <Skeleton className="h-64 w-full" />
            ) : visible.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                {filter === "all" ? "접수된 사고가 없습니다." : "해당 단계의 사건이 없습니다."}
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                    <th className="py-2 pr-2">사고유형</th>
                    <th className="px-2">청구·보증금</th>
                    <th className="px-2">현재 단계</th>
                    <th className="px-2">처리 기한</th>
                    <th className="px-2">접수일</th>
                    <th className="px-2">다음 액션</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row, index) => {
                    const claim = row.performance_claim;
                    const stage = stageOf(row);
                    return (
                      <motion.tr
                        key={row.incident_id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(index, 12) * 0.04, duration: 0.3 }}
                        onClick={() => router.push(`/hug/incidents/${row.incident_id}`)}
                        className="cursor-pointer border-b border-line/70 transition-colors last:border-b-0 hover:bg-neutral-100"
                      >
                        <td className="max-w-44 py-3 pr-2">
                          <span className="block truncate font-semibold" title={row.description}>
                            {row.incident_type_label}
                          </span>
                          {row.address_summary ? (
                            <span className="block truncate text-[11px] text-muted-foreground">
                              {row.address_summary}
                            </span>
                          ) : row.contract_id ? (
                            <span className="font-mono text-[11px] text-muted-foreground">
                              {row.contract_id.slice(0, 14)}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-2 tnum">
                          {claim
                            ? `청구 ${formatWonShort(claim.claim_amount)}`
                            : row.deposit_amount
                              ? `신고 ${formatWonShort(row.deposit_amount)}`
                              : "—"}
                        </td>
                        <td className="px-2">
                          {stage ? (
                            <span
                              className={cn(
                                "whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold",
                                CLAIM_STAGE_TONE[stage],
                              )}
                            >
                              {CLAIM_STAGE_LABEL[stage]}
                            </span>
                          ) : (
                            <span
                              className={cn(
                                "whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold",
                                row.status === "Received"
                                  ? "bg-danger-100 text-danger-600"
                                  : "bg-neutral-200 text-neutral-600",
                              )}
                            >
                              {row.status === "Received" ? "사고통지 접수" : "통지 종결"}
                            </span>
                          )}
                        </td>
                        <td className="px-2">
                          {claim ? (
                            <span className="flex flex-col">
                              <span
                                className={cn(
                                  "w-fit whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold",
                                  SLA_STATUS_TONE[claim.sla.status as SlaStatus],
                                )}
                              >
                                {SLA_STATUS_LABEL[claim.sla.status as SlaStatus]}
                              </span>
                              {claim.sla.status !== "COMPLETED" ? (
                                <span className="mt-0.5 text-[11px] text-muted-foreground tnum">
                                  {claim.sla.remaining_seconds >= 0
                                    ? `${formatRemaining(claim.sla.remaining_seconds)} 남음`
                                    : `${formatRemaining(claim.sla.remaining_seconds)} 초과`}
                                </span>
                              ) : null}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-2 text-xs text-muted-foreground tnum">{formatDate(row.created_at)}</td>
                        <td className="max-w-36 px-2">
                          <span className="block truncate text-xs font-semibold text-hug-blue">
                            {nextActionOf(row)}
                          </span>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
