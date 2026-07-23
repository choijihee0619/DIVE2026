"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { ArrowLeft, Lock, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { recoveryService } from "@/services/recoveryService";
import { ApiError } from "@/services/apiClient";
import type { RecoveryClaimDetail } from "@/types/recovery";
import { TimelineList } from "@/components/viz/TimelineList";
import {
  AUCTION_STATUS_LABEL,
  BALANCE_STATUS_LABEL,
  CLOSE_REASON_LABEL,
  COLLECTION_ROUTE_LABEL,
  LEDGER_COMPONENT_LABEL,
  LEDGER_ENTRY_IS_ACCRUAL,
  LEDGER_ENTRY_TYPE_LABEL,
  LEGAL_STATUS_LABEL,
  RECOVERY_STAGE_FLOW,
  RECOVERY_STAGE_LABEL,
  REPAYMENT_PLAN_STATUS_LABEL,
  formatDate,
  formatDateTime,
  formatWonShort,
  type CloseReason,
  type LedgerEntryType,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const DETAIL_TABS = [
  { value: "ledger", label: "채권원장" },
  { value: "cases", label: "법무·경공매" },
  { value: "predictions", label: "예측 이력" },
  { value: "history", label: "진행 이력" },
] as const;

type DetailTab = (typeof DETAIL_TABS)[number]["value"];

const GRADE_PILL: Record<string, string> = {
  HIGH: "bg-hug-mint text-hug-green-deep",
  MED: "bg-warning-100 text-warning-700",
  LOW: "bg-danger-100 text-danger-600",
};

const RECEIPT_TYPES: LedgerEntryType[] = ["RECEIPT", "DIVIDEND_RECEIPT"];
const ACCRUAL_TYPES: LedgerEntryType[] = [
  "LEGAL_COST_ACCRUAL",
  "DELAY_DAMAGE_ACCRUAL",
  "ENFORCEMENT_COST_ACCRUAL",
];

const CLOSE_REASONS: CloseReason[] = [
  "FULL_RECOVERY",
  "SOLD",
  "WRITTEN_OFF",
  "INSOLVENCY_DISCHARGE",
  "LEGAL_EXPIRY",
  "OTHER_APPROVED",
];

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none tnum placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

/** 등록채권 상세 — 병렬 상태축, append-only 원장, 법무·경공매 사건, 예측 이력, 종결. */
export default function RecoveryClaimDetailPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const [detail, setDetail] = useState<RecoveryClaimDetail | null>(null);
  const [tab, setTab] = useState<DetailTab>("ledger");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isActing, setIsActing] = useState(false);

  /* 원장 입력 폼 */
  const [entryType, setEntryType] = useState<LedgerEntryType>("RECEIPT");
  const [entryAmount, setEntryAmount] = useState("");
  const [entryComponent, setEntryComponent] = useState("principal");
  const [entryNote, setEntryNote] = useState("");

  /* 종결 폼 */
  const [closeReason, setCloseReason] = useState<CloseReason>("FULL_RECOVERY");
  const [closeNote, setCloseNote] = useState("");

  const load = useCallback(() => {
    recoveryService
      .detail(claimId)
      .then((data) => {
        setDetail(data);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "채권 정보를 불러오지 못했습니다."),
      );
  }, [claimId]);

  useEffect(() => {
    load();
  }, [load]);

  const claim = detail?.claim ?? null;
  const isClosed = claim?.is_closed ?? false;

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

  const addLedgerEntry = (event: React.FormEvent) => {
    event.preventDefault();
    const amount = Number(entryAmount) || 0;
    const isAccrual = LEDGER_ENTRY_IS_ACCRUAL[entryType];
    runAction(
      () =>
        recoveryService.addLedgerEntry(claimId, {
          entry_type: entryType,
          amount_won: amount,
          allocations: isAccrual ? {} : { [entryComponent]: amount },
          note: entryNote || undefined,
        }),
      "원장에 기록했습니다.",
    );
    setEntryAmount("");
    setEntryNote("");
  };

  const axes = useMemo(() => {
    if (!claim) return [];
    const axisStatus = claim.axis_status ?? {};
    return [
      {
        label: "회수단계",
        value:
          RECOVERY_STAGE_LABEL[(axisStatus.recovery_stage ?? claim.recovery_stage ?? "Registered")] ??
          "채권 등록",
        active: true,
      },
      {
        label: "회수경로",
        value: COLLECTION_ROUTE_LABEL[axisStatus.collection_route ?? claim.collection_route ?? "None"],
        active: (axisStatus.collection_route ?? claim.collection_route ?? "None") !== "None",
      },
      {
        label: "법무",
        value: LEGAL_STATUS_LABEL[axisStatus.legal_status ?? claim.legal_status ?? "None"],
        active: (axisStatus.legal_status ?? claim.legal_status ?? "None") !== "None",
      },
      {
        label: "경·공매",
        value: AUCTION_STATUS_LABEL[axisStatus.auction_status ?? claim.auction_status ?? "None"],
        active: (axisStatus.auction_status ?? claim.auction_status ?? "None") !== "None",
      },
      {
        label: "상환약정",
        value:
          REPAYMENT_PLAN_STATUS_LABEL[
            axisStatus.repayment_plan_status ?? claim.repayment_plan_status ?? "None"
          ],
        active: (axisStatus.repayment_plan_status ?? claim.repayment_plan_status ?? "None") !== "None",
      },
      {
        label: "잔액",
        value: BALANCE_STATUS_LABEL[axisStatus.balance_status ?? claim.balance_status ?? "Unrecovered"],
        active: true,
      },
    ];
  }, [claim]);

  const currentStageIndex = useMemo(() => {
    const stage = claim?.axis_status?.recovery_stage ?? claim?.recovery_stage ?? "Registered";
    const index = RECOVERY_STAGE_FLOW.indexOf(stage);
    return index >= 0 ? index : 0;
  }, [claim]);

  const latestPrediction = claim?.latest_prediction ?? null;

  if (errorMessage) {
    return (
      <div className="flex flex-col items-start gap-4">
        <p className="text-sm text-destructive">{errorMessage}</p>
        <Link href="/hug/recovery" className="text-sm font-bold text-hug-blue hover:underline">
          ← 채권관리로
        </Link>
      </div>
    );
  }

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      {/* 헤더 */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-start gap-3">
        <Link
          href="/hug/recovery"
          className="mt-1 flex size-9 items-center justify-center rounded-xl border border-line bg-card text-muted-foreground transition-colors hover:bg-neutral-100"
        >
          <ArrowLeft size={16} />
        </Link>
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold tracking-tight">{claim?.claim_type_label ?? "채권 상세"}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>{claim?.product_name_label ?? "—"}</span>
            <span aria-hidden>·</span>
            <span className="tnum">채권 발생일 {formatDate(claim?.incurred_date ?? claim?.created_at)}</span>
            {claim?.performance_claim_id ? (
              <>
                <span aria-hidden>·</span>
                <span className="font-mono text-xs">{String(claim.performance_claim_id).slice(0, 12)}</span>
              </>
            ) : null}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {isClosed ? (
            <span className="flex items-center gap-1 rounded-full bg-neutral-200 px-3 py-1 text-xs font-bold text-neutral-600">
              <Lock size={12} />
              종결 ·{" "}
              {claim?.closure?.reason
                ? CLOSE_REASON_LABEL[claim.closure.reason as CloseReason] ?? claim.closure.reason
                : "보관"}
            </span>
          ) : (
            <Button
              size="sm"
              variant="outline"
              className="rounded-full"
              disabled={isActing}
              onClick={() =>
                runAction(() => recoveryService.predict(claimId), "회수전망을 다시 산정했습니다.")
              }
            >
              <RefreshCw size={14} />
              회수전망 재산정
            </Button>
          )}
        </div>
      </motion.div>

      {detail === null ? (
        <Skeleton className="h-96 w-full rounded-2xl" />
      ) : (
        <>
          {/* 잔액·예측 요약 */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            {[
              { label: "잔존 원금", value: claim!.balances.principal },
              { label: "법무비용", value: claim!.balances.legal_cost },
              { label: "지연배상금", value: claim!.balances.delay_damage },
              { label: "집행비용", value: claim!.balances.enforcement_cost },
            ].map((item) => (
              <motion.div key={item.label} variants={fadeUp}>
                <Card className="h-full rounded-2xl border-line shadow-card">
                  <CardContent className="pt-6">
                    <p className="text-xs font-semibold text-muted-foreground">{item.label}</p>
                    <p className="mt-1 text-xl font-extrabold tnum">{formatWonShort(item.value)} 원</p>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
            <motion.div variants={fadeUp}>
              <Card className="h-full rounded-2xl border-hug-blue/40 bg-hug-sky/40 shadow-card">
                <CardContent className="pt-6">
                  <p className="text-xs font-semibold text-hug-navy">총 잔존 채권액</p>
                  <p className="mt-1 text-xl font-extrabold text-hug-navy tnum">
                    {formatWonShort(claim!.balances.total)} 원
                  </p>
                  {latestPrediction ? (
                    <p className="mt-0.5 text-[11px] text-hug-navy/70 tnum">
                      예상 회수 {formatWonShort(latestPrediction.expected_recovery_on_current_balance_won)} 원 (
                      {(latestPrediction.pred_recovery_ratio * 100).toFixed(0)}%)
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {/* 병렬 상태축 */}
          <motion.div variants={fadeUp}>
            <Card className="rounded-2xl border-line shadow-card">
              <CardContent className="pt-6">
                <div className="mb-4 flex items-center gap-1.5 overflow-x-auto">
                  {RECOVERY_STAGE_FLOW.map((stage, index) => (
                    <span
                      key={stage}
                      className={cn(
                        "whitespace-nowrap rounded-full px-3 py-1 text-xs font-bold",
                        index === currentStageIndex
                          ? "bg-hug-navy text-white"
                          : index < currentStageIndex
                            ? "bg-hug-mint text-hug-green-deep"
                            : "bg-neutral-200 text-neutral-500",
                      )}
                    >
                      {RECOVERY_STAGE_LABEL[stage]}
                    </span>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                  {axes.map((axis) => (
                    <div key={axis.label} className="rounded-xl bg-neutral-100 p-3 text-center">
                      <p className="text-[11px] font-semibold text-muted-foreground">{axis.label}</p>
                      <p
                        className={cn(
                          "mt-0.5 text-sm font-bold",
                          axis.active ? "text-ink" : "text-neutral-400",
                        )}
                      >
                        {axis.value}
                      </p>
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-[11px] text-muted-foreground">
                  법무·경공매·상환약정은 병행될 수 있어 별도 축으로 관리합니다.
                </p>
              </CardContent>
            </Card>
          </motion.div>

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

          {tab === "ledger" ? (
            <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-3">
              <Card className="rounded-2xl border-line shadow-card xl:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">
                    채권원장
                    <span className="ml-2 text-xs font-semibold text-muted-foreground">
                      입금·배당은 구성항목별로 명시 충당됩니다
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  {detail.ledger_entries.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">원장 기록이 없습니다.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                          <th className="py-2 pr-2">일시</th>
                          <th className="px-2">구분</th>
                          <th className="px-2 text-right">금액</th>
                          <th className="px-2">충당 내역</th>
                          <th className="px-2">메모</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.ledger_entries.map((entry, index) => {
                          const isAccrual =
                            LEDGER_ENTRY_IS_ACCRUAL[entry.entry_type as LedgerEntryType] ?? true;
                          return (
                            <tr key={entry._id ?? index} className="border-b border-line/70 last:border-b-0">
                              <td className="py-2.5 pr-2 text-xs text-muted-foreground tnum">
                                {formatDateTime(entry.occurred_at)}
                              </td>
                              <td className="px-2">
                                <span
                                  className={cn(
                                    "whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold",
                                    isAccrual ? "bg-warning-100 text-warning-700" : "bg-hug-mint text-hug-green-deep",
                                  )}
                                >
                                  {LEDGER_ENTRY_TYPE_LABEL[entry.entry_type as LedgerEntryType] ??
                                    entry.entry_type}
                                </span>
                              </td>
                              <td
                                className={cn(
                                  "px-2 text-right font-bold tnum",
                                  isAccrual ? "text-warning-700" : "text-hug-green-deep",
                                )}
                              >
                                {isAccrual ? "+" : "−"}
                                {formatWonShort(entry.amount_won)}
                              </td>
                              <td className="px-2 text-xs text-muted-foreground tnum">
                                {Object.entries(entry.allocations ?? {})
                                  .map(
                                    ([component, amount]) =>
                                      `${LEDGER_COMPONENT_LABEL[component] ?? component} ${formatWonShort(Number(amount))}`,
                                  )
                                  .join(" · ") || "—"}
                              </td>
                              <td className="max-w-36 truncate px-2 text-xs text-muted-foreground" title={entry.note ?? ""}>
                                {entry.note ?? "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>

              {!isClosed ? (
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader>
                    <CardTitle className="text-base font-extrabold">원장 기록 추가</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <form className="flex flex-col gap-3" onSubmit={addLedgerEntry}>
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="entry-type">기록 구분</Label>
                        <select
                          id="entry-type"
                          value={entryType}
                          onChange={(e) => setEntryType(e.target.value as LedgerEntryType)}
                          className={inputClass}
                        >
                          <optgroup label="입금·배당">
                            {RECEIPT_TYPES.map((type) => (
                              <option key={type} value={type}>
                                {LEDGER_ENTRY_TYPE_LABEL[type]}
                              </option>
                            ))}
                          </optgroup>
                          <optgroup label="비용 발생">
                            {ACCRUAL_TYPES.map((type) => (
                              <option key={type} value={type}>
                                {LEDGER_ENTRY_TYPE_LABEL[type]}
                              </option>
                            ))}
                          </optgroup>
                        </select>
                      </div>
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="entry-amount">금액 (원)</Label>
                        <input
                          id="entry-amount"
                          type="number"
                          min={1}
                          value={entryAmount}
                          onChange={(e) => setEntryAmount(e.target.value)}
                          className={inputClass}
                          required
                        />
                      </div>
                      {!LEDGER_ENTRY_IS_ACCRUAL[entryType] ? (
                        <div className="flex flex-col gap-1.5">
                          <Label htmlFor="entry-component">충당 항목</Label>
                          <select
                            id="entry-component"
                            value={entryComponent}
                            onChange={(e) => setEntryComponent(e.target.value)}
                            className={inputClass}
                          >
                            {Object.entries(LEDGER_COMPONENT_LABEL).map(([value, label]) => (
                              <option key={value} value={value}>
                                {label}
                              </option>
                            ))}
                          </select>
                        </div>
                      ) : null}
                      <div className="flex flex-col gap-1.5">
                        <Label htmlFor="entry-note">메모</Label>
                        <input
                          id="entry-note"
                          value={entryNote}
                          onChange={(e) => setEntryNote(e.target.value)}
                          placeholder="예: 배당표 기준 수령"
                          className={inputClass}
                        />
                      </div>
                      <Button type="submit" disabled={isActing} className="rounded-xl font-bold">
                        원장 기록
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              ) : null}
            </div>
          ) : tab === "cases" ? (
            <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">법무 사건</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  {detail.legal_cases.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">등록된 법무 사건이 없습니다.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                          <th className="py-2 pr-2">사건</th>
                          <th className="px-2">법원</th>
                          <th className="px-2">상태</th>
                          <th className="px-2 text-right">판결금액</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.legal_cases.map((legalCase) => (
                          <tr key={legalCase.legal_case_id} className="border-b border-line/70 last:border-b-0">
                            <td className="py-2.5 pr-2">
                              <span className="block font-semibold">
                                {LEGAL_STATUS_LABEL[legalCase.case_type as keyof typeof LEGAL_STATUS_LABEL] ??
                                  legalCase.case_type}
                              </span>
                              <span className="font-mono text-[11px] text-muted-foreground">
                                {legalCase.case_number}
                              </span>
                            </td>
                            <td className="px-2 text-xs">{legalCase.court}</td>
                            <td className="px-2">
                              <span className="rounded-full bg-hug-sky px-2 py-0.5 text-xs font-bold text-hug-blue">
                                {LEGAL_STATUS_LABEL[legalCase.status as keyof typeof LEGAL_STATUS_LABEL] ??
                                  legalCase.status}
                              </span>
                            </td>
                            <td className="px-2 text-right text-xs tnum">
                              {legalCase.judgment_amount_won
                                ? `${formatWonShort(legalCase.judgment_amount_won)} 원`
                                : "—"}
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
                  <CardTitle className="text-base font-extrabold">경·공매 사건</CardTitle>
                </CardHeader>
                <CardContent className="overflow-x-auto">
                  {detail.auction_cases.length === 0 ? (
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      등록된 경·공매 사건이 없습니다.
                    </p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                          <th className="py-2 pr-2">사건번호</th>
                          <th className="px-2">상태</th>
                          <th className="px-2">감정가</th>
                          <th className="px-2">매각·배당</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.auction_cases.map((auctionCase) => (
                          <tr key={auctionCase.auction_case_id} className="border-b border-line/70 last:border-b-0">
                            <td className="py-2.5 pr-2">
                              <span className="block font-semibold">
                                {auctionCase.auction_type === "PublicSale" ? "공매" : "경매"}
                              </span>
                              <span className="font-mono text-[11px] text-muted-foreground">
                                {auctionCase.case_number}
                              </span>
                            </td>
                            <td className="px-2">
                              <span className="rounded-full bg-hug-sky px-2 py-0.5 text-xs font-bold text-hug-blue">
                                {AUCTION_STATUS_LABEL[auctionCase.status as keyof typeof AUCTION_STATUS_LABEL] ??
                                  auctionCase.status}
                              </span>
                            </td>
                            <td className="px-2 text-xs tnum">
                              {auctionCase.appraisal_won ? `${formatWonShort(auctionCase.appraisal_won)} 원` : "—"}
                            </td>
                            <td className="px-2 text-xs text-muted-foreground tnum">
                              {auctionCase.sale_date ? `매각 ${formatDate(auctionCase.sale_date)}` : ""}
                              {auctionCase.dividend_date ? (
                                <>
                                  <br />
                                  배당 {formatDate(auctionCase.dividend_date)} ·{" "}
                                  {formatWonShort(auctionCase.dividend_amount_won)} 원
                                </>
                              ) : null}
                              {!auctionCase.sale_date && !auctionCase.dividend_date ? "—" : null}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : tab === "predictions" ? (
            <Card className="rounded-2xl border-line shadow-card">
              <CardHeader>
                <CardTitle className="text-base font-extrabold">
                  회수전망 예측 이력
                  <span className="ml-2 text-xs font-semibold text-muted-foreground">
                    산정 시점의 입력·결과가 함께 보관됩니다
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                {detail.predictions.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">예측 이력이 없습니다.</p>
                ) : (
                  <table className="w-full text-sm tnum">
                    <thead>
                      <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                        <th className="py-2 pr-2">산정일시</th>
                        <th className="px-2">예상회수율</th>
                        <th className="px-2">등급</th>
                        <th className="px-2">예상소요</th>
                        <th className="px-2 text-right">예상회수액</th>
                        <th className="px-2 text-right">직전 대비</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.predictions.map((record, index) => (
                        <tr key={record._id ?? index} className="border-b border-line/70 last:border-b-0">
                          <td className="py-2.5 pr-2 text-xs text-muted-foreground">
                            {formatDateTime(record.predicted_at)}
                          </td>
                          <td className="px-2 font-bold">
                            {(record.result.pred_recovery_ratio * 100).toFixed(1)}%
                          </td>
                          <td className="px-2">
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-xs font-bold",
                                GRADE_PILL[record.result.pred_recovery_grade],
                              )}
                            >
                              {record.result.pred_recovery_grade}
                            </span>
                          </td>
                          <td className="px-2">{record.result.pred_days_to_dividend}일</td>
                          <td className="px-2 text-right">
                            {formatWonShort(record.result.expected_recovery_on_current_balance_won)} 원
                          </td>
                          <td className="px-2 text-right text-xs text-muted-foreground">
                            {record.delta_from_previous
                              ? `${record.delta_from_previous.pred_recovery_ratio >= 0 ? "+" : ""}${(
                                  record.delta_from_previous.pred_recovery_ratio * 100
                                ).toFixed(1)}%p`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardContent>
            </Card>
          ) : (
            <Card className="rounded-2xl border-line shadow-card">
              <CardHeader>
                <CardTitle className="text-base font-extrabold">진행 이력</CardTitle>
              </CardHeader>
              <CardContent>
                {detail.events.length === 0 ? (
                  <p className="py-8 text-center text-sm text-muted-foreground">기록된 이력이 없습니다.</p>
                ) : (
                  <TimelineList
                    items={detail.events
                      .slice()
                      .reverse()
                      .map((event) => ({
                        time: formatDateTime(event.occurred_at),
                        title: event.status_axis
                          ? `${event.event_type} — ${event.after ?? ""}`
                          : event.event_type,
                        trailing: event.note ? (
                          <span className="max-w-44 truncate text-muted-foreground" title={event.note}>
                            {event.note}
                          </span>
                        ) : undefined,
                      }))}
                  />
                )}
              </CardContent>
            </Card>
          )}

          {/* 종결 */}
          {!isClosed ? (
            <motion.div variants={fadeUp}>
              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">
                    채권 종결
                    <span className="ml-2 text-xs font-semibold text-muted-foreground">
                      종결 후에는 원장·이력이 읽기 전용으로 전환됩니다
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <form
                    className="flex flex-col gap-3 md:flex-row md:items-end"
                    onSubmit={(event) => {
                      event.preventDefault();
                      runAction(
                        () =>
                          recoveryService.close(claimId, {
                            reason: closeReason,
                            note: closeNote || undefined,
                          }),
                        "채권을 종결했습니다.",
                      );
                    }}
                  >
                    <div className="flex flex-1 flex-col gap-1.5">
                      <Label htmlFor="close-reason">종결 사유</Label>
                      <select
                        id="close-reason"
                        value={closeReason}
                        onChange={(e) => setCloseReason(e.target.value as CloseReason)}
                        className={inputClass}
                      >
                        {CLOSE_REASONS.map((reason) => (
                          <option key={reason} value={reason}>
                            {CLOSE_REASON_LABEL[reason]}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex flex-[2] flex-col gap-1.5">
                      <Label htmlFor="close-note">승인 근거</Label>
                      <input
                        id="close-note"
                        value={closeNote}
                        onChange={(e) => setCloseNote(e.target.value)}
                        placeholder="전액 회수 외 종결에는 승인 근거가 필요합니다"
                        className={inputClass}
                      />
                    </div>
                    <Button type="submit" variant="outline" disabled={isActing} className="rounded-xl font-bold">
                      종결 처리
                    </Button>
                  </form>
                </CardContent>
              </Card>
            </motion.div>
          ) : null}
        </>
      )}
    </motion.div>
  );
}
