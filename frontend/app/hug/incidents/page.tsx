"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Siren } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { incidentService } from "@/services/incidentService";
import { ApiError } from "@/services/apiClient";
import {
  INCIDENT_STATUS_FLOW,
  INCIDENT_STATUS_LABEL,
  type Incident,
  type IncidentStatus,
} from "@/types/incident";
import { formatDeposit } from "@/lib/contract-labels";
import { TimelineList } from "@/components/viz/TimelineList";
import type { SignalLevel } from "@/components/viz/RiskSignals";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<IncidentStatus, string> = {
  Received: "bg-hug-sky text-hug-blue",
  Reviewing: "bg-warning-100 text-warning-700",
  TransferredToRecovery: "bg-hug-mint text-hug-green-deep",
  Closed: "bg-neutral-200 text-neutral-600",
};

const STATUS_LEVEL: Record<IncidentStatus, SignalLevel> = {
  Received: "info",
  Reviewing: "warn",
  TransferredToRecovery: "ok",
  Closed: "ok",
};

function nextStatusOf(status: IncidentStatus): IncidentStatus | null {
  const index = INCIDENT_STATUS_FLOW.indexOf(status);
  return index >= 0 && index < INCIDENT_STATUS_FLOW.length - 1 ? INCIDENT_STATUS_FLOW[index + 1] : null;
}

/** HUG-02 사고 접수 큐: GET /incidents 전체 조회 + PATCH 상태 전이(접수→검토→회수 이관→종결). */
export default function HugIncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const load = useCallback(() => {
    incidentService
      .list()
      .then((data) => {
        setIncidents(data.items);
        setSelectedId((prev) => prev ?? data.items[0]?.incident_id ?? null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "사고 큐를 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => (incidents ?? []).find((incident) => incident.incident_id === selectedId) ?? null,
    [incidents, selectedId],
  );

  const advance = (incident: Incident) => {
    const next = nextStatusOf(incident.status);
    if (!next || isUpdating) return;
    setIsUpdating(true);
    incidentService
      .updateStatus(incident.incident_id, next, `HUG 처리 — ${INCIDENT_STATUS_LABEL[next]} 전환`)
      .then((updated) => {
        setIncidents((prev) =>
          (prev ?? []).map((item) => (item.incident_id === updated.incident_id ? updated : item)),
        );
        toast.success(`${INCIDENT_STATUS_LABEL[next]} 상태로 전환했습니다.`);
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "상태 전환에 실패했습니다."),
      )
      .finally(() => setIsUpdating(false));
  };

  const countByStatus = useMemo(() => {
    const counts = new Map<IncidentStatus, number>();
    for (const incident of incidents ?? []) {
      counts.set(incident.status, (counts.get(incident.status) ?? 0) + 1);
    }
    return counts;
  }, [incidents]);

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
            <Siren size={22} className="text-danger-500" />
            사고 접수 큐
          </h1>
          <p className="mt-1.5 text-muted-foreground">
            임차인 사고 접수를 검토하고 회수 절차로 이관합니다 — 접수 → 검토 → 회수 이관 → 종결.
          </p>
        </div>
        <div className="ml-auto flex gap-1.5">
          {INCIDENT_STATUS_FLOW.map((status) => (
            <span key={status} className={cn("rounded-full px-2.5 py-1 text-xs font-bold tnum", STATUS_TONE[status])}>
              {INCIDENT_STATUS_LABEL[status]} {countByStatus.get(status) ?? 0}
            </span>
          ))}
        </div>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-5">
        {/* 큐 목록 */}
        <motion.div variants={fadeUp} className="xl:col-span-3">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                접수 목록 {incidents ? `· ${incidents.length}건` : ""}
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {incidents === null ? (
                <Skeleton className="h-48 w-full" />
              ) : incidents.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">접수된 사고가 없습니다.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">유형</th>
                      <th className="px-2">보증금</th>
                      <th className="px-2">접수일</th>
                      <th className="px-2">상태</th>
                      <th className="px-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {incidents.map((incident, index) => {
                      const next = nextStatusOf(incident.status);
                      return (
                        <motion.tr
                          key={incident.incident_id}
                          initial={{ opacity: 0, y: 8 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: index * 0.05, duration: 0.3 }}
                          onClick={() => setSelectedId(incident.incident_id)}
                          className={cn(
                            "cursor-pointer border-b border-line/70 transition-colors last:border-b-0",
                            selectedId === incident.incident_id ? "bg-hug-sky/60" : "hover:bg-neutral-100",
                          )}
                        >
                          <td className="max-w-44 truncate py-2.5 pr-2 font-semibold" title={incident.description}>
                            {incident.incident_type_label}
                          </td>
                          <td className="px-2 tnum">
                            {incident.deposit_amount ? formatDeposit(incident.deposit_amount) : "—"}
                          </td>
                          <td className="px-2 text-muted-foreground tnum">{incident.created_at.slice(0, 10)}</td>
                          <td className="px-2">
                            <span className={cn("rounded-full px-2 py-0.5 text-xs font-bold", STATUS_TONE[incident.status])}>
                              {INCIDENT_STATUS_LABEL[incident.status]}
                            </span>
                          </td>
                          <td className="px-2 text-right">
                            {next ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 rounded-full px-2.5 text-xs"
                                disabled={isUpdating}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  advance(incident);
                                }}
                              >
                                {INCIDENT_STATUS_LABEL[next]}
                                <ArrowRight size={12} />
                              </Button>
                            ) : null}
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

        {/* 선택 건 상세 */}
        <motion.div variants={fadeUp} className="xl:col-span-2">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">선택 건 · 처리 타임라인</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {selected ? (
                <>
                  <div className="rounded-xl bg-neutral-100 p-3.5 text-sm">
                    <p className="font-bold">{selected.incident_type_label}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{selected.description}</p>
                    {selected.contract_id ? (
                      <p className="mt-1.5 font-mono text-xs text-muted-foreground">계약 {selected.contract_id}</p>
                    ) : null}
                  </div>
                  <TimelineList
                    items={selected.timeline.map((entry) => ({
                      time: entry.at.slice(0, 16).replace("T", " "),
                      title: INCIDENT_STATUS_LABEL[entry.status],
                      trailing: entry.note ? <span className="text-muted-foreground">{entry.note}</span> : undefined,
                      level: STATUS_LEVEL[entry.status],
                    }))}
                  />
                  {selected.next_steps.length > 0 ? (
                    <div className="rounded-xl bg-hug-sky p-3.5">
                      <p className="mb-1 text-xs font-bold text-hug-navy">피해자 안내 (안심전세포털 절차)</p>
                      <ol className="list-decimal pl-4 text-xs text-hug-navy/80">
                        {selected.next_steps.map((step) => (
                          <li key={step}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </>
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">좌측에서 사고 건을 선택하세요.</p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}
