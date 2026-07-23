"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Banknote,
  CircleAlert,
  FileStack,
  FileText,
  Landmark,
  MapPinned,
  Percent,
  PiggyBank,
  RotateCcw,
  Scale,
  Siren,
} from "lucide-react";
import { toast } from "sonner";
import type { LucideIcon } from "lucide-react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { hugService } from "@/services/hugService";
import { hugContractService } from "@/services/hugContractService";
import { performanceClaimService } from "@/services/performanceClaimService";
import { recoveryService } from "@/services/recoveryService";
import type { HugSummary, IssuanceIncidentTrend, RegionRiskData, VictimsData } from "@/types/hug";
import type { HugContractItem } from "@/types/hugContract";
import type { HugIncidentRow } from "@/types/performanceClaim";
import type { RecoveryClaim, RecoverySummary } from "@/types/recovery";
import { AnimatedNumber } from "@/components/viz/AnimatedNumber";
import { Term } from "@/components/common/Term";
import {
  CLAIM_STAGE_LABEL,
  CLAIM_STAGE_TONE,
  SLA_STATUS_LABEL,
  SLA_STATUS_TONE,
  formatDday,
  formatWonShort,
  type PerformanceClaimStage,
  type SlaStatus,
} from "@/lib/hug-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

interface KpiSpec {
  key: string;
  label: React.ReactNode;
  icon: LucideIcon;
  tone: string;
  href?: string;
  render: () => React.ReactNode;
}

