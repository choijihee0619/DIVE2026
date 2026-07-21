"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { LifeBuoy, Siren } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { incidentService } from "@/services/incidentService";
import { ApiError } from "@/services/apiClient";
import { useContractList } from "@/hooks/useContractList";
import {
  INCIDENT_STATUS_LABEL,
  INCIDENT_TYPE_LABEL,
  type Incident,
  type IncidentType,
} from "@/types/incident";
import { formatDeposit } from "@/lib/contract-labels";
import { TimelineList } from "@/components/viz/TimelineList";
import type { SignalLevel } from "@/components/viz/RiskSignals";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

const STATUS_TONE: Record<string, string> = {
  Received: "bg-hug-sky text-hug-blue",
  Reviewing: "bg-warning-100 text-warning-700",
  TransferredToRecovery: "bg-hug-mint text-hug-green-deep",
  Closed: "bg-neutral-200 text-neutral-600",
};

const STATUS_LEVEL: Record<string, SignalLevel> = {
  Received: "info",
  Reviewing: "warn",
  TransferredToRecovery: "ok",
  Closed: "ok",
};

/** TEN-07 사고 접수(축 B 진입점): POST /incidents + 내 접수 현황·처리 타임라인. */
export default function TenantIncidentsPage() {
  const { contracts } = useContractList();
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [incidentType, setIncidentType] = useState<IncidentType>("DEPOSIT_NOT_RETURNED");
  const [contractId, setContractId] = useState("");
  const [depositAmount, setDepositAmount] = useState("");
  const [occurredDate, setOccurredDate] = useState("");
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const load = useCallback(() => {
    incidentService
      .list()
      .then((data) => setIncidents(data.items))
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "사고 접수 내역을 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (description.trim().length < 10) {
      toast.error("상황 설명을 10자 이상 입력해 주세요.");
      return;
    }
    if (isSubmitting) return;
    setIsSubmitting(true);
    incidentService
      .create({
        incident_type: incidentType,
        description: description.trim(),
        contract_id: contractId || null,
        deposit_amount: depositAmount ? Number(depositAmount) : null,
        occurred_date: occurredDate || null,
      })
      .then((incident) => {
        toast.success(`사고가 접수되었습니다 (${incident.incident_type_label}). HUG 검토가 시작됩니다.`);
        setDescription("");
        setDepositAmount("");
        setOccurredDate("");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "사고 접수에 실패했습니다."),
      )
      .finally(() => setIsSubmitting(false));
  };

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
          <Siren size={22} className="text-danger-500" />
          사고 접수 / 지원 안내
        </h1>
        <p className="mt-1.5 text-muted-foreground">
          보증금 미반환·경매 개시 등 사고 상황을 접수하면 HUG 검토를 거쳐 회수 절차로 연결됩니다.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
        {/* 접수 폼 */}
        <motion.div variants={fadeUp}>
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">새 사고 접수</CardTitle>
            </CardHeader>
            <CardContent>
              <form className="flex flex-col gap-4" onSubmit={submit}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="incident-type">사고 유형</Label>
                  <select
                    id="incident-type"
                    value={incidentType}
                    onChange={(event) => setIncidentType(event.target.value as IncidentType)}
                    className={inputClass}
                  >
                    {Object.entries(INCIDENT_TYPE_LABEL).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="incident-contract">관련 계약 (선택)</Label>
                  <select
                    id="incident-contract"
                    value={contractId}
                    onChange={(event) => setContractId(event.target.value)}
                    className={inputClass}
                  >
                    <option value="">선택 안 함</option>
                    {(contracts ?? []).map((contract) => (
                      <option key={contract.contract_id} value={contract.contract_id}>
                        {contract.contract_id} · {formatDeposit(contract.deposit)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="incident-deposit">보증금 (원, 선택)</Label>
                    <input
                      id="incident-deposit"
                      type="number"
                      min={0}
                      value={depositAmount}
                      onChange={(event) => setDepositAmount(event.target.value)}
                      placeholder="예: 180000000"
                      className={inputClass}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label htmlFor="incident-date">발생일 (선택)</Label>
                    <input
                      id="incident-date"
                      type="date"
                      value={occurredDate}
                      onChange={(event) => setOccurredDate(event.target.value)}
                      className={inputClass}
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="incident-desc">상황 설명</Label>
                  <textarea
                    id="incident-desc"
                    rows={4}
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    placeholder="예: 계약 만기 2주 전인데 임대인이 보증금 반환을 미루고 연락을 피하고 있습니다."
                    className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={isSubmitting || description.trim().length < 10}
                  className="rounded-xl bg-danger-500 py-5 text-base font-extrabold hover:bg-danger-600"
                >
                  {isSubmitting ? "접수 중..." : "사고 접수하기"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </motion.div>

        {/* 내 접수 현황 */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4">
          {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
          {incidents === null ? (
            <Skeleton className="h-40 w-full rounded-2xl" />
          ) : incidents.length === 0 ? (
            <Card className="rounded-2xl border-line">
              <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
                <span className="flex size-12 items-center justify-center rounded-full bg-hug-mint text-hug-green">
                  <LifeBuoy size={22} />
                </span>
                <p className="text-sm font-semibold">접수된 사고가 없습니다.</p>
                <p className="text-xs text-muted-foreground">사고 없이 안전한 전세 생활을 응원합니다.</p>
              </CardContent>
            </Card>
          ) : (
            incidents.map((incident) => (
              <Card key={incident.incident_id} className="rounded-2xl border-line shadow-card">
                <CardHeader className="flex flex-row items-center justify-between pb-3">
                  <CardTitle className="text-sm font-extrabold">
                    {incident.incident_type_label}
                    {incident.deposit_amount ? (
                      <span className="ml-2 font-semibold text-muted-foreground tnum">
                        {formatDeposit(incident.deposit_amount)}
                      </span>
                    ) : null}
                  </CardTitle>
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-1 text-xs font-bold",
                      STATUS_TONE[incident.status],
                    )}
                  >
                    {INCIDENT_STATUS_LABEL[incident.status]}
                  </span>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <p className="text-sm text-muted-foreground">{incident.description}</p>
                  <TimelineList
                    items={incident.timeline.map((entry) => ({
                      time: entry.at.slice(0, 16).replace("T", " "),
                      title: INCIDENT_STATUS_LABEL[entry.status],
                      trailing: entry.note ? (
                        <span className="text-muted-foreground">{entry.note}</span>
                      ) : undefined,
                      level: STATUS_LEVEL[entry.status],
                    }))}
                  />
                  {incident.next_steps.length > 0 ? (
                    <div className="rounded-xl bg-hug-sky p-3.5">
                      <p className="mb-1 text-xs font-bold text-hug-navy">다음 단계 안내</p>
                      <ol className="list-decimal pl-4 text-xs text-hug-navy/80">
                        {incident.next_steps.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            ))
          )}
        </motion.div>
      </div>
    </motion.div>
  );
}
