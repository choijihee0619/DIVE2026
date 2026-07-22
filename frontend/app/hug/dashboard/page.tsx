"use client";

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Banknote, CalendarClock, FileStack, Percent, PiggyBank } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { ContractTable } from "@/components/contracts/ContractTable";
import { useContractList } from "@/hooks/useContractList";
import { ContractStatus } from "@/types/enums";
import { hugCasePriority } from "@/lib/contract-labels";
import { CLAIM_TYPE_TERM_KEY } from "@/lib/glossary";
import { hugService } from "@/services/hugService";
import type {
  HugSummary,
  IssuanceData,
  PriorityBond,
  PriorityListData,
  RecoveryGrade,
  RegionRiskData,
  VictimsData,
} from "@/types/hug";
import { AnimatedNumber } from "@/components/viz/AnimatedNumber";
import { ShapBars, type ShapFactor } from "@/components/viz/ShapBars";
import { FactorSentences } from "@/components/viz/FactorSentences";
import { Term, TermHelp } from "@/components/common/Term";
import { RecoveryPredictCard } from "@/components/hug/RecoveryPredictCard";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const FILTER_TABS: { value: string; label: string }[] = [
  { value: "all", label: "전체" },
  { value: ContractStatus.INCIDENT_REPORTED, label: "사고 접수" },
  { value: ContractStatus.TRANSFERRED_TO_HUG, label: "HUG 이관" },
  { value: ContractStatus.RECOVERY_IN_PROGRESS, label: "회수 진행" },
  { value: ContractStatus.AT_RISK, label: "위험" },
];

const GRADE_PILL: Record<RecoveryGrade, string> = {
  HIGH: "bg-hug-mint text-hug-green-deep",
  MED: "bg-warning-100 text-warning-700",
  LOW: "bg-danger-100 text-danger-600",
};

const GRADE_COLOR: Record<RecoveryGrade, string> = {
  HIGH: "var(--color-hug-green)",
  MED: "var(--color-warning-500)",
  LOW: "var(--color-danger-500)",
};

/** 7.14e12 → "7.1조", 4.8e8 → "4.8억". */
function formatWonShort(won: number): string {
  if (won >= 1e12) return `${(won / 1e12).toFixed(1)}조`;
  if (won >= 1e8) return `${(won / 1e8).toFixed(1)}억`;
  if (won >= 1e4) return `${Math.round(won / 1e4).toLocaleString("ko-KR")}만`;
  return won.toLocaleString("ko-KR");
}

/** 채권구분 값 — 용어 사전에 있으면 툴팁을 달아 렌더링. */
function ClaimType({ value }: { value: string }) {
  const termKey = CLAIM_TYPE_TERM_KEY[value];
  return termKey ? <Term k={termKey}>{value}</Term> : <>{value}</>;
}

/** "발생금액=4.8억(+0.129); 채권구분=구상채권(-0.052)" → ShapFactor[]. */
function parseTopFactors(raw: string): ShapFactor[] {
  return raw
    .split(";")
    .map((chunk) => chunk.trim())
    .map((chunk) => {
      const match = chunk.match(/^(.+)\(([-+][\d.]+)\)$/);
      if (!match) return null;
      return { label: match[1], value: Number.parseFloat(match[2]) };
    })
    .filter((f): f is ShapFactor => f !== null);
}

