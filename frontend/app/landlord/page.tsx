"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { evidenceService } from "@/services/evidenceService";
import { contractService } from "@/services/contractService";
import { ApiError } from "@/services/apiClient";
import type { EvidenceRequest } from "@/types/evidence";
import type { Contract } from "@/types/contract";
import {
  EVIDENCE_TYPE_LABEL,
  VERIFICATION_STATUS_LABEL,
  verificationStatusBadgeVariant,
} from "@/lib/domain-labels";

const selectClass =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** LAND-00 임대인 홈: 증빙 요청 목록·파일 제출(POST /evidence) + 반환계획 제출(POST /return-plans). */
export default function LandlordHomePage() {
  const [requests, setRequests] = useState<EvidenceRequest[] | null>(null);
  const [contracts, setContracts] = useState<Contract[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [uploadTarget, setUploadTarget] = useState<EvidenceRequest | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [planContractId, setPlanContractId] = useState("");
  const [planDate, setPlanDate] = useState("");
  const [planMethod, setPlanMethod] = useState("계좌이체");
  const [isSubmittingPlan, setIsSubmittingPlan] = useState(false);

  const load = useCallback(() => {
    evidenceService
      .listRequests()
      .then((data) => setRequests(data.items))
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "증빙 요청 목록을 불러오지 못했습니다."),
      );
    contractService
      .list({ size: 100 })
      .then((data) => {
        setContracts(data.items);
        if (data.items.length > 0) setPlanContractId(data.items[0].contract_id);
      })
      .catch(() => setContracts([]));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submitEvidence = () => {
    if (!uploadTarget || !uploadFile || isUploading) return;
    setIsUploading(true);
    setErrorMessage(null);
    evidenceService
      .submitEvidence(uploadTarget.evidence_request_id, uploadFile)
      .then(() => {
        setNotice(`'${EVIDENCE_TYPE_LABEL[uploadTarget.evidence_type] ?? uploadTarget.evidence_type}' 증빙을 제출했습니다.`);
        setUploadTarget(null);
        setUploadFile(null);
        load();
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "증빙 제출에 실패했습니다."),
      )
      .finally(() => setIsUploading(false));
  };

  const submitReturnPlan = (event: React.FormEvent) => {
    event.preventDefault();
    if (!planContractId || !planDate || isSubmittingPlan) return;
    setIsSubmittingPlan(true);
    setErrorMessage(null);
    contractService
      .submitReturnPlan({
        contract_id: planContractId,
        planned_return_date: planDate,
        return_method: planMethod,
      })
      .then((plan) => {
        setNotice(
          `반환계획을 제출했습니다 (예정일 ${plan.planned_return_date}${typeof plan.d_day === "number" ? `, D-${plan.d_day}` : ""}).`,
        );
        setPlanDate("");
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "반환계획 제출에 실패했습니다."),
      )
      .finally(() => setIsSubmittingPlan(false));
  };

  return (
    <div className="flex flex-col gap-6">
      {notice ? <p className="text-sm text-primary">{notice}</p> : null}
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>증빙 요청 목록</CardTitle>
        </CardHeader>
        <CardContent>
          {requests === null ? (
            <Skeleton className="h-24 w-full" />
          ) : requests.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">받은 증빙 요청이 없습니다.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>증빙 유형</TableHead>
                  <TableHead>사유</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>마감일</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.map((request) => (
                  <TableRow key={request.evidence_request_id}>
                    <TableCell className="font-medium">
                      {EVIDENCE_TYPE_LABEL[request.evidence_type] ?? request.evidence_type}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{request.reason}</TableCell>
                    <TableCell>
                      <Badge variant={verificationStatusBadgeVariant(request.verification_status)}>
                        {VERIFICATION_STATUS_LABEL[request.verification_status] ?? request.verification_status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{request.due_date ?? "-"}</TableCell>
                    <TableCell>
                      {["Pending", "Rejected"].includes(request.verification_status) ? (
                        <Button size="sm" variant="outline" onClick={() => setUploadTarget(request)}>
                          파일 제출
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>보증금 반환계획 제출</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4 md:max-w-xl" onSubmit={submitReturnPlan}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="plan-contract">대상 계약</Label>
              <select
                id="plan-contract"
                value={planContractId}
                onChange={(event) => setPlanContractId(event.target.value)}
                className={selectClass}
                disabled={contracts === null || contracts.length === 0}
              >
                {(contracts ?? []).map((contract) => (
                  <option key={contract.contract_id} value={contract.contract_id}>
                    {contract.contract_id} ({contract.contract_start_date} ~ {contract.contract_end_date})
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="plan-date">반환 예정일</Label>
                <Input id="plan-date" type="date" value={planDate} onChange={(e) => setPlanDate(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="plan-method">반환 방법</Label>
                <select
                  id="plan-method"
                  value={planMethod}
                  onChange={(event) => setPlanMethod(event.target.value)}
                  className={selectClass}
                >
                  <option value="계좌이체">계좌이체</option>
                  <option value="현금">현금</option>
                  <option value="보증보험 이행">보증보험 이행</option>
                  <option value="기타">기타</option>
                </select>
              </div>
            </div>
            <div>
              <Button type="submit" disabled={!planContractId || !planDate || isSubmittingPlan}>
                {isSubmittingPlan ? "제출 중..." : "반환계획 제출"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Dialog open={uploadTarget !== null} onOpenChange={(open) => !open && setUploadTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              증빙 파일 제출
              {uploadTarget ? ` — ${EVIDENCE_TYPE_LABEL[uploadTarget.evidence_type] ?? uploadTarget.evidence_type}` : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="evidence-file">파일 (PDF, PNG, JPEG · 최대 20MB)</Label>
            <Input
              id="evidence-file"
              type="file"
              accept="application/pdf,image/png,image/jpeg"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadTarget(null)}>
              취소
            </Button>
            <Button onClick={submitEvidence} disabled={!uploadFile || isUploading}>
              {isUploading ? "제출 중..." : "제출"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
