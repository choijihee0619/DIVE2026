"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Banknote, Calculator, Landmark, Percent, PiggyBank, Scale } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { recoveryService } from "@/services/recoveryService";
import { hugService } from "@/services/hugService";
import { ApiError } from "@/services/apiClient";
import type { RecoveryClaim, RecoveryPredictionRecord, RecoverySummary } from "@/types/recovery";
import type { HugSummary, PriorityBond } from "@/types/hug";
import { AnimatedNumber } from "@/components/viz/AnimatedNumber";
import { ShapBars } from "@/components/viz/ShapBars";
import { FactorSentences } from "@/components/viz/FactorSentences";
import { Term, TermHelp } from "@/components/common/Term";
import {
  AUCTION_STATUS_LABEL,
  BALANCE_STATUS_LABEL,
  CLOSE_REASON_LABEL,
  COLLECTION_ROUTE_LABEL,
  LEGAL_STATUS_LABEL,
  RECOVERY_STAGE_LABEL,
  formatDate,
  formatWonShort,
  type AuctionStatus,
  type CloseReason,
  type CollectionRoute,
  type LegalStatus,
  type RecoveryStage,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const GRADE_PILL: Record<string, string> = {
  HIGH: "bg-hug-mint text-hug-green-deep",
  MED: "bg-warning-100 text-warning-700",
  LOW: "bg-danger-100 text-danger-600",
};

const VIEW_TABS = [
  { value: "priority", label: "회수 우선순위" },
  { value: "progress", label: "회수 진행" },
  { value: "closed", label: "종결" },
  { value: "simulator", label: "회수전망 시뮬레이터" },
] as const;

type ViewTab = (typeof VIEW_TABS)[number]["value"];

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none tnum placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

/** 회수 우선순위 병합 행 — 등록채권 원장(ledger) 또는 전체 포트폴리오 참조 행(reference). */
type PriorityRow =
  | { kind: "ledger"; key: string; score: number; claim: RecoveryClaim }
  | { kind: "reference"; key: string; score: number; bond: PriorityBond };

/** "발생금액=4.8억(+0.129); 채권구분=구상채권(-0.052)" → 요인 배열. */
function parseFactorText(text: string): { name: string; value: string; shap: number }[] {
  return [...text.matchAll(/([^=;]+)=([^()]+)\(([+-]?[\d.]+)\)/g)]
    .map((match) => ({
      name: match[1].trim(),
      value: match[2].trim(),
      shap: Number(match[3]),
    }))
    .filter((factor) => factor.name && Number.isFinite(factor.shap));
}

/** 사고 후 채권관리 — 회수 우선순위·진행·종결과 등록채권 회수전망 시뮬레이터. */
export default function HugRecoveryPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<RecoverySummary | null>(null);
  const [claims, setClaims] = useState<RecoveryClaim[] | null>(null);
  const [closedClaims, setClosedClaims] = useState<RecoveryClaim[] | null>(null);
  /** 전체 관리채권 참조 포트폴리오(§20.2) — KPI·우선순위 목록 표시 전용, 원장과 저장 분리. */
  const [refSummary, setRefSummary] = useState<HugSummary | null>(null);
  const [refBonds, setRefBonds] = useState<PriorityBond[] | null>(null);
  const [tab, setTab] = useState<ViewTab>("priority");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedBond, setSelectedBond] = useState<PriorityBond | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /* 시뮬레이터 상태 */
  const [simClaimId, setSimClaimId] = useState<string>("");
  const [simAuctionDate, setSimAuctionDate] = useState("");
  const [simReason, setSimReason] = useState("");
  const [simResult, setSimResult] = useState<RecoveryPredictionRecord | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  const load = useCallback(() => {
    recoveryService
      .summaryWithFallback()
      .then(({ data }) => setSummary(data))
      .catch(() => setErrorMessage("채권 현황을 불러오지 못했습니다."));
    recoveryService
      .listClaimsWithFallback({ lifecycle: "active", sort_by: "priority_score", size: 100 })
      .then(({ data }) => {
        setClaims(data.items);
        setSelectedId((prev) => prev ?? data.items[0]?.recovery_claim_id ?? null);
      })
      .catch(() => setClaims([]));
    recoveryService
      .listClaimsWithFallback({ lifecycle: "closed", sort_by: "updated_at", size: 100 })
      .then(({ data }) => setClosedClaims(data.items))
      .catch(() => setClosedClaims([]));
    hugService
      .summary()
      .then(setRefSummary)
      .catch(() => setRefSummary(null));
    hugService
      .priority(10, 1)
      .then((data) => setRefBonds(data.items))
      .catch(() => setRefBonds([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => (claims ?? []).find((claim) => claim.recovery_claim_id === selectedId) ?? null,
    [claims, selectedId],
  );

  /** 우선순위 목록 병합(§20.2) — 전체 포트폴리오 상위 + 등록채권 원장을 점수순 정렬. */
  const priorityRows = useMemo<PriorityRow[] | null>(() => {
    if (claims === null || refBonds === null) return null;
    const rows: PriorityRow[] = [
      ...claims.map((claim) => ({
        kind: "ledger" as const,
        key: claim.recovery_claim_id,
        // 병합 정렬은 전체 포트폴리오 기준 모델 점수로 통일한다(등록 2건 내부 정규화 점수는 스케일이 다름).
        score:
          claim.latest_prediction?.priority_score ?? claim.priority_score ?? 0,
        claim,
      })),
      ...refBonds.map((bond) => ({
        kind: "reference" as const,
        key: `ref-${bond.source_row_id}`,
        score: bond.priority_score,
        bond,
      })),
    ];
    rows.sort((a, b) => b.score - a.score || a.key.localeCompare(b.key));
    return rows;
  }, [claims, refBonds]);

  /** KPI 병합 — 관리 규모는 전체 포트폴리오 + 원장, 비율은 합산 가중. */
  const combinedKpi = useMemo(() => {
    if (!summary) return null;
    const refCount = refSummary?.portfolio_count ?? 0;
    const refClaimed = refSummary?.claimed_total_won ?? 0;
    const refExpected = refSummary?.expected_recovery_total_won ?? 0;
    const predictedBase = (summary.predicted_balance_coverage_won ?? 0) + refClaimed;
    const expectedTotal = summary.expected_recovery_total_won + refExpected;
    return {
      managed: summary.managed_claim_count + refCount,
      principal: summary.subrogation_principal_balance_won + refClaimed,
      totalBalance: summary.total_balance_won + refClaimed,
      expected: expectedTotal,
      ratio: predictedBase > 0 ? expectedTotal / predictedBase : null,
    };
  }, [summary, refSummary]);

  /** 참조 행 선택 시 판단 근거 요인(문자열 → 구조화). */
  const selectedBondFactors = useMemo(
    () => (selectedBond ? parseFactorText(selectedBond.top_factors).slice(0, 3) : []),
    [selectedBond],
  );

  const simClaim = useMemo(
    () => (claims ?? []).find((claim) => claim.recovery_claim_id === simClaimId) ?? null,
    [claims, simClaimId],
  );

  /** 선택 채권 최신 예측의 회수율 요인. */
  const selectedFactors = useMemo(() => {
    const factors = selected?.latest_prediction?.top_factors ?? [];
    return factors.map((factor) => ({
      name: factor.label,
      value: String(factor.value),
      shap: factor.shap,
    }));
  }, [selected]);

  const runSimulation = (event: React.FormEvent) => {
    event.preventDefault();
    if (!simClaimId || isSimulating) return;
    setIsSimulating(true);
    recoveryService
      .predict(
        simClaimId,
        simAuctionDate
          ? { auction_filed_date: simAuctionDate, assumption_reason: simReason || "회수전망 시나리오 검토" }
          : {},
      )
      .then((record) => {
        setSimResult(record);
        toast.success("회수전망을 산정해 예측 이력에 저장했습니다.");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "회수전망 산정에 실패했습니다."),
      )
      .finally(() => setIsSimulating(false));
  };

  const kpis: { key: string; label: React.ReactNode; icon: LucideIcon; tone: string; render: () => React.ReactNode }[] = [
    {
      key: "managed",
      label: <>관리 <Term k="bond">채권</Term></>,
      icon: Landmark,
      tone: "bg-hug-navy text-white",
      render: () =>
        combinedKpi ? (
          <>
            <AnimatedNumber value={combinedKpi.managed} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "principal",
      label: <><Term k="subrogation">대위변제</Term> 원금 잔액</>,
      icon: Banknote,
      tone: "bg-hug-sky text-hug-blue",
      render: () => (combinedKpi ? <span className="tnum">{formatWonShort(combinedKpi.principal)}</span> : "—"),
    },
    {
      key: "balance",
      label: "총 잔존 채권액",
      icon: Scale,
      tone: "bg-warning-100 text-warning-700",
      render: () => (combinedKpi ? <span className="tnum">{formatWonShort(combinedKpi.totalBalance)}</span> : "—"),
    },
    {
      key: "expected",
      label: "예상 회수액",
      icon: PiggyBank,
      tone: "bg-hug-mint text-hug-green-deep",
      render: () => (combinedKpi ? <span className="tnum">{formatWonShort(combinedKpi.expected)}</span> : "—"),
    },
    {
      key: "ratio",
      label: <><Term k="recoveryRate">예상 회수율</Term> (가중)</>,
      icon: Percent,
      tone: "bg-hug-mint text-hug-green-deep",
      render: () =>
        combinedKpi?.ratio != null ? (
          <>
            <AnimatedNumber value={combinedKpi.ratio * 100} decimals={1} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">%</small>
          </>
        ) : (
          "—"
        ),
    },
  ];

  const renderAxisChip = (label: string, active: boolean) => (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11px] font-bold",
        active ? "bg-hug-sky text-hug-blue" : "bg-neutral-200 text-neutral-500",
      )}
    >
      {label}
    </span>
  );

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
            <Landmark size={22} className="text-hug-blue" />
            사고 후 채권관리
          </h1>
          <p className="mt-1.5 text-muted-foreground">
            구상채권 등록 이후의 회수업무 — 무엇부터 회수할 것인가를 예상 회수액과 회수 속도로
            정렬하고, 법무·경공매·상환 진행을 관리합니다.
          </p>
        </div>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      {/* KPI */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        {kpis.map(({ key, label, icon: Icon, tone, render }) => (
          <motion.div key={key} variants={fadeUp}>
            <Card className="h-full rounded-2xl border-line shadow-card">
              <CardContent className="flex items-center gap-3 pt-6">
                <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", tone)}>
                  <Icon size={18} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-xs font-semibold text-muted-foreground">{label}</span>
                  <span className="text-2xl font-extrabold">{render()}</span>
                </span>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <motion.div variants={fadeUp}>
        <Tabs value={tab} onValueChange={(value) => setTab(value as ViewTab)}>
          <TabsList>
            {VIEW_TABS.map((item) => (
              <TabsTrigger key={item.value} value={item.value}>
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </motion.div>

      {tab === "priority" ? (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <motion.div variants={fadeUp} className="xl:col-span-2">
            <Card className="h-full rounded-2xl border-line shadow-card">
              <CardHeader>
                <CardTitle className="text-base font-extrabold">
                  회수 우선순위 상위 채권 <TermHelp k="priorityScore" />
                  <span className="ml-2 text-xs font-semibold text-muted-foreground">
                    점수 = 예상회수액 60% · 회수속도 40%
                    {combinedKpi ? ` · 전체 ${combinedKpi.managed.toLocaleString("ko-KR")}건 중 상위` : ""}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="overflow-x-auto">
                {priorityRows === null ? (
                  <Skeleton className="h-48 w-full" />
                ) : priorityRows.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">진행 중인 채권이 없습니다.</p>
                ) : (
                  <table className="w-full text-sm tnum">
                    <thead>
                      <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                        <th className="py-2 pr-2">채권구분</th>
                        <th className="px-2">잔존액</th>
                        <th className="px-2">예상회수율</th>
                        <th className="px-2">예상소요</th>
                        <th className="px-2">
                          <Term k="recoveryGrade">회수등급</Term>
                        </th>
                        <th className="px-2 text-right">점수</th>
                      </tr>
                    </thead>
                    <tbody>
                      {priorityRows.map((row, index) => {
                        const grade =
                          row.kind === "ledger"
                            ? row.claim.latest_prediction?.pred_recovery_grade
                            : row.bond.pred_recovery_grade;
                        const ratio =
                          row.kind === "ledger"
                            ? row.claim.latest_prediction?.pred_recovery_ratio
                            : row.bond.pred_recovery_ratio;
                        const days =
                          row.kind === "ledger"
                            ? row.claim.latest_prediction?.pred_days_to_dividend
                            : row.bond.pred_days_to_dividend;
                        const isSelected =
                          row.kind === "ledger"
                            ? selectedId === row.claim.recovery_claim_id && !selectedBond
                            : selectedBond?.source_row_id === row.bond.source_row_id;
                        return (
                          <motion.tr
                            key={row.key}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: Math.min(index, 12) * 0.04, duration: 0.3 }}
                            onClick={() => {
                              if (row.kind === "ledger") {
                                setSelectedBond(null);
                                setSelectedId(row.claim.recovery_claim_id);
                              } else {
                                setSelectedBond(row.bond);
                              }
                            }}
                            onDoubleClick={() => {
                              if (row.kind === "ledger") {
                                router.push(`/hug/recovery/${row.claim.recovery_claim_id}`);
                              }
                            }}
                            className={cn(
                              "cursor-pointer border-b border-line/70 transition-colors last:border-b-0",
                              isSelected ? "bg-hug-sky/60" : "hover:bg-neutral-100",
                            )}
                          >
                            <td className="max-w-44 py-2.5 pr-2">
                              <span className="flex items-center gap-1.5 font-semibold">
                                <span className="truncate">
                                  {row.kind === "ledger" ? row.claim.claim_type_label : row.bond.claim_type}
                                </span>
                                {row.kind === "ledger" ? (
                                  <span className="shrink-0 rounded-full bg-hug-navy px-1.5 py-px text-[10px] font-bold text-white">
                                    진행
                                  </span>
                                ) : null}
                              </span>
                              <span className="text-[11px] text-muted-foreground">
                                {row.kind === "ledger" ? row.claim.product_name_label : row.bond.product_name}
                              </span>
                            </td>
                            <td className="px-2">
                              {formatWonShort(row.kind === "ledger" ? row.claim.balance : row.bond.claimed_amount)}
                            </td>
                            <td className="px-2">{ratio != null ? `${(ratio * 100).toFixed(0)}%` : "—"}</td>
                            <td className="px-2">{days != null ? `${days}일` : "—"}</td>
                            <td className="px-2">
                              {grade ? (
                                <span
                                  className={cn(
                                    "rounded-full px-2 py-0.5 text-xs font-bold",
                                    GRADE_PILL[grade],
                                  )}
                                >
                                  {grade}
                                </span>
                              ) : (
                                <span className="text-xs text-muted-foreground">미산정</span>
                              )}
                            </td>
                            <td className="px-2 text-right text-base font-extrabold">
                              {row.score.toFixed(1)}
                            </td>
                          </motion.tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
                <p className="mt-3 text-[11px] text-muted-foreground">
                  행 클릭 = 판단 근거 보기 · <b>진행</b> 표시 채권은 더블클릭으로 상세 이동
                </p>
              </CardContent>
            </Card>
          </motion.div>

          <motion.div variants={fadeUp}>
            <Card className="h-full rounded-2xl border-line shadow-card">
              <CardHeader>
                <CardTitle className="text-base font-extrabold">
                  이 채권, 왜 이 점수인가 <TermHelp k="shap" />
                </CardTitle>
              </CardHeader>
              <CardContent className="flex h-[calc(100%-64px)] flex-col gap-3">
                {selectedBond ? (
                  <>
                    <div className="rounded-xl bg-neutral-100 p-3 text-xs">
                      <b>{selectedBond.claim_type}</b> · 대위변제 {formatWonShort(selectedBond.claimed_amount)} 원
                      · 예상 회수 {formatWonShort(selectedBond.expected_recovery_won)} 원
                      <span className="mt-1 block text-muted-foreground">
                        전체 포트폴리오 상위 채권 — 진행 이력은 <b>진행</b> 표시 채권에서 확인합니다
                      </span>
                    </div>
                    {selectedBondFactors.length > 0 ? (
                      <>
                        <p className="text-xs font-bold text-muted-foreground">회수율 예측 근거 Top 3</p>
                        <ShapBars
                          key={selectedBond.source_row_id}
                          factors={selectedBondFactors.map((factor) => ({ label: factor.name, value: factor.shap }))}
                        />
                        <FactorSentences factors={selectedBondFactors} />
                      </>
                    ) : (
                      <p className="py-6 text-center text-sm text-muted-foreground">요인 정보가 없습니다.</p>
                    )}
                  </>
                ) : selected ? (
                  <>
                    <div className="rounded-xl bg-neutral-100 p-3 text-xs">
                      <b>{selected.claim_type_label}</b> · 잔존 {formatWonShort(selected.balance)} 원
                      {selected.latest_prediction ? (
                        <> · 예상 회수 {formatWonShort(selected.latest_prediction.expected_recovery_on_current_balance_won)} 원</>
                      ) : null}
                      {selected.priority_rank != null && selected.priority_portfolio_size != null ? (
                        <span className="mt-1 block text-muted-foreground">
                          진행 채권 {selected.priority_portfolio_size}건 중 {selected.priority_rank}위
                        </span>
                      ) : null}
                    </div>
                    {selectedFactors.length > 0 ? (
                      <>
                        <p className="text-xs font-bold text-muted-foreground">회수율 예측 근거 Top 3</p>
                        <ShapBars
                          key={selected.recovery_claim_id}
                          factors={selectedFactors.map((factor) => ({ label: factor.name, value: factor.shap }))}
                        />
                        <FactorSentences factors={selectedFactors} />
                      </>
                    ) : (
                      <p className="py-6 text-center text-sm text-muted-foreground">
                        예측 이력이 없습니다. 시뮬레이터에서 회수전망을 산정하세요.
                      </p>
                    )}
                    {selected.priority_components ? (
                      <div className="mt-auto rounded-xl bg-neutral-100 p-3 text-xs">
                        <p className="mb-1 font-bold text-muted-foreground">우선순위 점수 분해</p>
                        <div className="grid grid-cols-2 gap-1 tnum">
                          <span>예상회수액 백분위</span>
                          <b className="text-right">
                            {Math.round(
                              Number(selected.priority_components.expected_recovery_normalized ?? 0) * 100,
                            )}
                            %
                          </b>
                          <span>회수속도 백분위</span>
                          <b className="text-right">
                            {Math.round(Number(selected.priority_components.speed_normalized ?? 0) * 100)}%
                          </b>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <Skeleton className="h-40 w-full" />
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      ) : tab === "progress" ? (
        <motion.div variants={fadeUp}>
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                회수 진행 목록
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  법무·경공매·상환은 병행될 수 있습니다
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {claims === null ? (
                <Skeleton className="h-48 w-full" />
              ) : claims.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">진행 중인 채권이 없습니다.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">채권구분</th>
                      <th className="px-2">잔존액</th>
                      <th className="px-2">회수단계</th>
                      <th className="px-2">회수경로</th>
                      <th className="px-2">법무</th>
                      <th className="px-2">경·공매</th>
                      <th className="px-2">회수현황</th>
                    </tr>
                  </thead>
                  <tbody>
                    {claims.map((claim, index) => {
                      const stage = (claim.axis_status?.recovery_stage ?? claim.recovery_stage ?? "Registered") as RecoveryStage;
                      const route = (claim.axis_status?.collection_route ?? claim.collection_route ?? "None") as CollectionRoute;
                      const legal = (claim.axis_status?.legal_status ?? claim.legal_status ?? "None") as LegalStatus;
                      const auction = (claim.axis_status?.auction_status ?? claim.auction_status ?? "None") as AuctionStatus;
                      const balanceStatus = claim.axis_status?.balance_status ?? claim.balance_status ?? "Unrecovered";
                      return (
                        <motion.tr
                          key={claim.recovery_claim_id}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: Math.min(index, 12) * 0.04, duration: 0.3 }}
                          onClick={() => router.push(`/hug/recovery/${claim.recovery_claim_id}`)}
                          className="cursor-pointer border-b border-line/70 transition-colors last:border-b-0 hover:bg-neutral-100"
                        >
                          <td className="max-w-40 py-2.5 pr-2">
                            <span className="block truncate font-semibold">{claim.claim_type_label}</span>
                            <span className="text-[11px] text-muted-foreground">{claim.product_name_label}</span>
                          </td>
                          <td className="px-2 font-bold tnum">{formatWonShort(claim.balance)}</td>
                          <td className="px-2">
                            <span className="rounded-full bg-hug-navy px-2 py-0.5 text-xs font-bold text-white">
                              {RECOVERY_STAGE_LABEL[stage] ?? stage}
                            </span>
                          </td>
                          <td className="px-2 text-xs">{COLLECTION_ROUTE_LABEL[route] ?? route}</td>
                          <td className="px-2">{renderAxisChip(LEGAL_STATUS_LABEL[legal] ?? legal, legal !== "None")}</td>
                          <td className="px-2">
                            {renderAxisChip(AUCTION_STATUS_LABEL[auction] ?? auction, auction !== "None")}
                          </td>
                          <td className="px-2 text-xs">
                            {BALANCE_STATUS_LABEL[balanceStatus as keyof typeof BALANCE_STATUS_LABEL] ??
                              balanceStatus}
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
      ) : tab === "closed" ? (
        <motion.div variants={fadeUp}>
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                종결 채권
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  종결 후에는 읽기 전용으로 보관됩니다
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {closedClaims === null ? (
                <Skeleton className="h-40 w-full" />
              ) : closedClaims.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">종결된 채권이 없습니다.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">채권구분</th>
                      <th className="px-2">잔존액</th>
                      <th className="px-2">종결 사유</th>
                      <th className="px-2">종결일</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closedClaims.map((claim) => (
                      <tr
                        key={claim.recovery_claim_id}
                        onClick={() => router.push(`/hug/recovery/${claim.recovery_claim_id}`)}
                        className="cursor-pointer border-b border-line/70 transition-colors last:border-b-0 hover:bg-neutral-100"
                      >
                        <td className="py-2.5 pr-2 font-semibold">{claim.claim_type_label}</td>
                        <td className="px-2 tnum">{formatWonShort(claim.balance)}</td>
                        <td className="px-2">
                          <span className="rounded-full bg-neutral-200 px-2 py-0.5 text-xs font-bold text-neutral-600">
                            {claim.closure?.reason
                              ? CLOSE_REASON_LABEL[claim.closure.reason as CloseReason] ?? claim.closure.reason
                              : "종결"}
                          </span>
                        </td>
                        <td className="px-2 text-xs text-muted-foreground tnum">
                          {formatDate(claim.closure?.closed_at ?? claim.closed_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </motion.div>
      ) : (
        /* 등록채권 회수전망 시뮬레이터 */
        <motion.div variants={fadeUp}>
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base font-extrabold">
                <Calculator size={16} className="text-hug-blue" />
                등록채권 회수전망 시뮬레이터
                <Term
                  k="recoveryModel"
                  underline={false}
                  className="rounded-full bg-hug-sky px-2.5 py-0.5 text-xs font-bold text-hug-blue"
                >
                  원장 자동입력 · 결과 저장
                </Term>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <form className="flex flex-col gap-3" onSubmit={runSimulation}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="sim-claim">등록 채권 선택</Label>
                  <select
                    id="sim-claim"
                    value={simClaimId}
                    onChange={(e) => {
                      setSimClaimId(e.target.value);
                      setSimResult(null);
                    }}
                    className={inputClass}
                    required
                  >
                    <option value="">채권을 선택하세요</option>
                    {(claims ?? []).map((claim) => (
                      <option key={claim.recovery_claim_id} value={claim.recovery_claim_id}>
                        {claim.claim_type_label} · 잔존 {formatWonShort(claim.balance)} 원
                      </option>
                    ))}
                  </select>
                </div>

                {simClaim ? (
                  <div className="rounded-xl bg-neutral-100 p-3.5 text-xs">
                    <p className="mb-2 font-bold text-muted-foreground">원장 자동입력 값</p>
                    <div className="grid grid-cols-2 gap-1.5 tnum">
                      <span className="text-muted-foreground">상품</span>
                      <b className="text-right">{simClaim.product_name_label}</b>
                      <span className="text-muted-foreground">채권구분</span>
                      <b className="text-right">{simClaim.claim_type_label}</b>
                      <span className="text-muted-foreground">잔존 채권액</span>
                      <b className="text-right">{formatWonShort(simClaim.balance)} 원</b>
                      <span className="text-muted-foreground">채권 발생일</span>
                      <b className="text-right">{formatDate(simClaim.incurred_date ?? simClaim.created_at)}</b>
                      <span className="text-muted-foreground">경·공매 신청일</span>
                      <b className="text-right">
                        {simClaim.auction_filed_date ? formatDate(simClaim.auction_filed_date) : "미등록"}
                      </b>
                    </div>
                  </div>
                ) : null}

                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="sim-auction">
                    경·공매 신청일 가정
                    <span className="ml-1.5 text-[11px] font-normal text-muted-foreground">
                      원장에 신청일이 없거나 시나리오를 비교할 때만 입력
                    </span>
                  </Label>
                  <input
                    id="sim-auction"
                    type="date"
                    value={simAuctionDate}
                    onChange={(e) => setSimAuctionDate(e.target.value)}
                    className={inputClass}
                  />
                </div>
                {simAuctionDate ? (
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="sim-reason">가정 사유</Label>
                    <input
                      id="sim-reason"
                      value={simReason}
                      onChange={(e) => setSimReason(e.target.value)}
                      placeholder="예: 경매 신청 예정일 기준 검토"
                      className={inputClass}
                    />
                  </div>
                ) : null}

                <Button type="submit" disabled={isSimulating || !simClaimId} className="mt-1 rounded-xl font-bold">
                  {isSimulating ? "산정 중..." : "회수전망 산정"}
                </Button>
              </form>

              <div>
                {simResult ? (
                  <motion.div
                    key={simResult._id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                    className="flex h-full flex-col gap-3"
                  >
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div className="rounded-xl bg-neutral-100 p-3">
                        <p className="text-[11px] font-semibold text-muted-foreground">
                          <Term k="recoveryRate">예상 회수율</Term>
                        </p>
                        <p className="text-xl font-extrabold tnum">
                          <AnimatedNumber
                            value={simResult.result.pred_recovery_ratio * 100}
                            decimals={1}
                            durationSec={0.7}
                          />
                          %
                        </p>
                        <span
                          className={cn(
                            "mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold",
                            GRADE_PILL[simResult.result.pred_recovery_grade],
                          )}
                        >
                          {simResult.result.pred_recovery_grade}
                        </span>
                      </div>
                      <div className="rounded-xl bg-neutral-100 p-3">
                        <p className="text-[11px] font-semibold text-muted-foreground">
                          <Term k="daysToDividend">예상 소요일</Term>
                        </p>
                        <p className="text-xl font-extrabold tnum">
                          <AnimatedNumber value={simResult.result.pred_days_to_dividend} durationSec={0.7} />일
                        </p>
                      </div>
                      <div className="rounded-xl bg-neutral-100 p-3">
                        <p className="text-[11px] font-semibold text-muted-foreground">포트폴리오 순위</p>
                        <p className="text-xl font-extrabold text-hug-blue tnum">
                          {simResult.result.priority_rank}
                          <small className="text-xs text-muted-foreground">
                            /{simResult.result.priority_portfolio_size}
                          </small>
                        </p>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground tnum">
                      현재 잔액 기준 예상 회수액{" "}
                      <b>{formatWonShort(simResult.result.expected_recovery_on_current_balance_won)} 원</b>
                    </p>
                    {simResult.delta_from_previous ? (
                      <div className="rounded-xl bg-hug-sky p-3 text-xs text-hug-navy">
                        <p className="mb-1 font-bold">직전 예측 대비 변화</p>
                        <div className="grid grid-cols-2 gap-1 tnum">
                          <span>회수율</span>
                          <b className="text-right">
                            {simResult.delta_from_previous.pred_recovery_ratio >= 0 ? "+" : ""}
                            {(simResult.delta_from_previous.pred_recovery_ratio * 100).toFixed(1)}%p
                          </b>
                          <span>소요일</span>
                          <b className="text-right">
                            {simResult.delta_from_previous.pred_days_to_dividend >= 0 ? "+" : ""}
                            {simResult.delta_from_previous.pred_days_to_dividend}일
                          </b>
                          <span>예상 회수액</span>
                          <b className="text-right">
                            {simResult.delta_from_previous.expected_recovery_on_current_balance_won >= 0
                              ? "+"
                              : ""}
                            {formatWonShort(
                              simResult.delta_from_previous.expected_recovery_on_current_balance_won,
                            )}{" "}
                            원
                          </b>
                        </div>
                      </div>
                    ) : null}
                    {(simResult.result.top_factors ?? []).length > 0 ? (
                      <>
                        <ShapBars
                          factors={(simResult.result.top_factors ?? []).map((factor) => ({
                            label: factor.label,
                            value: factor.shap,
                          }))}
                        />
                        <FactorSentences
                          factors={(simResult.result.top_factors ?? []).map((factor) => ({
                            name: factor.label,
                            value: String(factor.value),
                            shap: factor.shap,
                          }))}
                        />
                      </>
                    ) : null}
                    <p className="mt-auto text-[11px] text-muted-foreground">
                      결과는 채권 예측 이력에 저장되어 상세 화면과 감사 이력에서 다시 확인할 수 있습니다.
                    </p>
                  </motion.div>
                ) : (
                  <div className="flex h-full min-h-40 items-center justify-center rounded-xl border border-dashed border-line px-6 text-center text-sm text-muted-foreground">
                    등록 채권을 선택하고 &ldquo;회수전망 산정&rdquo;을 누르면 원장값 기준 예상 회수율과
                    판단 근거가 표시됩니다.
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </motion.div>
  );
}
