"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  BadgeCheck,
  CalendarClock,
  CircleAlert,
  Eye,
  FileCheck2,
  FileClock,
  Home,
  ScrollText,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { contractService } from "@/services/contractService";
import { evidenceService } from "@/services/evidenceService";
import { propertyService } from "@/services/propertyService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { Contract, ContractTimeline, ReturnPlan } from "@/types/contract";
import type { Property } from "@/types/property";
import type { EvidenceRequest } from "@/types/evidence";
import { ContractStatus, UserRole } from "@/types/enums";
import { contractPhase, formatDeposit } from "@/lib/contract-labels";
import {
  BLOCKCHAIN_STATUS_LABEL,
  EVIDENCE_TYPE_LABEL,
  HOUSING_TYPE_LABEL,
  LANDLORD_TYPE_LABEL,
  TIMELINE_EVENT_LABEL,
  VERIFICATION_STATUS_LABEL,
  verificationStatusBadgeVariant,
} from "@/lib/domain-labels";
import { StatusChip } from "@/components/viz/StatusChip";
import { TimelineList, type TimelineItem } from "@/components/viz/TimelineList";
import { GlossaryText, TermHelp } from "@/components/common/Term";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** 특약 이행 체크리스트 골격(19.1) — 전자계약 특약 데이터 연동 전까지의 정적 데모 항목. */
const CLAUSE_CHECKLIST = [
  { title: "근저당 말소 확인 특약", state: "done", detail: "잔금 지급 전 말소 완료 확인" },
  { title: "전입신고·확정일자 협조 특약", state: "done", detail: "전입·확정일자 절차 협조 완료" },
  { title: "등기사항 변동 통지 특약", state: "watch", detail: "만기까지 등기 변동 모니터링 중" },
] as const;

/** 역할별 하단 CTA — 같은 원본을 보되, 다음 행동은 역할마다 다르다. */
const ROLE_CTA: Partial<Record<UserRole, { href: (contractId: string) => string; label: string }>> = {
  [UserRole.TENANT]: {
    href: (id) => `/tenant/contracts/${id}`,
    label: "계약 상세로 이동 (진단·증빙 요청)",
  },
  [UserRole.LANDLORD]: {
    href: () => "/landlord",
    label: "임대인 대시보드로 이동 (증빙 제출·반환계획)",
  },
  [UserRole.HUG_ADMIN]: {
    href: () => "/hug/dashboard",
    label: "채권회수 대시보드로 이동",
  },
};

