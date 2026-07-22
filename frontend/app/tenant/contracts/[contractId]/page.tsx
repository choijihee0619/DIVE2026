"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  CalendarDays,
  FileSignature,
  Home,
  Info,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  UserRound,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { esignService } from "@/services/esignService";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { contractService } from "@/services/contractService";
import { riskService } from "@/services/riskService";
import { evidenceService } from "@/services/evidenceService";
import { propertyService } from "@/services/propertyService";
import { ApiError } from "@/services/apiClient";
import type { Contract, ContractTimeline, ReturnPlan } from "@/types/contract";
import type { Property } from "@/types/property";
import type { RiskAssessment } from "@/types/risk";
import type { EvidenceRequest } from "@/types/evidence";
import { contractPhase, formatDeposit } from "@/lib/contract-labels";
import { GlossaryText } from "@/components/common/Term";
import {
  BLOCKCHAIN_STATUS_LABEL,
  EVIDENCE_TYPE_LABEL,
  HOUSING_TYPE_LABEL,
  LANDLORD_TYPE_LABEL,
  RISK_GRADE_LABEL,
  TIMELINE_EVENT_LABEL,
  VERIFICATION_STATUS_LABEL,
  verificationStatusBadgeVariant,
} from "@/lib/domain-labels";
import { ContractStatus } from "@/types/enums";
import { StatusChip } from "@/components/viz/StatusChip";
import { DonutGauge } from "@/components/viz/DonutGauge";
import { RiskSignalList, type RiskSignal, type SignalLevel } from "@/components/viz/RiskSignals";
import { TimelineList, type TimelineItem } from "@/components/viz/TimelineList";
import { staggerContainer, fadeUp } from "@/lib/motion";

/** 생애주기 진행률(도넛 게이지)용 상태 순서. */
const STATUS_ORDER: ContractStatus[] = Object.values(ContractStatus);

const SEVERITY_TO_LEVEL: Record<string, SignalLevel> = {
  high: "danger",
  medium: "warn",
  low: "ok",
};

/** 260721 목업 4번의 "전세 진행 시 넣어야 하는 필수 특약" AI 추천 카드(정적 데모 콘텐츠). */
const AI_CLAUSES = [
  {
    icon: ShieldAlert,
    tone: "text-danger-500",
    title: "근저당 말소 확인 특약",
    description: "잔금 지급 전 근저당권 말소 완료를 확인한 후 지급하도록 명시",
  },
  {
    icon: Info,
    tone: "text-hug-blue",
    title: "전입신고·확정일자 협조 특약",
    description: "임대인은 전입 및 확정일자 절차에 적극 협조해야 합니다.",
  },
  {
    icon: FileSignature,
    tone: "text-hug-green",
    title: "등기사항 변동 통지 특약",
    description: "계약일부터 잔금일까지 등기사항 변경 시 즉시 임차인에게 통보",
  },
];

/**
 * TEN-01 계약 상세: 계약 정보 + 위험진단 + 증빙 요청 + 타임라인 + 반환계획 실데이터.
 *
 * MODIFIED 2026-07-21: 위험진단 실행 시 CODEF 등기부 refresh를 먼저 수행하도록 변경 — 기존에는
 * diagnose만 호출해 DB의 mock 스냅샷을 읽었고 모든 계약의 진단 결과가 동일했음. 집합건물 특정을
 * 위해 매물에 동·호수가 없으면 입력 다이얼로그를 띄운 뒤 조회하며, 등기부 원문 열람 링크를 추가.
 */
