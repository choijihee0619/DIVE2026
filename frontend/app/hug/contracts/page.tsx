"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { BellRing, FileText, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { hugContractService } from "@/services/hugContractService";
import { ApiError } from "@/services/apiClient";
import type { HugDataMode } from "@/services/hugDataMode";
import type { HugContractItem } from "@/types/hugContract";
import {
  BUNDLE_STATUS_LABEL,
  BUNDLE_STATUS_TONE,
  PREVENTION_STATUS_LABEL,
  PREVENTION_STATUS_TONE,
  formatDday,
  formatWonShort,
  toWorkText,
  type BundleStatus,
  type PreventionStatus,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const FILTER_TABS = [
  { value: "all", label: "전체" },
  { value: "high_risk", label: "고위험" },
  { value: "D90", label: "D-90" },
  { value: "D60", label: "D-60" },
  { value: "D30", label: "D-30" },
  { value: "maturity", label: "만기경과" },
  { value: "overdue", label: "증빙 기한초과" },
  { value: "action", label: "조치 필요" },
] as const;

type FilterValue = (typeof FILTER_TABS)[number]["value"];

const ACTION_NEEDED: PreventionStatus[] = [
  "RiskDetected",
  "Notified",
  "ActionRequested",
  "Verifying",
  "Overdue",
  "EscalatedMonitoring",
];

/** 사고위험 셀 — 위험도·상대 위치를 업무 표현으로만 표시한다. */
function RiskCell({ contract }: { contract: HugContractItem }) {
  const prediction = contract.prediction;
  if (!prediction) return <span className="text-xs text-muted-foreground">미산정</span>;
  if (prediction.prediction_status === "NOT_SCORABLE")
    return <span className="text-xs text-muted-foreground">산정 불가</span>;
  if (prediction.prediction_status === "FAILED")
    return <span className="text-xs text-danger-600">산정 실패</span>;
  const probability = prediction.accident_probability ?? prediction.pu_risk_score ?? 0;
  const topPct = prediction.risk_percentile != null ? Math.max(1, Math.round((1 - prediction.risk_percentile) * 100)) : null;
  const highRisk = (prediction.risk_percentile ?? 0) >= 0.8;
  return (
    <span className="flex flex-col">
      <b className={cn("tnum", highRisk ? "text-danger-600" : undefined)}>
        {(probability * 100).toFixed(1)}%
      </b>
      {topPct != null ? (
        <span className="text-[11px] text-muted-foreground tnum">상위 {topPct}%</span>
      ) : null}
    </span>
  );
}

/** 사고 전 계약관리 — 사전예방 우선순위 정렬 계약 목록과 일괄 예방 액션. */
export default function HugContractsPage() {
  const router = useRouter();
  const [contracts, setContracts] = useState<HugContractItem[] | null>(null);
  const [dataMode, setDataMode] = useState<HugDataMode>("LIVE");
  const [filter, setFilter] = useState<FilterValue>("all");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSweeping, setIsSweeping] = useState(false);

  const load = useCallback(() => {
    hugContractService
      .listWithFallback({ size: 400 })
      .then(({ data, mode }) => {
        setContracts(data.items);
        setDataMode(mode);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "계약 목록을 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** 사고위험 일괄 재산정 — 사고 전 전체 계약을 최신 입력으로 다시 평가한다. */
  const refreshAll = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    hugContractService
      .refreshPredictions(dataMode)
      .then(() => {
        toast.success("사고위험 재산정을 완료했습니다.");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "사고위험 재산정에 실패했습니다."),
      )
      .finally(() => setIsRefreshing(false));
  };

  /** D-90/60/30 예방 점검 — 기한 도래 계약의 증빙요청·3자 알림을 생성한다. */
  const runSweep = () => {
    if (isSweeping) return;
    setIsSweeping(true);
    hugContractService
      .sweep(dataMode)
      .then(() => {
        toast.success("D-일정 예방 점검을 완료했습니다.");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "예방 점검에 실패했습니다."),
      )
      .finally(() => setIsSweeping(false));
  };

  const visible = useMemo(() => {
    if (!contracts) return null;
    switch (filter) {
      case "high_risk":
        return contracts.filter((c) => (c.prediction?.risk_percentile ?? 0) >= 0.8);
      case "D90":
      case "D60":
      case "D30":
        return contracts.filter((c) => c.d_day_stage === filter);
      case "maturity":
        // §20.5 P4 — 만기경과·사고요건 확인 스테이지
        return contracts.filter((c) => c.d_day_stage === "OVERDUE" || c.d_day < 0);
      case "overdue":
        return contracts.filter((c) => c.evidence_bundle.overdue_count > 0);
      case "action":
        return contracts.filter(
          (c) => c.prevention_case && ACTION_NEEDED.includes(c.prevention_case.status),
        );
      default:
        return contracts;
    }
  }, [contracts, filter]);

  const stats = useMemo(() => {
    const items = contracts ?? [];
    return {
      total: items.length,
      highRisk: items.filter((c) => (c.prediction?.risk_percentile ?? 0) >= 0.8).length,
      maturity: items.filter((c) => c.d_day_stage === "OVERDUE" || c.d_day < 0).length,
      overdue: items.filter((c) => c.evidence_bundle.overdue_count > 0).length,
      action: items.filter((c) => c.prevention_case && ACTION_NEEDED.includes(c.prevention_case.status))
        .length,
    };
  }, [contracts]);

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
            <FileText size={22} className="text-hug-blue" />
            사고 전 계약관리
          </h1>
          <p className="mt-1.5 text-muted-foreground">
            사고접수 전 진행 계약 {stats.total}건 — 사고위험과 만기 일정, 미해소 조치를 결합한 사전예방
            우선순위로 오늘 관리할 계약부터 보여줍니다.
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="rounded-full"
            disabled={isRefreshing}
            onClick={refreshAll}
          >
            <RefreshCw size={14} className={isRefreshing ? "animate-spin" : undefined} />
            {isRefreshing ? "재산정 중..." : "사고위험 일괄 재산정"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="rounded-full"
            disabled={isSweeping}
            onClick={runSweep}
          >
            <BellRing size={14} />
            {isSweeping ? "점검 중..." : "D-일정 예방 점검"}
          </Button>
        </div>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      {/* 요약 배지 */}
      <motion.div variants={fadeUp} className="flex flex-wrap gap-1.5">
        <span className="rounded-full bg-hug-sky px-3 py-1 text-xs font-bold text-hug-navy tnum">
          관리 대상 {stats.total}건
        </span>
        <span className="rounded-full bg-danger-100 px-3 py-1 text-xs font-bold text-danger-600 tnum">
          고위험 {stats.highRisk}건
        </span>
        <span className="rounded-full bg-danger-100 px-3 py-1 text-xs font-bold text-danger-600 tnum">
          만기경과 {stats.maturity}건
        </span>
        <span className="rounded-full bg-warning-100 px-3 py-1 text-xs font-bold text-warning-700 tnum">
          증빙 기한초과 {stats.overdue}건
        </span>
        <span className="rounded-full bg-hug-mint px-3 py-1 text-xs font-bold text-hug-green-deep tnum">
          조치 진행 {stats.action}건
        </span>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-base font-extrabold">
                사전예방 계약 목록
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  사전예방 우선순위 내림차순
                </span>
              </CardTitle>
            </div>
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
            {visible === null ? (
              <Skeleton className="h-64 w-full" />
            ) : visible.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                {filter === "all" ? "관리 대상 계약이 없습니다." : "조건에 해당하는 계약이 없습니다."}
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                    <th className="py-2 pr-2">계약·주소</th>
                    <th className="px-2">보증금</th>
                    <th className="px-2">만기</th>
                    <th className="px-2">사고위험</th>
                    <th className="px-2 text-right">예방 우선순위</th>
                    <th className="px-2">예방상태</th>
                    <th className="px-2">증빙</th>
                    <th className="px-2">3자 알림</th>
                    <th className="px-2">다음 조치</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((contract, index) => {
                    const bundle = contract.evidence_bundle;
                    const notifications = contract.notification_status;
                    const totalSent =
                      (notifications?.tenant?.sent_count ?? 0) +
                      (notifications?.landlord?.sent_count ?? 0) +
                      (notifications?.hug_admin?.sent_count ?? 0);
                    const dDayUrgent = contract.d_day <= 30;
                    return (
                      <motion.tr
                        key={contract.contract_id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(index, 12) * 0.04, duration: 0.3 }}
                        onClick={() => router.push(`/hug/contracts/${contract.contract_id}`)}
                        className="cursor-pointer border-b border-line/70 transition-colors last:border-b-0 hover:bg-neutral-100"
                      >
                        <td className="max-w-52 py-3 pr-2">
                          <span className="block truncate font-semibold" title={contract.address_summary ?? ""}>
                            {contract.address_summary ?? contract.contract_id}
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            {contract.guarantee_product}
                          </span>
                        </td>
                        <td className="px-2 tnum">
                          {contract.deposit ? formatWonShort(contract.deposit) : "—"}
                        </td>
                        <td className="px-2">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-bold tnum",
                              dDayUrgent
                                ? "bg-danger-100 text-danger-600"
                                : contract.d_day <= 90
                                  ? "bg-warning-100 text-warning-700"
                                  : "bg-neutral-200 text-neutral-600",
                            )}
                          >
                            {formatDday(contract.d_day)}
                          </span>
                        </td>
                        <td className="px-2">
                          <RiskCell contract={contract} />
                        </td>
                        <td className="px-2 text-right text-base font-extrabold tnum">
                          {contract.prevention_priority.toFixed(1)}
                        </td>
                        <td className="px-2">
                          {contract.prevention_case ? (
                            <span
                              className={cn(
                                "whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold",
                                PREVENTION_STATUS_TONE[contract.prevention_case.status],
                              )}
                            >
                              {PREVENTION_STATUS_LABEL[contract.prevention_case.status]}
                            </span>
                          ) : (
                            <span className="whitespace-nowrap rounded-full bg-neutral-200 px-2 py-0.5 text-xs font-bold text-neutral-600">
                              모니터링
                            </span>
                          )}
                        </td>
                        <td className="px-2">
                          {bundle.required_count > 0 ? (
                            <span className="flex flex-col">
                              <span
                                className={cn(
                                  "w-fit whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-bold",
                                  BUNDLE_STATUS_TONE[bundle.status as BundleStatus],
                                )}
                              >
                                {BUNDLE_STATUS_LABEL[bundle.status as BundleStatus]}
                              </span>
                              <span className="mt-0.5 text-[11px] text-muted-foreground tnum">
                                검증 {bundle.verified_count}/{bundle.required_count}
                                {bundle.overdue_count > 0 ? ` · 초과 ${bundle.overdue_count}` : ""}
                              </span>
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="px-2 text-xs text-muted-foreground tnum">
                          {totalSent > 0 ? `${totalSent}건 발송` : "—"}
                        </td>
                        <td className="max-w-40 px-2">
                          <span
                            className="block truncate text-xs font-semibold"
                            title={toWorkText(contract.next_action)}
                          >
                            {toWorkText(contract.next_action) || "정상 모니터링"}
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