function daysUntil(dateStr: string): number {
  const target = new Date(`${dateStr}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}

function ddayLabel(days: number): string {
  if (days === 0) return "D-Day";
  return days > 0 ? `D-${days}` : `D+${-days}`;
}

interface ContractManagementViewProps {
  contractId: string;
}

/**
 * 19.1 계약 후 관리 화면 — 임차인·임대인·HUG 3자 공동 열람 뷰.
 *
 * 동일 계약을 어느 역할 화면에서 열어도 같은 원본(계약 내용·변경 이력·증빙 상태)을 보도록
 * `contracts`·`timeline_events`·`evidence_requests`·`return_plans`를 그대로 노출한다.
 * 관리 국면(반환 D-day·증빙 현황·특약 이행)을 전면 배치하고, 역할별 다음 행동만 CTA로 분기한다.
 */
export function ContractManagementView({ contractId }: ContractManagementViewProps) {
  const role = useSessionStore((state) => state.user?.role);

  const [contract, setContract] = useState<Contract | null>(null);
  const [property, setProperty] = useState<Property | null>(null);
  const [timeline, setTimeline] = useState<ContractTimeline | null>(null);
  const [returnPlan, setReturnPlan] = useState<ReturnPlan | null>(null);
  const [evidenceRequests, setEvidenceRequests] = useState<EvidenceRequest[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    contractService
      .get(contractId)
      .then((c) => {
        setContract(c);
        propertyService.get(c.property_id).then(setProperty).catch(() => setProperty(null));
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "계약 정보를 불러오지 못했습니다."),
      );
    contractService.timeline(contractId).then(setTimeline).catch(() => setTimeline(null));
    contractService.returnPlan(contractId).then(setReturnPlan).catch(() => setReturnPlan(null));
    evidenceService
      .listRequests({ contractId })
      .then((d) => setEvidenceRequests(d.items))
      .catch(() => setEvidenceRequests([]));
  }, [contractId]);

  useEffect(() => {
    load();
  }, [load]);

  const timelineItems: TimelineItem[] = useMemo(
    () =>
      (timeline?.events ?? []).map((event) => ({
        time: event.occurred_at.slice(0, 16).replace("T", " "),
        title: TIMELINE_EVENT_LABEL[event.event_type] ?? event.event_type,
        level: event.blockchain_tx_id ? "ok" : "info",
        trailing: event.blockchain_tx_id ? (
          <Link
            href={`/blockchain/${event.blockchain_tx_id}`}
            className="font-semibold text-hug-blue underline underline-offset-2"
          >
            블록체인 기록 보기
          </Link>
        ) : (
          <span className="text-muted-foreground">
            {BLOCKCHAIN_STATUS_LABEL[event.blockchain_status] ?? event.blockchain_status}
          </span>
        ),
      })),
    [timeline],
  );

  if (errorMessage && !contract) {
    return (
      <Card className="rounded-2xl">
        <CardContent className="py-10 text-center text-sm text-destructive">{errorMessage}</CardContent>
      </Card>
    );
  }

  if (!contract) {
    return (
      <div className="flex flex-col gap-3" aria-label="불러오는 중">
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-44 w-full rounded-2xl" />
        <Skeleton className="h-44 w-full rounded-2xl" />
      </div>
    );
  }

  const phase = contractPhase(contract.contract_status);
  const atRisk =
    contract.contract_status === ContractStatus.AT_RISK ||
    contract.contract_status === ContractStatus.INCIDENT_REPORTED;

  const maturityDays = daysUntil(contract.contract_end_date);
  const returnDays =
    returnPlan?.planned_return_date != null ? daysUntil(returnPlan.planned_return_date) : null;
  /** 전면 D-day: 반환계획이 있으면 반환 예정일, 없으면 계약 만기 기준. */
  const heroDays = returnDays ?? maturityDays;
  const heroUrgent = heroDays <= 90;

  const verifiedCount = (evidenceRequests ?? []).filter((r) => r.verification_status === "Verified").length;
  const cta = role ? ROLE_CTA[role] : undefined;

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      {/* 헤더 — 3자 공동 열람 안내 */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-muted-foreground">계약 후 관리</p>
          <h1 className="mt-1 flex flex-wrap items-center gap-2.5 text-2xl font-extrabold tracking-tight">
            계약 <span className="font-mono text-xl">{contract.contract_id}</span>
            <StatusChip status={contract.contract_status} />
          </h1>
          <p className="mt-1.5 text-muted-foreground">
            계약 내용·변경 이력·증빙 상태를 반환 시점까지 한 화면에서 관리합니다.
          </p>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-hug-sky px-3.5 py-2 text-xs font-bold text-hug-blue">
          <Users size={14} />
          3자 공동 열람
          <TermHelp k="threePartyView" className="text-hug-blue/70" />
        </span>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
      {phase === "in_progress" ? (
        <motion.p
          variants={fadeUp}
          className="rounded-xl border border-line bg-neutral-100 px-4 py-3 text-sm text-muted-foreground"
        >
          이 계약은 아직 <b>진행중</b> 단계입니다. 계약이 확정되면 반환 D-day·증빙 현황이 이 화면에서
          본격적으로 관리됩니다.
        </motion.p>
      ) : null}

      {/* 관리 국면 KPI — 반환 D-day 전면 배치 */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <motion.div variants={fadeUp}>
          <Card
            className={cn(
              "h-full rounded-2xl border-line shadow-card",
              atRisk || returnPlan?.early_warning ? "border-2 border-danger-500/40" : "",
            )}
          >
            <CardContent className="flex h-full flex-col justify-between gap-2 pt-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground">
                  {returnDays !== null ? "보증금 반환 예정" : "계약 만기"}
                </span>
                <CalendarClock size={16} className={heroUrgent ? "text-danger-500" : "text-hug-blue"} />
              </div>
              <b className={cn("text-3xl font-extrabold tnum", heroUrgent ? "text-danger-600" : "")}>
                {ddayLabel(heroDays)}
              </b>
              <p className="text-xs text-muted-foreground tnum">
                {returnDays !== null
                  ? `${returnPlan?.planned_return_date} 반환 예정`
                  : `${contract.contract_end_date} 만기`}
                {returnPlan?.early_warning ? (
                  <Badge variant="destructive" className="ml-1.5 align-middle">
                    조기 경보
                  </Badge>
                ) : null}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-between gap-2 pt-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground">보증금</span>
                <ShieldCheck size={16} className="text-hug-green" />
              </div>
              <b className="text-3xl font-extrabold tnum">{formatDeposit(contract.deposit)}</b>
              <p className="text-xs text-muted-foreground tnum">
                {contract.contract_start_date} ~ {contract.contract_end_date}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-between gap-2 pt-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground">증빙 현황</span>
                <FileCheck2 size={16} className="text-hug-blue" />
              </div>
              <b className="text-3xl font-extrabold tnum">
                {evidenceRequests === null ? "—" : `${verifiedCount}/${evidenceRequests.length}`}
              </b>
              <p className="text-xs text-muted-foreground">요청 대비 검증 완료</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardContent className="flex h-full flex-col justify-between gap-2 pt-5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-muted-foreground">반환계획</span>
                <FileClock size={16} className={returnPlan ? "text-hug-green" : "text-warning-600"} />
              </div>
              <b className="text-xl font-extrabold leading-8">
                {returnPlan ? "제출됨" : "미제출"}
              </b>
              <p className="text-xs text-muted-foreground">
                {returnPlan
                  ? `반환 방법: ${returnPlan.return_method ?? "-"}`
                  : "임대인이 아직 반환계획을 제출하지 않았습니다."}
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {/* 계약 원본 — 3자가 보는 동일 소스 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-extrabold">계약 원본</CardTitle>
              <Link
                href={`/registry/${contract.property_id}`}
                className="flex items-center gap-1 rounded-full border border-line px-3 py-1.5 text-xs font-bold text-hug-blue transition-colors hover:bg-hug-sky"
              >
                <ScrollText size={13} />
                등기부 원문
              </Link>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-3 text-sm">
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-sky text-hug-blue">
                    <Home size={16} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-xs text-muted-foreground">매물</span>
                    <b className="block truncate">
                      {property?.address.road_address ||
                        property?.address.jibun_address ||
                        `매물 ${contract.property_id.slice(0, 8)}`}
                    </b>
                  </span>
                </li>
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-sky text-hug-blue">
                    <UserRound size={16} />
                  </span>
                  <span>
                    <span className="block text-xs text-muted-foreground">임대인 유형 · 주택 유형</span>
                    <b>
                      {LANDLORD_TYPE_LABEL[contract.landlord_type] ?? contract.landlord_type} ·{" "}
                      {HOUSING_TYPE_LABEL[contract.housing_type] ?? contract.housing_type}
                    </b>
                  </span>
                </li>
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-mint text-hug-green-deep">
                    <CalendarClock size={16} />
                  </span>
                  <span>
                    <span className="block text-xs text-muted-foreground">계약 기간</span>
                    <b className="tnum">
                      {contract.contract_start_date} ~ {contract.contract_end_date}
                    </b>
                  </span>
                </li>
              </ul>
              <p className="mt-4 rounded-xl bg-neutral-100 px-3.5 py-2.5 text-xs text-muted-foreground">
                최근 변경 {contract.updated_at.slice(0, 16).replace("T", " ")} — 모든 변경은 아래 변경
                이력에 기록되어 임차인·임대인·HUG가 동일하게 확인합니다.
              </p>
            </CardContent>
          </Card>
        </motion.div>

        {/* 특약 이행 체크리스트(골격) */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">특약 이행 현황</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              {CLAUSE_CHECKLIST.map((clause) => (
                <div
                  key={clause.title}
                  className="flex items-center gap-3 rounded-xl border border-line p-3"
                >
                  {clause.state === "done" ? (
                    <BadgeCheck size={18} className="shrink-0 text-hug-green" />
                  ) : (
                    <Eye size={18} className="shrink-0 text-warning-600" />
                  )}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold">
                      <GlossaryText text={clause.title} />
                    </p>
                    <p className="truncate text-xs text-muted-foreground">{clause.detail}</p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-2.5 py-1 text-xs font-bold",
                      clause.state === "done"
                        ? "bg-hug-mint text-hug-green-deep"
                        : "bg-warning-100 text-warning-700",
                    )}
                  >
                    {clause.state === "done" ? "이행 확인" : "모니터링"}
                  </span>
                </div>
              ))}
              <p className="mt-1 text-xs text-muted-foreground">
                전자계약에서 합의한 특약 기준 — 이행 여부가 바뀌면 변경 이력에 기록됩니다.
              </p>
            </CardContent>
          </Card>
        </motion.div>

        {/* 증빙 제출 이력 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">증빙 제출 이력</CardTitle>
            </CardHeader>
            <CardContent>
              {evidenceRequests === null ? (
                <Skeleton className="h-16 w-full" />
              ) : evidenceRequests.length === 0 ? (
                <p className="text-sm text-muted-foreground">아직 요청·제출된 증빙이 없습니다.</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {evidenceRequests.map((request) => (
                    <li
                      key={request.evidence_request_id}
                      className="flex items-center gap-3 rounded-xl border border-line p-3 text-sm"
                    >
                      <Badge variant={verificationStatusBadgeVariant(request.verification_status)}>
                        {VERIFICATION_STATUS_LABEL[request.verification_status] ?? request.verification_status}
                      </Badge>
                      <span className="font-semibold">
                        {EVIDENCE_TYPE_LABEL[request.evidence_type] ?? request.evidence_type}
                      </span>
                      <span className="truncate text-muted-foreground">{request.reason}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* 변경 이력 — timeline_events 공유 소스 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">변경 이력</CardTitle>
            </CardHeader>
            <CardContent>
              {timeline === null ? (
                <Skeleton className="h-16 w-full" />
              ) : timelineItems.length === 0 ? (
                <p className="text-sm text-muted-foreground">기록된 이벤트가 없습니다.</p>
              ) : (
                <TimelineList items={timelineItems} />
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {atRisk ? (
        <motion.p
          variants={fadeUp}
          className="flex items-center gap-2 rounded-xl border-2 border-danger-500/40 bg-danger-100/40 px-4 py-3 text-sm font-semibold text-danger-600"
        >
          <CircleAlert size={16} className="shrink-0" />
          위험 신호가 감지된 계약입니다. 증빙 현황과 반환계획을 우선 확인하세요.
        </motion.p>
      ) : null}

      {cta ? (
        <motion.div variants={fadeUp}>
          <Link
            href={cta.href(contract.contract_id)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-card px-4 py-2.5 text-sm font-bold text-hug-blue transition-colors hover:bg-hug-sky"
          >
            {cta.label} →
          </Link>
        </motion.div>
      ) : null}
    </motion.div>
  );
}