/** HUG 통합 대시보드 — 보증·예방/회수 KPI, 업무 파이프라인, 발급·사고 추이, 오늘의 조치 Top 5. */
export default function HugDashboardPage() {
  const router = useRouter();

  const [trend, setTrend] = useState<IssuanceIncidentTrend | null>(null);
  const [regionRisk, setRegionRisk] = useState<RegionRiskData | null>(null);
  const [victims, setVictims] = useState<VictimsData | null>(null);
  const [contracts, setContracts] = useState<HugContractItem[] | null>(null);
  const [incidents, setIncidents] = useState<HugIncidentRow[] | null>(null);
  const [recoverySummary, setRecoverySummary] = useState<RecoverySummary | null>(null);
  const [topRecovery, setTopRecovery] = useState<RecoveryClaim[] | null>(null);
  /** 전체 관리채권 참조 포트폴리오(§20.2) — 회수 KPI 규모감 병합 표시 전용. */
  const [refSummary, setRefSummary] = useState<HugSummary | null>(null);
  const [dashError, setDashError] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetArmed, setResetArmed] = useState(false);

  /** §20.3 원클릭 리셋 — 1차 클릭으로 확인 상태를 열고, 2차 클릭 시 기준 업무대장으로 원복한다. */
  const handleReset = async () => {
    if (resetting) return;
    if (!resetArmed) {
      setResetArmed(true);
      window.setTimeout(() => setResetArmed(false), 5000);
      return;
    }
    setResetArmed(false);
    setResetting(true);
    try {
      await hugService.resetDemoData();
      toast.success("업무 데이터를 기준 상태로 초기화했습니다.");
      window.location.reload();
    } catch {
      toast.error("초기화에 실패했습니다. 잠시 후 다시 시도하세요.");
      setResetting(false);
    }
  };

  useEffect(() => {
    hugService.issuanceIncidentTrend().then(setTrend).catch(() => setTrend(null));
    hugService.regionRisk().then(setRegionRisk).catch(() => setRegionRisk(null));
    hugService.victims().then(setVictims).catch(() => setVictims(null));
    hugContractService
      .listWithFallback({ size: 400 })
      .then(({ data }) => setContracts(data.items))
      .catch(() => {
        setContracts([]);
        setDashError("대시보드 집계를 불러오지 못했습니다.");
      });
    hugService
      .summary()
      .then(setRefSummary)
      .catch(() => setRefSummary(null));
    performanceClaimService
      .listIncidents({ size: 100 })
      .then((data) => setIncidents(data.items))
      .catch(() => setIncidents([]));
    recoveryService
      .summaryWithFallback()
      .then(({ data }) => setRecoverySummary(data))
      .catch(() => setRecoverySummary(null));
    recoveryService
      .listClaimsWithFallback({ sort_by: "priority_score", size: 5, lifecycle: "active" })
      .then(({ data }) => setTopRecovery(data.items))
      .catch(() => setTopRecovery([]));
  }, []);

  /** 진행 중이 아닌(등록·인계·거절) 이행 단계. */
  const CLAIM_DONE_STAGES = useMemo(
    () => new Set(["RecoveryClaimRegistered", "TransferredToRecovery", "Rejected"]),
    [],
  );
  const ACTION_NEEDED_STATUSES = useMemo(
    () =>
      new Set(["RiskDetected", "Notified", "ActionRequested", "Verifying", "Overdue", "EscalatedMonitoring"]),
    [],
  );

  /**
   * KPI·파이프라인 집계 — 하단 목록·업무화면과 동일한 조회 소스에서 계산해
   * 대시보드 숫자와 클릭 후 화면이 항상 일치하도록 한다.
   */
  const register = useMemo(() => {
    if (contracts === null || incidents === null) return null;
    const contractIds = new Set(contracts.map((contract) => contract.contract_id));
    const incidentContractIds = new Set(
      incidents.map((row) => row.contract_id).filter((id): id is string => Boolean(id)),
    );
    const extraIncidentContracts = [...incidentContractIds].filter((id) => !contractIds.has(id)).length;
    const highRisk = contracts.filter(
      (contract) =>
        (contract.prediction?.risk_percentile ?? 0) >= 0.8 ||
        contract.evidence_bundle.overdue_count > 0 ||
        (contract.prevention_case && ACTION_NEEDED_STATUSES.has(contract.prevention_case.status)),
    ).length;
    const stageCount = (stages: string[]) =>
      incidents.filter((row) => row.performance_claim && stages.includes(row.performance_claim.stage)).length;
    return {
      guarantee_contract_count: contracts.length + extraIncidentContracts,
      pre_incident_active_contract_count: contracts.length,
      high_risk_action_needed_contract_count: highRisk,
      performance_claim_in_progress_count: incidents.filter(
        (row) =>
          (row.performance_claim && !CLAIM_DONE_STAGES.has(row.performance_claim.stage)) ||
          (!row.performance_claim && row.status === "Received"),
      ).length,
      // 회수 KPI는 §20.2에 따라 전체 관리채권 참조 포트폴리오와 병합 표시한다(저장 분리 유지).
      managed_claim_count:
        (recoverySummary?.managed_claim_count ?? 0) + (refSummary?.portfolio_count ?? 0),
      subrogation_principal_balance_won:
        (recoverySummary?.subrogation_principal_balance_won ?? 0) +
        (refSummary?.claimed_total_won ?? 0),
      expected_recovery_total_won:
        (recoverySummary?.expected_recovery_total_won ?? 0) +
        (refSummary?.expected_recovery_total_won ?? 0),
      weighted_expected_recovery_ratio: (() => {
        const base =
          (recoverySummary?.predicted_balance_coverage_won ?? 0) +
          (refSummary?.claimed_total_won ?? 0);
        if (base <= 0) return recoverySummary?.weighted_expected_recovery_ratio ?? null;
        return (
          ((recoverySummary?.expected_recovery_total_won ?? 0) +
            (refSummary?.expected_recovery_total_won ?? 0)) / base
        );
      })(),
      pipeline_counts: {
        prevention_action_needed: contracts.filter(
          (contract) =>
            contract.evidence_bundle.overdue_count > 0 ||
            (contract.prevention_case && ACTION_NEEDED_STATUSES.has(contract.prevention_case.status)),
        ).length,
        accident_notified: incidents.filter((row) => !row.performance_claim && row.status === "Received")
          .length,
        performance_review: stageCount(["ClaimReceived", "SupplementRequested", "UnderReview", "OnHold"]),
        handover_waiting: stageCount(["Approved", "HandoverScheduled"]),
        subrogation_paid: stageCount(["SubrogationPaid"]),
        recovery_active: recoverySummary?.managed_claim_count ?? 0,
      },
    };
  }, [contracts, incidents, recoverySummary, refSummary, ACTION_NEEDED_STATUSES, CLAIM_DONE_STAGES]);

  /** 오늘 처리할 고위험 계약 Top 5 — 사전예방 우선순위 상위. */
  const topContracts = useMemo(() => (contracts === null ? null : contracts.slice(0, 5)), [contracts]);

  /** 기한 임박 이행사건 Top 5 — 남은 처리시간 오름차순. */
  const slaIncidents = useMemo(() => {
    if (incidents === null) return null;
    return incidents
      .filter((row) => row.performance_claim && !CLAIM_DONE_STAGES.has(row.performance_claim.stage))
      .sort(
        (a, b) =>
          (a.performance_claim?.sla.remaining_seconds ?? 0) -
          (b.performance_claim?.sla.remaining_seconds ?? 0),
      )
      .slice(0, 5);
  }, [incidents, CLAIM_DONE_STAGES]);

  /** 전국·수도권·지방 집계와 개별 시도 분리. */
  const { aggregates, sidoRows } = useMemo(() => {
    const rows = regionRisk?.sido_summary ?? [];
    const aggregateNames = new Set(["전국", "수도권", "지방"]);
    return {
      aggregates: rows.filter((r) => aggregateNames.has(r.sido)),
      sidoRows: rows
        .filter((r) => !aggregateNames.has(r.sido))
        .sort((a, b) => b.accident_rate_pct - a.accident_rate_pct)
        .slice(0, 8),
    };
  }, [regionRisk]);

  const victimTop = useMemo(() => {
    const items = victims?.items ?? [];
    const latestYear = Math.max(...items.map((v) => v.year), 0);
    return {
      year: latestYear,
      rows: items
        .filter((v) => v.year === latestYear)
        .sort((a, b) => b.victim_house_cnt - a.victim_house_cnt)
        .slice(0, 6),
    };
  }, [victims]);

  const trendSeries = useMemo(
    () =>
      (trend?.series ?? []).map((point) => ({
        year: String(point.year),
        issue: point.issue_cnt,
        accident: point.accident_cnt ?? 0,
        rate: point.accident_rate_pct,
      })),
    [trend],
  );

  const maxSidoRate = Math.max(...sidoRows.map((r) => r.accident_rate_pct), 0.001);
  const maxVictim = Math.max(...victimTop.rows.map((r) => r.victim_house_cnt), 1);

  const guaranteeKpis: KpiSpec[] = [
    {
      key: "contracts",
      label: "보증계약 전체",
      icon: FileText,
      tone: "bg-hug-navy text-white",
      href: "/hug/contracts",
      render: () =>
        register ? (
          <>
            <AnimatedNumber value={register.guarantee_contract_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "preIncident",
      label: "사고 전 진행 계약",
      icon: FileStack,
      tone: "bg-hug-sky text-hug-blue",
      href: "/hug/contracts",
      render: () =>
        register ? (
          <>
            <AnimatedNumber value={register.pre_incident_active_contract_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "highRisk",
      label: "고위험·조치필요",
      icon: CircleAlert,
      tone: "bg-danger-100 text-danger-600",
      href: "/hug/contracts",
      render: () =>
        register ? (
          <>
            <AnimatedNumber value={register.high_risk_action_needed_contract_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "claims",
      label: "보증이행 진행",
      icon: Siren,
      tone: "bg-warning-100 text-warning-700",
      href: "/hug/incidents",
      render: () =>
        register ? (
          <>
            <AnimatedNumber value={register.performance_claim_in_progress_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
  ];

  const recoveryKpis: KpiSpec[] = [
    {
      key: "managed",
      label: <>관리 <Term k="bond">채권</Term></>,
      icon: Landmark,
      tone: "bg-hug-navy text-white",
      href: "/hug/recovery",
      render: () =>
        register ? (
          <>
            <AnimatedNumber value={register.managed_claim_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "balance",
      label: <><Term k="subrogation">대위변제</Term> 잔고</>,
      icon: Banknote,
      tone: "bg-hug-sky text-hug-blue",
      href: "/hug/recovery",
      render: () =>
        register ? (
          <span className="tnum">{formatWonShort(register.subrogation_principal_balance_won)}</span>
        ) : (
          "—"
        ),
    },
    {
      key: "expected",
      label: "예상 회수액",
      icon: PiggyBank,
      tone: "bg-hug-mint text-hug-green-deep",
      href: "/hug/recovery",
      render: () =>
        register ? (
          <span className="tnum">{formatWonShort(register.expected_recovery_total_won)}</span>
        ) : (
          "—"
        ),
    },
    {
      key: "ratio",
      label: <><Term k="recoveryRate">예상 회수율</Term> (가중)</>,
      icon: Percent,
      tone: "bg-hug-mint text-hug-green-deep",
      href: "/hug/recovery",
      render: () =>
        register?.weighted_expected_recovery_ratio != null ? (
          <>
            <AnimatedNumber value={register.weighted_expected_recovery_ratio * 100} decimals={1} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">%</small>
          </>
        ) : (
          "—"
        ),
    },
  ];

  const pipeline: { key: string; label: string; count: number; href: string; tone: string }[] =
    register
      ? [
          {
            key: "prevention",
            label: "사고 전 조치필요",
            count: register.pipeline_counts.prevention_action_needed,
            href: "/hug/contracts",
            tone: "text-warning-700",
          },
          {
            key: "notified",
            label: "사고통지",
            count: register.pipeline_counts.accident_notified,
            href: "/hug/incidents",
            tone: "text-danger-600",
          },
          {
            key: "review",
            label: "이행심사",
            count: register.pipeline_counts.performance_review,
            href: "/hug/incidents",
            tone: "text-hug-blue",
          },
          {
            key: "handover",
            label: "명도 대기",
            count: register.pipeline_counts.handover_waiting,
            href: "/hug/incidents",
            tone: "text-hug-blue",
          },
          {
            key: "paid",
            label: "대위변제",
            count: register.pipeline_counts.subrogation_paid,
            href: "/hug/incidents",
            tone: "text-hug-green-deep",
          },
          {
            key: "recovery",
            label: "회수 진행",
            count: register.pipeline_counts.recovery_active,
            href: "/hug/recovery",
            tone: "text-hug-navy",
          },
        ]
      : [];

  const renderKpiRow = (title: string, kpis: KpiSpec[]) => (
    <div>
      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">{title}</p>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map(({ key, label, icon: Icon, tone, href, render }) => (
          <motion.div key={key} variants={fadeUp}>
            <Card
              onClick={href ? () => router.push(href) : undefined}
              className={cn(
                "h-full rounded-2xl border-line shadow-card",
                href && "cursor-pointer transition-shadow hover:shadow-lg",
              )}
            >
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
    </div>
  );

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">통합 대시보드</h1>
          <p className="mt-1.5 text-muted-foreground">
            보증 포트폴리오 전체 현황 — 사고 전 예방, 보증이행, 사고 후 회수 중 어디에 업무가 집중되어
            있는지 확인하고 각 업무화면으로 이동합니다.
          </p>
        </div>
        <Link
          href="/hug/map"
          className="ml-auto flex items-center gap-1.5 rounded-full border border-line bg-card px-3.5 py-1.5 text-xs font-bold text-hug-blue transition-colors hover:bg-hug-sky"
        >
          <MapPinned size={14} />
          전국 위험 지도 상세
        </Link>
        {/* 관리자 전용 조용한 리셋(§20.3) — 2단계 클릭으로 기준 업무대장 원복 */}
        <button
          type="button"
          onClick={handleReset}
          disabled={resetting}
          title="업무 데이터 초기화"
          aria-label="업무 데이터 초기화"
          className={cn(
            "flex h-8 items-center justify-center gap-1.5 rounded-full border border-line bg-card text-muted-foreground transition-colors hover:bg-neutral-100 hover:text-foreground disabled:opacity-50",
            resetArmed ? "px-3 text-xs font-bold text-destructive hover:text-destructive" : "w-8",
          )}
        >
          <RotateCcw size={14} className={resetting ? "animate-spin" : undefined} />
          {resetArmed ? "기준 상태로 초기화" : null}
        </button>
      </motion.div>

      {dashError ? <p className="text-sm text-destructive">{dashError}</p> : null}

      {/* KPI — 보증·예방 / 회수 2묶음 */}
      <motion.div variants={fadeUp} className="flex flex-col gap-5">
        {renderKpiRow("보증 · 예방", guaranteeKpis)}
        {renderKpiRow("회수", recoveryKpis)}
      </motion.div>

      {/* 업무 파이프라인 요약 */}
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardContent className="pt-6">
            <div className="grid grid-cols-3 gap-2 md:grid-cols-6">
              {pipeline.length > 0
                ? pipeline.map((step, index) => (
                    <button
                      key={step.key}
                      onClick={() => router.push(step.href)}
                      className="group relative flex flex-col items-center gap-1 rounded-xl px-2 py-3 transition-colors hover:bg-neutral-100"
                    >
                      {index < pipeline.length - 1 ? (
                        <ArrowRight
                          size={13}
                          className="absolute -right-[7px] top-1/2 hidden -translate-y-1/2 text-neutral-300 md:block"
                        />
                      ) : null}
                      <span className={cn("text-xl font-extrabold tnum", step.tone)}>{step.count}</span>
                      <span className="text-[11px] font-semibold text-muted-foreground group-hover:text-ink">
                        {step.label}
                      </span>
                    </button>
                  ))
                : Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* 발급·사고 추이 + 지역 통계 */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <motion.div variants={fadeUp} className="xl:col-span-2">
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                전세보증금반환보증 발급·사고 추이
                <span className="ml-2 text-xs font-semibold text-muted-foreground">연도별 · 전국</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {trend === null ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={trendSeries} margin={{ top: 8, right: 4, bottom: 0, left: -8 }}>
                      <CartesianGrid stroke="var(--color-line)" strokeDasharray="3 3" vertical={false} />
                      <XAxis
                        dataKey="year"
                        tick={{ fontSize: 11, fill: "var(--color-ink-soft)" }}
                        tickLine={false}
                        axisLine={{ stroke: "var(--color-line)" }}
                      />
                      <YAxis
                        yAxisId="count"
                        tick={{ fontSize: 10, fill: "var(--color-ink-soft)" }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(v: number) => (v >= 10000 ? `${Math.round(v / 10000)}만` : String(v))}
                      />
                      <YAxis
                        yAxisId="rate"
                        orientation="right"
                        tick={{ fontSize: 10, fill: "var(--color-ink-soft)" }}
                        tickLine={false}
                        axisLine={false}
                        unit="%"
                      />
                      <Tooltip
                        formatter={(value, name) => {
                          if (name === "사고율") return [`${Number(value).toFixed(2)}%`, name];
                          return [`${Number(value).toLocaleString("ko-KR")}건`, name];
                        }}
                        contentStyle={{ borderRadius: 12, border: "1px solid var(--color-line)", fontSize: 12 }}
                      />
                      <Bar
                        yAxisId="count"
                        dataKey="issue"
                        name="발급"
                        fill="var(--color-hug-blue)"
                        opacity={0.85}
                        radius={[4, 4, 0, 0]}
                        animationDuration={900}
                      />
                      <Bar
                        yAxisId="count"
                        dataKey="accident"
                        name="사고"
                        fill="var(--color-danger-500)"
                        opacity={0.85}
                        radius={[4, 4, 0, 0]}
                        animationDuration={900}
                      />
                      <Line
                        yAxisId="rate"
                        type="monotone"
                        dataKey="rate"
                        name="사고율"
                        stroke="var(--color-warning-500)"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        animationDuration={1100}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              )}
              <p className="mt-2 text-[11px] text-muted-foreground">
                발급건수·사고건수(좌축)와 사고율 = 사고건수 ÷ 발급건수(우축) — HUG 빅데이터 포털 공개 집계
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base font-extrabold">
                지역 사고율 순위
                <Link href="/hug/map" className="text-xs font-bold text-hug-blue hover:underline">
                  지도 보기 →
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {aggregates.map((row) => (
                  <span key={row.sido} className="rounded-full bg-hug-sky px-2.5 py-1 text-xs font-bold text-hug-navy tnum">
                    {row.sido} {row.accident_rate_pct.toFixed(1)}%
                  </span>
                ))}
              </div>
              {regionRisk === null ? (
                <Skeleton className="h-36 w-full" />
              ) : (
                <ul className="flex flex-col gap-1.5 text-xs">
                  {sidoRows.map((row, index) => (
                    <li key={row.sido} className="grid grid-cols-[52px_1fr_60px] items-center gap-2">
                      <span className="font-semibold">{row.sido}</span>
                      <span className="h-2 overflow-hidden rounded-full bg-neutral-200">
                        <motion.i
                          className={cn(
                            "block h-full rounded-full",
                            row.accident_rate_pct >= 2.0
                              ? "bg-danger-500"
                              : row.accident_rate_pct >= 1.5
                                ? "bg-warning-500"
                                : "bg-hug-green",
                          )}
                          initial={{ width: 0 }}
                          whileInView={{ width: `${(row.accident_rate_pct / maxSidoRate) * 100}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.7, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
                        />
                      </span>
                      <span className="text-right text-muted-foreground tnum">
                        {row.accident_rate_pct.toFixed(1)}% · {row.accident_cnt}건
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-3 text-[11px] text-muted-foreground">
                발급건수 대비 사고건수 — HUG 빅데이터 포털(HOUSTA) 집계
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* 오늘의 조치 Top 5 — 3개 업무영역 요약 카드 */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base font-extrabold">
                오늘 처리할 고위험 계약
                <Link href="/hug/contracts" className="text-xs font-bold text-hug-blue hover:underline">
                  전체 보기 →
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {topContracts === null ? (
                <Skeleton className="h-40 w-full" />
              ) : topContracts.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">조치가 필요한 계약이 없습니다.</p>
              ) : (
                <ul className="flex flex-col text-sm">
                  {topContracts.map((contract) => (
                    <li
                      key={contract.contract_id}
                      onClick={() => router.push(`/hug/contracts/${contract.contract_id}`)}
                      className="flex cursor-pointer items-center gap-2 border-b border-line/70 py-2.5 transition-colors last:border-b-0 hover:bg-neutral-100"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-semibold">
                          {contract.address_summary ?? contract.contract_id}
                        </span>
                        <span className="text-xs text-muted-foreground tnum">
                          {contract.deposit ? `보증금 ${formatWonShort(contract.deposit)}` : ""} ·{" "}
                          {formatDday(contract.d_day)}
                        </span>
                      </span>
                      <span className="shrink-0 rounded-full bg-danger-100 px-2 py-0.5 text-xs font-bold text-danger-600 tnum">
                        우선순위 {contract.prevention_priority.toFixed(0)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base font-extrabold">
                기한 임박 이행사건
                <Link href="/hug/incidents" className="text-xs font-bold text-hug-blue hover:underline">
                  전체 보기 →
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {slaIncidents === null ? (
                <Skeleton className="h-40 w-full" />
              ) : slaIncidents.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">진행 중인 이행사건이 없습니다.</p>
              ) : (
                <ul className="flex flex-col text-sm">
                  {slaIncidents.map((row) => {
                    const claim = row.performance_claim;
                    if (!claim) return null;
                    return (
                      <li
                        key={row.incident_id}
                        onClick={() => router.push(`/hug/incidents/${row.incident_id}`)}
                        className="flex cursor-pointer items-center gap-2 border-b border-line/70 py-2.5 transition-colors last:border-b-0 hover:bg-neutral-100"
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-semibold">{row.incident_type_label}</span>
                          <span className="text-xs text-muted-foreground tnum">
                            청구 {formatWonShort(claim.claim_amount)} 원
                          </span>
                        </span>
                        <span
                          className={cn(
                            "shrink-0 rounded-full px-2 py-0.5 text-xs font-bold",
                            CLAIM_STAGE_TONE[claim.stage as PerformanceClaimStage] ??
                              "bg-neutral-200 text-neutral-600",
                          )}
                        >
                          {CLAIM_STAGE_LABEL[claim.stage as PerformanceClaimStage] ?? claim.stage}
                        </span>
                        <span
                          className={cn(
                            "shrink-0 rounded-full px-2 py-0.5 text-xs font-bold",
                            SLA_STATUS_TONE[claim.sla.status as SlaStatus] ?? "bg-neutral-200 text-neutral-600",
                          )}
                        >
                          {SLA_STATUS_LABEL[claim.sla.status as SlaStatus] ?? claim.sla.status}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base font-extrabold">
                <span className="flex items-center gap-1.5">
                  <Scale size={15} className="text-hug-blue" />
                  회수 우선순위 Top 5
                </span>
                <Link href="/hug/recovery" className="text-xs font-bold text-hug-blue hover:underline">
                  전체 보기 →
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {topRecovery === null ? (
                <Skeleton className="h-40 w-full" />
              ) : topRecovery.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">진행 중인 관리채권이 없습니다.</p>
              ) : (
                <ul className="flex flex-col text-sm">
                  {topRecovery.map((claim) => (
                    <li
                      key={claim.recovery_claim_id}
                      onClick={() => router.push(`/hug/recovery/${claim.recovery_claim_id}`)}
                      className="flex cursor-pointer items-center gap-2 border-b border-line/70 py-2.5 transition-colors last:border-b-0 hover:bg-neutral-100"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-semibold">{claim.claim_type_label}</span>
                        <span className="text-xs text-muted-foreground tnum">
                          잔액 {formatWonShort(claim.balance)} 원
                        </span>
                      </span>
                      {claim.priority_score != null ? (
                        <span className="shrink-0 text-base font-extrabold text-hug-blue tnum">
                          {claim.priority_score.toFixed(1)}
                        </span>
                      ) : (
                        <span className="shrink-0 text-xs text-muted-foreground">—</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* 전세사기 피해주택 분포 */}
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader>
            <CardTitle className="text-base font-extrabold">
              전세사기 피해주택 분포{victimTop.year ? ` (${victimTop.year})` : ""}
              <span className="ml-2 text-xs font-semibold text-muted-foreground">
                지역별 집계이며 개별 주택 위치가 아닙니다
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {victims === null ? (
              <Skeleton className="h-36 w-full" />
            ) : (
              <ul className="grid grid-cols-1 gap-x-8 gap-y-1.5 text-xs md:grid-cols-2">
                {victimTop.rows.map((row, index) => (
                  <li
                    key={`${row.sido_short}-${row.sigungu}`}
                    className="grid grid-cols-[100px_1fr_44px] items-center gap-2"
                  >
                    <span className="truncate font-semibold">
                      {row.sido_short} {row.sigungu}
                    </span>
                    <span className="h-2 overflow-hidden rounded-full bg-neutral-200">
                      <motion.i
                        className="block h-full rounded-full bg-hug-blue"
                        initial={{ width: 0 }}
                        whileInView={{ width: `${(row.victim_house_cnt / maxVictim) * 100}%` }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.7, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
                      />
                    </span>
                    <span className="text-right text-muted-foreground tnum">{row.victim_house_cnt}호</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-[11px] text-muted-foreground">
              경공매지원서비스 신청 피해주택 소재지 — HUG 빅데이터 포털 집계
            </p>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
