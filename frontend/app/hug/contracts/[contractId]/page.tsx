"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, ExternalLink, RefreshCw, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { hugContractService } from "@/services/hugContractService";
import { ApiError } from "@/services/apiClient";
import type { HugContractDetail } from "@/types/hugContract";
import { DonutGauge } from "@/components/viz/DonutGauge";
import { RiskSignalList, type RiskSignal } from "@/components/viz/RiskSignals";
import { TimelineList } from "@/components/viz/TimelineList";
import {
  BUNDLE_STATUS_LABEL,
  BUNDLE_STATUS_TONE,
  CHECKPOINT_LABEL,
  PREDICTION_STATUS_LABEL,
  PREVENTION_STATUS_LABEL,
  PREVENTION_STATUS_TONE,
  PREVENTIVE_ACTION_STATUS_LABEL,
  PREVENTIVE_ACTION_TYPE_LABEL,
  formatDate,
  formatDateTime,
  formatDday,
  formatWonShort,
  toWorkText,
  type BundleStatus,
  type PreventiveActionStatus,
  type PreventiveActionType,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const DETAIL_TABS = [
  { value: "risk", label: "위험·예측" },
  { value: "dday", label: "D-일정·증빙" },
  { value: "actions", label: "예방 조치" },
  { value: "notify", label: "3자 알림" },
  { value: "timeline", label: "변경 이력" },
] as const;

type DetailTab = (typeof DETAIL_TABS)[number]["value"];

const ACTION_TYPES: PreventiveActionType[] = [
  "EVIDENCE_REQUEST",
  "CREDIT_ENHANCEMENT_REQUEST",
  "CALLBACK",
  "MANUAL_REVIEW",
];

const TARGET_ROLES = [
  { value: "landlord", label: "임대인" },
  { value: "tenant", label: "임차인" },
  { value: "hug_admin", label: "HUG 담당" },
] as const;

const ROLE_LABEL: Record<"tenant" | "landlord" | "hug_admin", string> = {
  tenant: "임차인",
  landlord: "임대인",
  hug_admin: "HUG",
};

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

/** 사고 전 계약 상세 — 위험·예측, D-일정 증빙, 예방 조치, 3자 알림, 변경 이력. */
export default function HugContractDetailPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const [detail, setDetail] = useState<HugContractDetail | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("risk");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [actionType, setActionType] = useState<PreventiveActionType>("EVIDENCE_REQUEST");
  const [targetRole, setTargetRole] = useState<(typeof TARGET_ROLES)[number]["value"]>("landlord");
  const [actionNote, setActionNote] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  const load = useCallback(() => {
    hugContractService
      .get(contractId)
      .then((data) => {
        setDetail(data);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "계약 정보를 불러오지 못했습니다."),
      );
  }, [contractId]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshPrediction = () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    hugContractService
      .refreshPrediction(contractId)
      .then(() => {
        toast.success("사고위험을 다시 산정했습니다.");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "사고위험 재산정에 실패했습니다."),
      )
      .finally(() => setIsRefreshing(false));
  };

  const createAction = (event: React.FormEvent) => {
    event.preventDefault();
    if (isCreating) return;
    setIsCreating(true);
    hugContractService
      .createAction(contractId, {
        action_type: actionType,
        target_role: targetRole,
        note: actionNote || undefined,
      })
      .then(() => {
        toast.success("예방 조치를 등록하고 대상자에게 알림을 발송했습니다.");
        setActionNote("");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "예방 조치 등록에 실패했습니다."),
      )
      .finally(() => setIsCreating(false));
  };

  const prediction = detail?.prediction ?? null;
  const riskProbability = prediction?.accident_probability ?? prediction?.pu_risk_score ?? null;
  const riskPercentile = prediction?.risk_percentile ?? null;

  /** Rule 위험신호 → 신호등 리스트 변환. */
  const ruleSignals = useMemo<RiskSignal[]>(() => {
    const factors = detail?.rule_risk?.risk_factors ?? [];
    return factors.map((factor) => {
      const severity = String(factor.severity ?? "").toUpperCase();
      return {
        level: severity === "HIGH" ? "danger" : severity === "MED" || severity === "MEDIUM" ? "warn" : "info",
        title: String(factor.factor ?? factor.description ?? "위험 신호"),
        detail: factor.factor && factor.description ? String(factor.description) : undefined,
      };
    });
  }, [detail]);

  /** 우선순위 구성요소 — 알려진 4개 축만 0~1 비율로 표시하고 내부 키·가중치 항목은 걸러낸다. */
  const priorityComponents = useMemo(() => {
    const components = detail?.priority_components ?? {};
    const axes: { label: string; keys: string[] }[] = [
      { label: "사고위험", keys: ["risk_percentile", "risk", "risk_score"] },
      { label: "보증금 노출", keys: ["deposit_percentile", "deposit_exposure", "deposit"] },
      { label: "만기 긴급도", keys: ["maturity_urgency", "urgency", "d_day_urgency"] },
      { label: "미해소 조치", keys: ["unresolved_severity", "unresolved_actions", "unresolved"] },
    ];
    return axes
      .map((axis) => {
        const key = axis.keys.find((candidate) => typeof components[candidate] === "number");
        return key ? { label: axis.label, value: Math.min(1, Math.max(0, Number(components[key]))) } : null;
      })
      .filter((component): component is { label: string; value: number } => component !== null);
  }, [detail]);

  if (errorMessage) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-sm text-destructive">{errorMessage}</p>
        <Link href="/hug/contracts" className="text-sm font-bold text-hug-blue hover:underline">
          ← 계약 목록으로
        </Link>
      </div>
    );
  }

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      {/* 헤더 */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-start gap-3">
        <Link
          href="/hug/contracts"
          className="mt-1 flex size-9 items-center justify-center rounded-xl border border-line bg-card text-muted-foreground transition-colors hover:bg-neutral-100"
        >
          <ArrowLeft size={16} />
        </Link>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-extrabold tracking-tight">
            {detail?.address_summary ?? "계약 상세"}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>{detail?.guarantee_product ?? "—"}</span>
            <span aria-hidden>·</span>
            <span className="tnum">보증금 {detail?.deposit ? `${formatWonShort(detail.deposit)} 원` : "—"}</span>
            <span aria-hidden>·</span>
            <span className="tnum">
              계약기간 {formatDate(detail?.contract_start_date)} ~ {formatDate(detail?.contract_end_date)}
            </span>
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {detail?.prevention_case ? (
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-bold",
                PREVENTION_STATUS_TONE[detail.prevention_case.status],
              )}
            >
              {PREVENTION_STATUS_LABEL[detail.prevention_case.status]}
            </span>
          ) : null}
          <Button size="sm" variant="outline" className="rounded-full" disabled={isRefreshing} onClick={refreshPrediction}>
            <RefreshCw size={14} className={isRefreshing ? "animate-spin" : undefined} />
            {isRefreshing ? "재산정 중..." : "사고위험 재산정"}
          </Button>
          <Link
            href={`/contracts/${contractId}/manage`}
            className="flex items-center gap-1.5 rounded-full border border-line bg-card px-3.5 py-1.5 text-xs font-bold text-hug-blue transition-colors hover:bg-hug-sky"
          >
            <ExternalLink size={13} />
            공동 계약화면
          </Link>
        </div>
      </motion.div>

      {/* 상단 요약 카드 */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex flex-col items-center gap-1 pt-6 text-center">
              {detail === null ? (
                <Skeleton className="size-24 rounded-full" />
              ) : (
                <DonutGauge
                  ratio={riskPercentile ?? 0}
                  size={104}
                  strokeWidth={10}
                  color={
                    (riskPercentile ?? 0) >= 0.8
                      ? "var(--color-danger-500)"
                      : (riskPercentile ?? 0) >= 0.5
                        ? "var(--color-warning-500)"
                        : "var(--color-hug-green)"
                  }
                >
                  <b className="text-lg font-extrabold tnum">
                    {riskProbability != null ? `${(riskProbability * 100).toFixed(1)}%` : "—"}
                  </b>
                </DonutGauge>
              )}
              <p className="text-xs font-semibold text-muted-foreground">
                사고위험
                {riskPercentile != null
                  ? ` · 상위 ${Math.max(1, Math.round((1 - riskPercentile) * 100))}%`
                  : prediction
                    ? ` · ${PREDICTION_STATUS_LABEL[prediction.prediction_status]}`
                    : ""}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-center gap-1.5 pt-6">
              <p className="text-xs font-semibold text-muted-foreground">사전예방 우선순위</p>
              <p className="text-3xl font-extrabold text-hug-blue tnum">
                {detail ? detail.prevention_priority.toFixed(1) : "—"}
              </p>
              <div className="flex flex-col gap-1">
                {priorityComponents.map((component) => (
                  <div key={component.label} className="grid grid-cols-[72px_1fr] items-center gap-2 text-[11px]">
                    <span className="text-muted-foreground">{component.label}</span>
                    <span className="h-1.5 overflow-hidden rounded-full bg-neutral-200">
                      <i
                        className="block h-full rounded-full bg-hug-blue"
                        style={{ width: `${Math.min(100, component.value * 100)}%` }}
                      />
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-center gap-1.5 pt-6">
              <p className="text-xs font-semibold text-muted-foreground">만기 일정</p>
              <p
                className={cn(
                  "text-3xl font-extrabold tnum",
                  detail && detail.d_day <= 30 ? "text-danger-600" : detail && detail.d_day <= 90 ? "text-warning-700" : undefined,
                )}
              >
                {detail ? formatDday(detail.d_day) : "—"}
              </p>
              <p className="text-xs text-muted-foreground tnum">만기일 {formatDate(detail?.contract_end_date)}</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-center gap-1.5 pt-6">
              <p className="text-xs font-semibold text-muted-foreground">반환준비 증빙</p>
              <p className="text-3xl font-extrabold tnum">
                {detail
                  ? `${detail.evidence_bundle.verified_count}/${detail.evidence_bundle.required_count}`
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground">
                {detail && detail.evidence_bundle.required_count > 0
                  ? `${BUNDLE_STATUS_LABEL[detail.evidence_bundle.status as BundleStatus]}${
                      detail.evidence_bundle.overdue_count > 0
                        ? ` · 기한초과 ${detail.evidence_bundle.overdue_count}건`
                        : ""
                    }`
                  : "요청된 증빙 없음"}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* 다음 조치 배너 */}
      {detail?.next_action ? (
        <motion.div variants={fadeUp} className="rounded-2xl bg-hug-sky px-5 py-3.5">
          <p className="text-xs font-bold text-hug-navy">다음 조치</p>
          <p className="mt-0.5 text-sm font-semibold text-hug-navy">
            {toWorkText(detail.next_action)}
            {detail.prevention_case?.due_at ? (
              <span className="ml-2 text-xs font-bold text-hug-blue tnum">
                기한 {formatDate(detail.prevention_case.due_at)}
              </span>
            ) : null}
          </p>
        </motion.div>
      ) : null}

      {/* 탭 */}
      <motion.div variants={fadeUp}>
        <Tabs value={tab} onValueChange={(value) => setTab(value as DetailTab)}>
          <TabsList>
            {DETAIL_TABS.map((item) => (
              <TabsTrigger key={item.value} value={item.value}>
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </motion.div>

      {detail === null ? (
        <Skeleton className="h-72 w-full rounded-2xl" />
      ) : tab === "risk" ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                사고위험 주요 요인
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  산정일 {formatDate(prediction?.predicted_at)}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {prediction && prediction.top_factors.length > 0 ? (
                <ul className="flex flex-col gap-2.5">
                  {prediction.top_factors.map((factor) => {
                    const maxImportance = Math.max(
                      ...prediction.top_factors.map((f) => Math.abs(f.importance)),
                      0.0001,
                    );
                    return (
                      <li key={factor.feature} className="grid grid-cols-[96px_1fr_auto] items-center gap-3 text-sm">
                        <span className="truncate font-semibold">{factor.label}</span>
                        <span className="h-2.5 overflow-hidden rounded-full bg-neutral-200">
                          <motion.i
                            className="block h-full rounded-full bg-hug-blue"
                            initial={{ width: 0 }}
                            whileInView={{ width: `${(Math.abs(factor.importance) / maxImportance) * 100}%` }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                          />
                        </span>
                        <span className="text-xs text-muted-foreground tnum">
                          {factor.value != null ? String(factor.value) : ""}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  {prediction
                    ? prediction.prediction_status === "SUCCESS"
                      ? "요인 정보가 없습니다."
                      : `${PREDICTION_STATUS_LABEL[prediction.prediction_status]} — ${
                          prediction.failure_reason.join(", ") || "입력 데이터를 보완한 뒤 재산정하세요."
                        }`
                    : "아직 사고위험이 산정되지 않았습니다."}
                </p>
              )}
              {prediction ? (
                <div className="grid grid-cols-2 gap-2 rounded-xl bg-neutral-100 p-3 text-xs">
                  <span className="text-muted-foreground">데이터 완결성</span>
                  <b className="text-right tnum">{Math.round((prediction.data_completeness ?? 0) * 100)}%</b>
                  <span className="text-muted-foreground">유효기한</span>
                  <b className="text-right tnum">{formatDate(prediction.valid_until)}</b>
                </div>
              ) : null}

              {detail.prediction_history.length > 1 ? (
                <div>
                  <p className="mb-1.5 text-xs font-bold text-muted-foreground">산정 이력</p>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-line text-left font-bold text-muted-foreground">
                        <th className="py-1.5 pr-2">산정일</th>
                        <th className="px-2">위험도</th>
                        <th className="px-2">상대 위치</th>
                        <th className="px-2">상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.prediction_history.slice(0, 6).map((item) => (
                        <tr key={item.prediction_id} className="border-b border-line/70 last:border-b-0">
                          <td className="py-1.5 pr-2 tnum">{formatDateTime(item.predicted_at)}</td>
                          <td className="px-2 tnum">
                            {item.accident_probability != null
                              ? `${(item.accident_probability * 100).toFixed(1)}%`
                              : "—"}
                          </td>
                          <td className="px-2 tnum">
                            {item.risk_percentile != null
                              ? `상위 ${Math.max(1, Math.round((1 - item.risk_percentile) * 100))}%`
                              : "—"}
                          </td>
                          <td className="px-2">{PREDICTION_STATUS_LABEL[item.prediction_status]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                확인된 위험신호
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  등기·증빙·임대인 사실 기반
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {ruleSignals.length > 0 ? (
                <RiskSignalList signals={ruleSignals} />
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">확인된 위험신호가 없습니다.</p>
              )}
              {detail.prevention_case && detail.prevention_case.triggers.length > 0 ? (
                <div className="mt-4 rounded-xl bg-neutral-100 p-3">
                  <p className="mb-1 text-xs font-bold text-muted-foreground">예방 케이스 트리거</p>
                  <ul className="list-disc pl-4 text-xs text-muted-foreground">
                    {detail.prevention_case.triggers.map((trigger, index) => (
                      <li key={index}>
                        {toWorkText(String(trigger.reason ?? trigger.trigger ?? "")) || "위험 신호"}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </div>
      ) : tab === "dday" ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          {detail.evidence_bundles.length === 0 ? (
            <Card className="rounded-2xl border-line shadow-card xl:col-span-3">
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                아직 D-일정 점검이 시작되지 않았습니다. 목록 화면의 &ldquo;D-일정 예방 점검&rdquo;으로
                증빙 요청을 생성할 수 있습니다.
              </CardContent>
            </Card>
          ) : (
            detail.evidence_bundles.map((bundle) => (
              <Card key={bundle.evidence_bundle_id ?? bundle._id ?? bundle.checkpoint} className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="flex items-center justify-between text-base font-extrabold">
                    {CHECKPOINT_LABEL[bundle.checkpoint]} 체크포인트
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 text-xs font-bold",
                        BUNDLE_STATUS_TONE[bundle.status as BundleStatus],
                      )}
                    >
                      {BUNDLE_STATUS_LABEL[bundle.status as BundleStatus]}
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs text-muted-foreground tnum">
                    <span>기한 {formatDate(bundle.due_at)}</span>
                    <span>
                      검증 {bundle.verified_count}/{bundle.required_count}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-neutral-200">
                    <motion.i
                      className={cn(
                        "block h-full rounded-full",
                        bundle.status === "Overdue" ? "bg-danger-500" : "bg-hug-green",
                      )}
                      initial={{ width: 0 }}
                      whileInView={{ width: `${bundle.completion_ratio * 100}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.6 }}
                    />
                  </div>
                  <ul className="flex flex-col gap-2">
                    {bundle.items.map((item) => (
                      <li
                        key={item.item_key}
                        className="flex items-center gap-2 rounded-xl bg-neutral-100 px-3 py-2 text-xs"
                      >
                        <span
                          className={cn(
                            "size-2 shrink-0 rounded-full",
                            item.is_verified
                              ? "bg-hug-green"
                              : item.is_overdue
                                ? "bg-danger-500"
                                : "bg-warning-500",
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate font-semibold">{item.label}</span>
                        <span
                          className={cn(
                            "shrink-0",
                            item.is_verified
                              ? "text-hug-green-deep"
                              : item.is_overdue
                                ? "font-bold text-danger-600"
                                : "text-muted-foreground",
                          )}
                        >
                          {item.is_verified ? "검증 완료" : item.is_overdue ? "기한 초과" : "대기"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      ) : tab === "actions" ? (
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-3">
          <Card className="rounded-2xl border-line shadow-card xl:col-span-2">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">예방 조치 이력</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {detail.preventive_actions.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">등록된 예방 조치가 없습니다.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">조치</th>
                      <th className="px-2">대상</th>
                      <th className="px-2">상태</th>
                      <th className="px-2">요청일</th>
                      <th className="px-2">기한</th>
                      <th className="px-2">메모</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.preventive_actions.map((action) => (
                      <tr key={action.action_id ?? action._id} className="border-b border-line/70 last:border-b-0">
                        <td className="py-2.5 pr-2 font-semibold">
                          {PREVENTIVE_ACTION_TYPE_LABEL[action.action_type as PreventiveActionType] ??
                            action.action_type}
                        </td>
                        <td className="px-2">
                          {ROLE_LABEL[action.target_role as keyof typeof ROLE_LABEL] ?? action.target_role}
                        </td>
                        <td className="px-2">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-xs font-bold",
                              action.status === "Completed"
                                ? "bg-hug-mint text-hug-green-deep"
                                : action.status === "Overdue" || action.status === "Rejected"
                                  ? "bg-danger-100 text-danger-600"
                                  : "bg-hug-sky text-hug-blue",
                            )}
                          >
                            {PREVENTIVE_ACTION_STATUS_LABEL[action.status as PreventiveActionStatus] ??
                              action.status}
                          </span>
                        </td>
                        <td className="px-2 text-xs text-muted-foreground tnum">{formatDate(action.requested_at)}</td>
                        <td className="px-2 text-xs text-muted-foreground tnum">{formatDate(action.due_at)}</td>
                        <td className="max-w-40 truncate px-2 text-xs text-muted-foreground" title={action.note ?? ""}>
                          {action.note ?? "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">새 예방 조치</CardTitle>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-3" onSubmit={createAction}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="action-type">조치 유형</Label>
                  <select
                    id="action-type"
                    value={actionType}
                    onChange={(e) => setActionType(e.target.value as PreventiveActionType)}
                    className={inputClass}
                  >
                    {ACTION_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {PREVENTIVE_ACTION_TYPE_LABEL[type]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="action-role">대상</Label>
                  <select
                    id="action-role"
                    value={targetRole}
                    onChange={(e) => setTargetRole(e.target.value as (typeof TARGET_ROLES)[number]["value"])}
                    className={inputClass}
                  >
                    {TARGET_ROLES.map((role) => (
                      <option key={role.value} value={role.value}>
                        {role.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="action-note">메모</Label>
                  <textarea
                    id="action-note"
                    value={actionNote}
                    onChange={(e) => setActionNote(e.target.value)}
                    rows={3}
                    placeholder="요청 배경과 확인할 내용"
                    className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                  />
                </div>
                <Button type="submit" disabled={isCreating} className="rounded-xl font-bold">
                  <Send size={14} />
                  {isCreating ? "등록 중..." : "조치 등록 + 알림 발송"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      ) : tab === "notify" ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {(["tenant", "landlord", "hug_admin"] as const).map((role) => {
            const summary = detail.notification_status?.[role];
            return (
              <Card key={role} className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">{ROLE_LABEL[role]}</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-xl bg-neutral-100 p-3">
                      <p className="text-[11px] font-semibold text-muted-foreground">발송</p>
                      <p className="text-xl font-extrabold tnum">{summary?.sent_count ?? 0}</p>
                    </div>
                    <div className="rounded-xl bg-neutral-100 p-3">
                      <p className="text-[11px] font-semibold text-muted-foreground">읽음</p>
                      <p className="text-xl font-extrabold tnum">{summary?.read_count ?? 0}</p>
                    </div>
                    <div className="rounded-xl bg-neutral-100 p-3">
                      <p className="text-[11px] font-semibold text-muted-foreground">업무 확인</p>
                      <p className="text-xl font-extrabold tnum">{summary?.acknowledged_count ?? 0}</p>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground tnum">
                    최근 발송 {summary?.latest_sent_at ? formatDateTime(summary.latest_sent_at) : "—"}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader>
            <CardTitle className="text-base font-extrabold">계약·증빙·예측 변경 이력</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.timeline.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">기록된 이력이 없습니다.</p>
            ) : (
              <TimelineList
                items={detail.timeline.map((entry) => ({
                  time: formatDateTime(String(entry.at ?? entry.created_at ?? "")),
                  title: String(entry.description ?? entry.event ?? "이벤트"),
                }))}
              />
            )}
          </CardContent>
        </Card>
      )}
    </motion.div>
  );
}