export default function ContractDetailPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const router = useRouter();
  const [isStartingEsign, setIsStartingEsign] = useState(false);

  const [contract, setContract] = useState<Contract | null>(null);
  const [property, setProperty] = useState<Property | null>(null);
  const [timeline, setTimeline] = useState<ContractTimeline | null>(null);
  const [returnPlan, setReturnPlan] = useState<ReturnPlan | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [evidenceRequests, setEvidenceRequests] = useState<EvidenceRequest[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDiagnosing, setIsDiagnosing] = useState(false);

  const [dongHoDialogOpen, setDongHoDialogOpen] = useState(false);
  const [dongInput, setDongInput] = useState("");
  const [hoInput, setHoInput] = useState("");

  const [requestDialogOpen, setRequestDialogOpen] = useState(false);
  const [requestType, setRequestType] = useState("REGISTRY_CANCELLATION_PROOF");
  const [requestReason, setRequestReason] = useState("");
  const [isSubmittingRequest, setIsSubmittingRequest] = useState(false);

  const load = useCallback(() => {
    contractService
      .get(contractId)
      .then((c) => {
        setContract(c);
        if (c.risk_assessment_id) {
          riskService.get(c.risk_assessment_id).then(setRisk).catch(() => setRisk(null));
        }
        propertyService
          .get(c.property_id)
          .then((p) => {
            setProperty(p);
            setDongInput((prev) => prev || String(p.address.dong ?? ""));
            setHoInput((prev) => prev || String(p.address.ho ?? ""));
          })
          .catch(() => setProperty(null));
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

  /** 등기부 refresh(CODEF 실조회) → 위험진단 순서로 실행. 등기부 실패 시에도 진단은 진행(백엔드 mock 폴백). */
  const executeDiagnosis = (dong: string, ho: string) => {
    if (!contract || isDiagnosing) return;
    setIsDiagnosing(true);
    propertyService
      .refreshRegistry(contract.property_id, { deposit: contract.deposit, dong, ho })
      .then((snapshot) => {
        if (snapshot.source_system === "demo_scenario") {
          toast.info("샌드박스는 주소 무관 고정표본이라, 매물 주소별 데모 시나리오로 진단합니다.");
        } else if (snapshot.source_system !== "api_live") {
          toast.warning("등기부 실조회에 실패해 Mock 데이터로 진단합니다.");
        }
      })
      .catch(() => toast.warning("등기부 조회에 실패했습니다. 기존 데이터로 진단합니다."))
      .then(() =>
        riskService.diagnose({
          property_id: contract.property_id,
          deposit: contract.deposit,
          contract_start_date: contract.contract_start_date,
          contract_end_date: contract.contract_end_date,
          landlord_type: contract.landlord_type,
          housing_type: contract.housing_type,
          landlord_id: contract.landlord_id,
          contract_id: contract.contract_id,
        }),
      )
      .then((result) => {
        setRisk(result);
        load();
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "위험진단에 실패했습니다."),
      )
      .finally(() => setIsDiagnosing(false));
  };

  const runDiagnosis = () => {
    if (!contract || isDiagnosing) return;
    // 집합건물 등기부는 동·호수까지 있어야 특정 가능 — 매물에 없으면 먼저 입력받는다
    if (!dongInput.trim() || !hoInput.trim()) {
      setDongHoDialogOpen(true);
      return;
    }
    executeDiagnosis(dongInput.trim(), hoInput.trim());
  };

  const submitDongHo = () => {
    if (!dongInput.trim() || !hoInput.trim()) return;
    setDongHoDialogOpen(false);
    executeDiagnosis(dongInput.trim(), hoInput.trim());
  };

  const startEsign = () => {
    if (isStartingEsign) return;
    setIsStartingEsign(true);
    esignService
      .createSession(contractId)
      .then((session) => {
        toast.success(`전자계약 세션 ${session.session_code}로 이동합니다.`);
        router.push(`/esign/${session.session_id}`);
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "전자계약 세션 생성에 실패했습니다."),
      )
      .finally(() => setIsStartingEsign(false));
  };

  const submitEvidenceRequest = () => {
    if (!requestReason.trim() || isSubmittingRequest) return;
    setIsSubmittingRequest(true);
    evidenceService
      .createRequest({
        contract_id: contractId,
        reason: requestReason.trim(),
        evidence_type: requestType,
        risk_assessment_id: risk?.risk_assessment_id ?? null,
      })
      .then(() => {
        setRequestDialogOpen(false);
        setRequestReason("");
        load();
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "증빙 요청에 실패했습니다."),
      )
      .finally(() => setIsSubmittingRequest(false));
  };

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
        <Skeleton className="h-32 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  const statusIndex = STATUS_ORDER.indexOf(contract.contract_status);
  const lifecycleRatio = (statusIndex + 1) / STATUS_ORDER.length;
  const atRisk =
    contract.contract_status === ContractStatus.AT_RISK ||
    contract.contract_status === ContractStatus.INCIDENT_REPORTED;

  const riskSignals: RiskSignal[] = (risk?.risk_factors ?? []).map((factor) => ({
    level: SEVERITY_TO_LEVEL[factor.severity] ?? "info",
    title: <GlossaryText text={factor.title} />,
    detail: <GlossaryText text={factor.description} />,
  }));

  const timelineItems: TimelineItem[] = (timeline?.events ?? []).map((event) => ({
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
  }));

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <p className="text-sm font-semibold text-muted-foreground">내 계약</p>
        <h1 className="mt-1 text-2xl font-extrabold tracking-tight">
          계약 <span className="font-mono text-xl">{contract.contract_id}</span>
        </h1>
        <p className="mt-1.5 text-muted-foreground">보증 계약 현황을 확인하고 안전한 전세 생활을 시작하세요.</p>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      {/* 관리 국면(계약 후)이면 3자 공동 열람 화면으로 유도 — README §19.1 */}
      {contractPhase(contract.contract_status) === "managed" ? (
        <motion.div variants={fadeUp}>
          <Link
            href={`/contracts/${contract.contract_id}/manage`}
            className="flex items-center gap-3 rounded-2xl border-2 border-hug-blue/30 bg-hug-sky px-4 py-3.5 transition-colors hover:border-hug-blue/60"
          >
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-blue text-white">
              <Users size={16} />
            </span>
            <span className="min-w-0 flex-1">
              <b className="block text-sm text-hug-navy">이 계약은 관리중(계약 후) 단계입니다</b>
              <span className="block truncate text-xs text-hug-navy/70">
                반환 D-day·증빙 현황·특약 이행을 임차인·임대인·HUG가 같은 화면으로 확인합니다.
              </span>
            </span>
            <span className="shrink-0 text-sm font-bold text-hug-blue">계약 후 관리 →</span>
          </Link>
        </motion.div>
      ) : null}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        {/* 계약 현황 요약 — 좌: 항목, 우: 생애주기 도넛 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-extrabold">계약 현황 요약</CardTitle>
              <StatusChip status={contract.contract_status} />
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-6">
              <ul className="flex min-w-0 flex-1 flex-col gap-3 text-sm">
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-sky text-hug-blue">
                    <CalendarDays size={16} />
                  </span>
                  <span>
                    <span className="block text-xs text-muted-foreground">계약 기간</span>
                    <b className="tnum">
                      {contract.contract_start_date} ~ {contract.contract_end_date}
                    </b>
                  </span>
                </li>
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-sky text-hug-blue">
                    <UserRound size={16} />
                  </span>
                  <span>
                    <span className="block text-xs text-muted-foreground">임대인 유형</span>
                    <b>{LANDLORD_TYPE_LABEL[contract.landlord_type] ?? contract.landlord_type}</b>
                  </span>
                </li>
                <li className="flex items-center gap-3">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-hug-mint text-hug-green-deep">
                    <Home size={16} />
                  </span>
                  <span>
                    <span className="block text-xs text-muted-foreground">주택 유형</span>
                    <b>{HOUSING_TYPE_LABEL[contract.housing_type] ?? contract.housing_type}</b>
                  </span>
                </li>
              </ul>
              <DonutGauge
                ratio={lifecycleRatio}
                color={atRisk ? "var(--color-danger-500)" : "var(--color-hug-blue)"}
                className="mx-auto"
              >
                <ShieldCheck size={20} className={atRisk ? "text-danger-500" : "text-hug-blue"} />
                <span className="mt-1 text-xs font-bold text-muted-foreground">보증금</span>
                <b className="text-lg leading-tight tnum">{formatDeposit(contract.deposit)}</b>
              </DonutGauge>
              <Button
                onClick={startEsign}
                disabled={isStartingEsign}
                className="w-full rounded-xl font-bold"
                variant="outline"
              >
                <FileSignature size={15} />
                {isStartingEsign ? "세션 준비 중..." : "전자계약 공동세션 진행 →"}
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* 위험 진단 결과 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-extrabold">위험 진단 결과</CardTitle>
              <div className="flex items-center gap-1.5">
                <Link
                  href={`/registry/${contract.property_id}`}
                  className="flex items-center gap-1 rounded-full border border-line px-3 py-1.5 text-xs font-bold text-hug-blue transition-colors hover:bg-hug-sky"
                >
                  <ScrollText size={13} />
                  등기부 원문
                </Link>
                <Button onClick={runDiagnosis} disabled={isDiagnosing} size="sm" className="rounded-full">
                  {isDiagnosing ? "진단 중..." : risk ? "재진단" : "위험진단 실행"}
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {risk ? (
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
                    <span
                      className={
                        "rounded-full px-3 py-1 text-xs font-bold " +
                        (risk.risk_grade === "HIGH"
                          ? "bg-danger-100 text-danger-600"
                          : risk.risk_grade === "MEDIUM"
                            ? "bg-warning-100 text-warning-700"
                            : "bg-hug-mint text-hug-green-deep")
                      }
                    >
                      위험등급 {RISK_GRADE_LABEL[risk.risk_grade] ?? risk.risk_grade}
                    </span>
                    <span className="text-muted-foreground tnum">
                      위험점수 {risk.risk_score}점 · 신뢰도 {(risk.confidence * 100).toFixed(0)}% · 데이터
                      완성도 {(risk.data_completeness * 100).toFixed(0)}%
                    </span>
                  </div>
                  {riskSignals.length > 0 ? (
                    <div>
                      <h3 className="mb-1 text-sm font-bold">위험 요인</h3>
                      <RiskSignalList signals={riskSignals} />
                    </div>
                  ) : null}
                  {risk.recommended_actions.length > 0 ? (
                    <div className="rounded-xl bg-hug-sky p-3.5">
                      <h3 className="mb-1.5 text-sm font-bold text-hug-navy">권장 조치</h3>
                      <ol className="list-decimal pl-5 text-sm text-hug-navy/80">
                        {risk.recommended_actions.map((action) => (
                          <li key={action}>
                            <GlossaryText text={action} />
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  아직 위험진단을 실행하지 않았습니다. 진단을 실행하면 규칙 엔진이 위험 요인과 권장 조치를
                  제시합니다.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* 계약 타임라인 */}
        <motion.div variants={fadeUp}>
          <Card className="h-full rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">계약 타임라인</CardTitle>
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

        {/* 보증금 반환 계획 + 증빙 요청 */}
        <motion.div variants={fadeUp} className="flex flex-col gap-5">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">보증금 반환 계획</CardTitle>
            </CardHeader>
            <CardContent>
              {returnPlan ? (
                <div className="flex flex-col gap-2 text-sm">
                  <div className="flex items-center gap-3">
                    {returnPlan.early_warning ? <Badge variant="destructive">조기 경보</Badge> : null}
                    {typeof returnPlan.d_day === "number" ? (
                      <span className="text-base font-extrabold tnum">
                        반환 예정 D{returnPlan.d_day >= 0 ? `-${returnPlan.d_day}` : `+${-returnPlan.d_day}`}
                      </span>
                    ) : null}
                  </div>
                  <p>
                    <span className="text-muted-foreground">반환 예정일: </span>
                    <b className="tnum">{returnPlan.planned_return_date ?? "-"}</b>
                  </p>
                  <p>
                    <span className="text-muted-foreground">반환 방법: </span>
                    {returnPlan.return_method ?? "-"}
                  </p>
                  {returnPlan.note ? (
                    <p>
                      <span className="text-muted-foreground">비고: </span>
                      {returnPlan.note}
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-hug-sky text-hug-blue">
                    <ShieldCheck size={18} />
                  </span>
                  <p className="text-sm text-muted-foreground">임대인이 아직 반환계획을 제출하지 않았습니다.</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-extrabold">증빙 요청</CardTitle>
              <Button
                size="sm"
                variant="outline"
                className="rounded-full"
                onClick={() => setRequestDialogOpen(true)}
              >
                증빙 요청 생성
              </Button>
            </CardHeader>
            <CardContent>
              {evidenceRequests === null ? (
                <Skeleton className="h-16 w-full" />
              ) : evidenceRequests.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  증빙 요청이 없습니다. 위험진단의 권장 조치에 따라 임대인에게 증빙을 요청해 보세요.
                </p>
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
      </div>

      {/* AI 추천 필수 특약 — 목업 4번 우하단 보라 카드 */}
      <motion.div variants={fadeUp}>
        <Card className="rounded-2xl border-2 border-violet-300 shadow-card">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2 text-base font-extrabold">
                전세 진행 시 넣어야 하는 필수 특약
                <span className="flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-bold text-violet-700">
                  <Sparkles size={12} />
                  AI 추천
                </span>
              </CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                현재 계약의 위험 요인을 보완하기 위해 다음 특약을 포함하는 것을 권장합니다.
              </p>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-2.5">
            {AI_CLAUSES.map((clause) => {
              const Icon = clause.icon;
              return (
                <div
                  key={clause.title}
                  className="flex items-center gap-3 rounded-xl border border-line p-3.5"
                >
                  <Icon size={18} className={`shrink-0 ${clause.tone}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold">
                      <GlossaryText text={clause.title} />
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      <GlossaryText text={clause.description} />
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="shrink-0 rounded-full"
                    onClick={() => toast.success(`"${clause.title}"이 계약서 초안에 추가되었습니다.`)}
                  >
                    특약 추가
                  </Button>
                </div>
              );
            })}
            <p className="mt-1 text-xs text-muted-foreground">
              근거: 상담사례 유사 분쟁 빈출 특약 — AI 상담에서 자세히 확인할 수 있어요.
            </p>
          </CardContent>
        </Card>
      </motion.div>

      <Dialog open={dongHoDialogOpen} onOpenChange={setDongHoDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>등기부 조회 — 동·호수 입력</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            집합건물(아파트·오피스텔 등)의 등기부는 동·호수까지 입력해야 해당 세대가 특정됩니다.
            {property?.address.road_address ? ` (${property.address.road_address})` : ""}
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="registry-dong">동</Label>
              <Input
                id="registry-dong"
                value={dongInput}
                onChange={(event) => setDongInput(event.target.value)}
                placeholder="예: 801"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="registry-ho">호수</Label>
              <Input
                id="registry-ho"
                value={hoInput}
                onChange={(event) => setHoInput(event.target.value)}
                placeholder="예: 804"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDongHoDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={submitDongHo} disabled={!dongInput.trim() || !hoInput.trim()}>
              등기부 조회 후 진단
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={requestDialogOpen} onOpenChange={setRequestDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>임대인에게 증빙 요청</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evidence-type">증빙 유형</Label>
              <select
                id="evidence-type"
                value={requestType}
                onChange={(event) => setRequestType(event.target.value)}
                className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {Object.entries(EVIDENCE_TYPE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="evidence-reason">요청 사유</Label>
              <Input
                id="evidence-reason"
                value={requestReason}
                onChange={(event) => setRequestReason(event.target.value)}
                placeholder="예: 선순위 근저당 말소 확인 필요"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRequestDialogOpen(false)}>
              취소
            </Button>
            <Button onClick={submitEvidenceRequest} disabled={!requestReason.trim() || isSubmittingRequest}>
              {isSubmittingRequest ? "요청 중..." : "요청 보내기"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </motion.div>
  );
}
