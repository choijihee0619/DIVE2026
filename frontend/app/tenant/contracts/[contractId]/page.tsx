"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
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
import { ApiError } from "@/services/apiClient";
import type { Contract, ContractTimeline, ReturnPlan } from "@/types/contract";
import type { RiskAssessment } from "@/types/risk";
import type { EvidenceRequest } from "@/types/evidence";
import { CONTRACT_STATUS_LABEL, contractStatusBadgeVariant, formatDeposit } from "@/lib/contract-labels";
import {
  BLOCKCHAIN_STATUS_LABEL,
  EVIDENCE_TYPE_LABEL,
  HOUSING_TYPE_LABEL,
  LANDLORD_TYPE_LABEL,
  RISK_GRADE_LABEL,
  SEVERITY_LABEL,
  TIMELINE_EVENT_LABEL,
  VERIFICATION_STATUS_LABEL,
  riskGradeBadgeVariant,
  verificationStatusBadgeVariant,
} from "@/lib/domain-labels";

/** TEN-01 계약 상세: 계약 정보 + 위험진단 + 증빙 요청 + 타임라인 + 반환계획 실데이터. */
export default function ContractDetailPage() {
  const { contractId } = useParams<{ contractId: string }>();

  const [contract, setContract] = useState<Contract | null>(null);
  const [timeline, setTimeline] = useState<ContractTimeline | null>(null);
  const [returnPlan, setReturnPlan] = useState<ReturnPlan | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [evidenceRequests, setEvidenceRequests] = useState<EvidenceRequest[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDiagnosing, setIsDiagnosing] = useState(false);

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

  const runDiagnosis = () => {
    if (!contract || isDiagnosing) return;
    setIsDiagnosing(true);
    riskService
      .diagnose({
        property_id: contract.property_id,
        deposit: contract.deposit,
        contract_start_date: contract.contract_start_date,
        contract_end_date: contract.contract_end_date,
        landlord_type: contract.landlord_type,
        housing_type: contract.housing_type,
        landlord_id: contract.landlord_id,
        contract_id: contract.contract_id,
      })
      .then((result) => {
        setRisk(result);
        load();
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "위험진단에 실패했습니다."),
      )
      .finally(() => setIsDiagnosing(false));
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
      <Card>
        <CardContent className="py-10 text-center text-sm text-destructive">{errorMessage}</CardContent>
      </Card>
    );
  }

  if (!contract) {
    return (
      <div className="flex flex-col gap-3" aria-label="불러오는 중">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>계약 정보</CardTitle>
          <Badge variant={contractStatusBadgeVariant(contract.contract_status)}>
            {CONTRACT_STATUS_LABEL[contract.contract_status] ?? contract.contract_status}
          </Badge>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm lg:grid-cols-4">
          <div>
            <p className="text-muted-foreground">보증금</p>
            <p className="font-medium">{formatDeposit(contract.deposit)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">계약 기간</p>
            <p className="font-medium">
              {contract.contract_start_date} ~ {contract.contract_end_date}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">임대인 유형</p>
            <p className="font-medium">{LANDLORD_TYPE_LABEL[contract.landlord_type] ?? contract.landlord_type}</p>
          </div>
          <div>
            <p className="text-muted-foreground">주택 유형</p>
            <p className="font-medium">{HOUSING_TYPE_LABEL[contract.housing_type] ?? contract.housing_type}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>위험진단</CardTitle>
          <Button onClick={runDiagnosis} disabled={isDiagnosing} size="sm">
            {isDiagnosing ? "진단 중..." : risk ? "재진단" : "위험진단 실행"}
          </Button>
        </CardHeader>
        <CardContent>
          {risk ? (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-4">
                <Badge variant={riskGradeBadgeVariant(risk.risk_grade)}>
                  위험등급 {RISK_GRADE_LABEL[risk.risk_grade] ?? risk.risk_grade}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  위험점수 {risk.risk_score}점 · 신뢰도 {(risk.confidence * 100).toFixed(0)}% · 데이터 완성도{" "}
                  {(risk.data_completeness * 100).toFixed(0)}%
                </span>
              </div>
              {risk.risk_factors.length > 0 ? (
                <div>
                  <h3 className="mb-2 text-sm font-medium">위험 요인</h3>
                  <ul className="flex flex-col gap-1.5">
                    {risk.risk_factors.map((factor) => (
                      <li key={factor.code} className="flex items-start gap-2 text-sm">
                        <Badge
                          variant={factor.severity === "high" ? "destructive" : "outline"}
                          className="mt-0.5 shrink-0"
                        >
                          {SEVERITY_LABEL[factor.severity]}
                        </Badge>
                        <span>
                          <span className="font-medium">{factor.title}</span>
                          <span className="text-muted-foreground"> — {factor.description}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {risk.recommended_actions.length > 0 ? (
                <div>
                  <h3 className="mb-2 text-sm font-medium">권장 조치</h3>
                  <ol className="list-decimal pl-5 text-sm text-muted-foreground">
                    {risk.recommended_actions.map((action) => (
                      <li key={action}>{action}</li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              아직 위험진단을 실행하지 않았습니다. 진단을 실행하면 규칙 엔진이 위험 요인과 권장 조치를 제시합니다.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>증빙 요청</CardTitle>
          <Button size="sm" variant="outline" onClick={() => setRequestDialogOpen(true)}>
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
                  className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm"
                >
                  <Badge variant={verificationStatusBadgeVariant(request.verification_status)}>
                    {VERIFICATION_STATUS_LABEL[request.verification_status] ?? request.verification_status}
                  </Badge>
                  <span className="font-medium">
                    {EVIDENCE_TYPE_LABEL[request.evidence_type] ?? request.evidence_type}
                  </span>
                  <span className="text-muted-foreground">{request.reason}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>계약 타임라인</CardTitle>
        </CardHeader>
        <CardContent>
          {timeline === null ? (
            <Skeleton className="h-16 w-full" />
          ) : timeline.events.length === 0 ? (
            <p className="text-sm text-muted-foreground">기록된 이벤트가 없습니다.</p>
          ) : (
            <ol className="flex flex-col gap-3">
              {timeline.events.map((event) => (
                <li key={event.timeline_event_id} className="flex items-center gap-3 text-sm">
                  <span className="w-40 shrink-0 text-muted-foreground">{event.occurred_at.slice(0, 16).replace("T", " ")}</span>
                  <span className="font-medium">{TIMELINE_EVENT_LABEL[event.event_type] ?? event.event_type}</span>
                  {event.blockchain_tx_id ? (
                    <Link href={`/blockchain/${event.blockchain_tx_id}`} className="text-xs text-primary underline">
                      블록체인 기록 보기
                    </Link>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      {BLOCKCHAIN_STATUS_LABEL[event.blockchain_status] ?? event.blockchain_status}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>보증금 반환계획</CardTitle>
        </CardHeader>
        <CardContent>
          {returnPlan ? (
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex items-center gap-3">
                {returnPlan.early_warning ? <Badge variant="destructive">조기 경보</Badge> : null}
                {typeof returnPlan.d_day === "number" ? (
                  <span className="font-medium">반환 예정 D{returnPlan.d_day >= 0 ? `-${returnPlan.d_day}` : `+${-returnPlan.d_day}`}</span>
                ) : null}
              </div>
              <Separator />
              <p>
                <span className="text-muted-foreground">반환 예정일: </span>
                {returnPlan.planned_return_date ?? "-"}
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
            <p className="text-sm text-muted-foreground">임대인이 아직 반환계획을 제출하지 않았습니다.</p>
          )}
        </CardContent>
      </Card>

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
    </div>
  );
}