/** HUG-01 채권회수 대시보드: /hug/dashboard 5종(HOUSTA 실집계 + ML 시뮬레이션) + 플랫폼 계약 큐 실데이터. */
export default function HugDashboardPage() {
  const { contracts, errorMessage, reload } = useContractList();
  const [filter, setFilter] = useState<string>("all");

  const [summary, setSummary] = useState<HugSummary | null>(null);
  const [priority, setPriority] = useState<PriorityListData | null>(null);
  const [regionRisk, setRegionRisk] = useState<RegionRiskData | null>(null);
  const [issuance, setIssuance] = useState<IssuanceData | null>(null);
  const [victims, setVictims] = useState<VictimsData | null>(null);
  const [selectedBond, setSelectedBond] = useState<PriorityBond | null>(null);
  const [dashError, setDashError] = useState<string | null>(null);

  useEffect(() => {
    hugService.summary().then(setSummary).catch(() => setDashError("대시보드 집계를 불러오지 못했습니다."));
    hugService
      .priority(8)
      .then((data) => {
        setPriority(data);
        setSelectedBond(data.items[0] ?? null);
      })
      .catch(() => setPriority(null));
    hugService.regionRisk().then(setRegionRisk).catch(() => setRegionRisk(null));
    hugService.issuance().then(setIssuance).catch(() => setIssuance(null));
    hugService.victims().then(setVictims).catch(() => setVictims(null));
  }, []);

  const sorted = useMemo(() => {
    if (!contracts) return null;
    return [...contracts].sort(
      (a, b) =>
        hugCasePriority(a.contract_status) - hugCasePriority(b.contract_status) || b.deposit - a.deposit,
    );
  }, [contracts]);

  const visible = useMemo(() => {
    if (!sorted) return null;
    return filter === "all" ? sorted : sorted.filter((c) => c.contract_status === filter);
  }, [sorted, filter]);

  const gradeData = useMemo(() => {
    if (!summary) return [];
    return (Object.entries(summary.grade_counts) as [RecoveryGrade, number][]).map(([grade, count]) => ({
      name: grade,
      value: count,
    }));
  }, [summary]);

  /** 전국·수도권·지방 집계와 개별 시도를 분리. */
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

  /** 발급 추이 — 최근 36개월, issue_cnt만 사용(금액 필드는 원천 집계 버그). */
  const issuanceSeries = useMemo(
    () =>
      (issuance?.series ?? []).slice(-36).map((point) => ({
        month: point.yyyymm,
        count: point.issue_cnt,
      })),
    [issuance],
  );

  /** 선택 채권 top_factors → 발산 바·문장화 공용 구조 ("발생금액=4.8억" 분해). */
  const selectedFactors = useMemo(() => {
    if (!selectedBond) return [];
    return parseTopFactors(selectedBond.top_factors).map((factor) => {
      const [name, value] = factor.label.split("=");
      return { name, value, shap: factor.value };
    });
  }, [selectedBond]);

  const maxSidoRate = Math.max(...sidoRows.map((r) => r.accident_rate_pct), 0.001);
  const maxVictim = Math.max(...victimTop.rows.map((r) => r.victim_house_cnt), 1);

  const kpis: { key: string; label: React.ReactNode; icon: LucideIcon; tone: string; render: () => React.ReactNode }[] = [
    {
      key: "portfolio",
      label: <>관리 <Term k="bond">채권</Term></>,
      icon: FileStack,
      tone: "bg-hug-navy text-white",
      render: () =>
        summary ? (
          <>
            <AnimatedNumber value={summary.portfolio_count} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">건</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "claimed",
      label: <><Term k="subrogation">대위변제</Term> 잔고</>,
      icon: Banknote,
      tone: "bg-hug-sky text-hug-blue",
      render: () =>
        summary ? (
          <>
            <AnimatedNumber value={summary.claimed_total_won / 1e12} decimals={1} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">조원</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "expected",
      label: "예상 회수액",
      icon: PiggyBank,
      tone: "bg-hug-mint text-hug-green-deep",
      render: () =>
        summary ? (
          <>
            <AnimatedNumber value={summary.expected_recovery_total_won / 1e12} decimals={1} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">조원</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "ratio",
      label: <><Term k="recoveryRate">예상 회수율</Term> (중앙값)</>,
      icon: Percent,
      tone: "bg-hug-mint text-hug-green-deep",
      render: () =>
        summary ? (
          <>
            <AnimatedNumber value={summary.median_pred_recovery_ratio * 100} decimals={1} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">%</small>
          </>
        ) : (
          "—"
        ),
    },
    {
      key: "days",
      label: <>예상 <Term k="dividend">배당</Term> 소요일 (중앙값)</>,
      icon: CalendarClock,
      tone: "bg-warning-100 text-warning-700",
      render: () =>
        summary ? (
          <>
            <AnimatedNumber value={summary.median_pred_days} />
            <small className="ml-0.5 text-sm font-bold text-muted-foreground">일</small>
          </>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">채권회수 대시보드</h1>
          <p className="mt-1.5 text-muted-foreground">
            대위변제 채권 {summary ? summary.portfolio_count.toLocaleString("ko-KR") : "—"}건, 무엇부터 회수할
            것인가 — 회수율·소요기간 예측과 우선순위 스코어로 답합니다.
          </p>
        </div>
        <span className="ml-auto rounded-full bg-warning-100 px-3 py-1 text-xs font-bold text-warning-700">
          {summary?.basis ?? "합성데이터 기준 시뮬레이션"}
        </span>
      </motion.div>

      {dashError ? <p className="text-sm text-destructive">{dashError}</p> : null}

      {/* KPI 5종 — /hug/dashboard/summary */}
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

      {/* 우선순위 채권 + SHAP — /hug/dashboard/priority */}
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <motion.div variants={fadeUp} className="xl:col-span-2">
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                회수 우선순위 상위 채권 <TermHelp k="priorityScore" />
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  점수 = 회수율 {summary ? Math.round(summary.priority_weights.recovery * 100) : 60}% ·
                  속도 {summary ? Math.round(summary.priority_weights.speed * 100) : 40}%
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {priority === null ? (
                <Skeleton className="h-48 w-full" />
              ) : (
                <table className="w-full text-sm tnum">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">채권구분</th>
                      <th className="px-2">청구금액</th>
                      <th className="px-2">예상회수율</th>
                      <th className="px-2">예상소요</th>
                      <th className="px-2">
                        <Term k="recoveryGrade">등급</Term>
                      </th>
                      <th className="px-2 text-right">점수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {priority.items.map((bond, index) => {
                      const selected = selectedBond?.source_row_id === bond.source_row_id;
                      return (
                        <motion.tr
                          key={bond.source_row_id}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.3 }}
                          onClick={() => setSelectedBond(bond)}
                          className={cn(
                            "cursor-pointer border-b border-line/70 transition-colors last:border-b-0",
                            selected ? "bg-hug-sky/60" : "hover:bg-neutral-100",
                          )}
                        >
                          <td className="max-w-40 truncate py-2.5 pr-2 font-semibold" title={bond.product_name}>
                            <ClaimType value={bond.claim_type} />
                          </td>
                          <td className="px-2">{formatWonShort(bond.claimed_amount)}</td>
                          <td className="px-2">{(bond.pred_recovery_ratio * 100).toFixed(0)}%</td>
                          <td className="px-2">{bond.pred_days_to_dividend}일</td>
                          <td className="px-2">
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-xs font-bold",
                                GRADE_PILL[bond.pred_recovery_grade],
                              )}
                            >
                              {bond.pred_recovery_grade}
                            </span>
                          </td>
                          <td className="px-2 text-right text-base font-extrabold">{bond.priority_score.toFixed(1)}</td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                이 채권, 왜 이 점수인가 <TermHelp k="shap" />
                <span className="ml-2 text-xs font-semibold text-muted-foreground">판단 근거 Top 3</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex h-[calc(100%-64px)] flex-col gap-3">
              {selectedBond ? (
                <>
                  <div className="rounded-xl bg-neutral-100 p-3 text-xs">
                    <b>
                      <ClaimType value={selectedBond.claim_type} />
                    </b>{" "}
                    · 청구 {formatWonShort(selectedBond.claimed_amount)} 원 · 예상 회수{" "}
                    {formatWonShort(selectedBond.expected_recovery_won)} 원
                  </div>
                  <ShapBars
                    key={selectedBond.source_row_id}
                    factors={selectedFactors.map((factor) => ({ label: factor.name, value: factor.shap }))}
                  />
                  <FactorSentences factors={selectedFactors} />
                  <p className="mt-auto pt-2 text-xs text-muted-foreground">
                    ▲ 파랑은 회수율을 올린 요인, ▼ 빨강은 내린 요인입니다. 행을 클릭하면 해당 채권의 근거로
                    바뀝니다.
                  </p>
                </>
              ) : (
                <Skeleton className="h-40 w-full" />
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* 신규 채권 회수 예측 — POST /ml/recovery/predict */}
      <motion.div variants={fadeUp}>
        <RecoveryPredictCard />
      </motion.div>

      {/* 등급 분포 · 지역 사고율 · 피해주택 분포 */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                <Term k="recoveryGrade">회수등급</Term> 분포
              </CardTitle>
            </CardHeader>
            <CardContent className="flex items-center gap-4">
              <div className="h-40 w-40 shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={gradeData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={42}
                      outerRadius={66}
                      paddingAngle={3}
                      strokeWidth={0}
                      isAnimationActive
                      animationDuration={900}
                    >
                      {gradeData.map((entry) => (
                        <Cell key={entry.name} fill={GRADE_COLOR[entry.name as RecoveryGrade]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value) => [`${Number(value).toLocaleString("ko-KR")}건`]}
                      contentStyle={{ borderRadius: 12, border: "1px solid var(--color-line)", fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="min-w-0 flex-1 text-sm">
                {gradeData.map((entry) => (
                  <li key={entry.name} className="flex items-center gap-2 py-1">
                    <span
                      className="size-2.5 shrink-0 rounded-full"
                      style={{ background: GRADE_COLOR[entry.name as RecoveryGrade] }}
                    />
                    <span className="flex-1 font-semibold">{entry.name}</span>
                    <b className="tnum">{entry.value.toLocaleString("ko-KR")}건</b>
                  </li>
                ))}
                {summary ? (
                  <li className="mt-2 border-t border-line pt-2 text-xs text-muted-foreground">
                    상품: {summary.by_product.map((p) => `${p.product_name} ${p.cnt.toLocaleString("ko-KR")}건`).join(" · ")}
                  </li>
                ) : null}
              </ul>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">지역 사고율 — HOUSTA 실집계</CardTitle>
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
              <p className="mt-3 text-[11px] text-muted-foreground">발급건수 대비 사고건수 — HUG 빅데이터 포털(HOUSTA) 실데이터</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                전세사기 피해주택 분포{victimTop.year ? ` (${victimTop.year})` : ""}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {victims === null ? (
                <Skeleton className="h-36 w-full" />
              ) : (
                <ul className="flex flex-col gap-1.5 text-xs">
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
              <p className="mt-3 text-[11px] text-muted-foreground">경공매지원서비스 신청 피해주택 소재지 — HOUSTA 실데이터</p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* 발급 추이 — /hug/dashboard/issuance */}
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader>
            <CardTitle className="text-base font-extrabold">전세보증금반환보증 발급 추이 (최근 36개월)</CardTitle>
          </CardHeader>
          <CardContent>
            {issuance === null ? (
              <Skeleton className="h-48 w-full" />
            ) : (
              <div className="h-52 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={issuanceSeries} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
                    <defs>
                      <linearGradient id="issuanceFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--color-hug-blue)" stopOpacity={0.35} />
                        <stop offset="100%" stopColor="var(--color-hug-blue)" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 10, fill: "var(--color-ink-soft)" }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--color-line)" }}
                      interval={5}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "var(--color-ink-soft)" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      formatter={(value) => [`${Number(value).toLocaleString("ko-KR")}건`, "발급"]}
                      contentStyle={{ borderRadius: 12, border: "1px solid var(--color-line)", fontSize: 12 }}
                    />
                    <Area
                      type="monotone"
                      dataKey="count"
                      stroke="var(--color-hug-blue)"
                      strokeWidth={2}
                      fill="url(#issuanceFill)"
                      animationDuration={1100}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
            <p className="mt-2 text-[11px] text-muted-foreground">
              발급 모수(정상 대조군) — 지역 사고율의 분모로 쓰이는 HOUSTA 발급현황 실데이터
            </p>
          </CardContent>
        </Card>
      </motion.div>

      {/* 플랫폼 계약 사고 큐 — GET /contracts */}
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="flex flex-col gap-3">
            <CardTitle className="text-base font-extrabold">
              사건 우선순위 목록
              <span className="ml-2 text-xs font-semibold text-muted-foreground">플랫폼 등록 계약 기준</span>
            </CardTitle>
            <Tabs value={filter} onValueChange={(value) => setFilter(String(value))}>
              <TabsList>
                {FILTER_TABS.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value}>
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent>
            <ContractTable
              contracts={visible}
              errorMessage={errorMessage}
              onRetry={reload}
              emptyMessage={filter === "all" ? "표시할 사건이 없습니다." : "해당 상태의 사건이 없습니다."}
            />
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  );
}
