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
import { ApiError } from "@/services/apiClient";
import type { EvidenceRequest, Verification } from "@/types/evidence";
import {
  EVIDENCE_TYPE_LABEL,
  VERIFICATION_STATUS_LABEL,
  verificationStatusBadgeVariant,
} from "@/lib/domain-labels";

const selectClass =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** ADV-00 검증 큐: 증빙 요청 목록 + 검증 승인/반려(POST /verifications/{id}/decision). */
export default function AdvisorQueuePage() {
  const [requests, setRequests] = useState<EvidenceRequest[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [reviewTarget, setReviewTarget] = useState<EvidenceRequest | null>(null);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [decision, setDecision] = useState<"approve" | "reject" | "hold">("approve");
  const [comment, setComment] = useState("");
  const [isDeciding, setIsDeciding] = useState(false);

  const load = useCallback(() => {
    evidenceService
      .listRequests()
      .then((data) => setRequests(data.items))
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "증빙 요청 목록을 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openReview = (request: EvidenceRequest) => {
    setReviewTarget(request);
    setVerification(null);
    setDecision("approve");
    setComment("");
    if (request.latest_evidence_id) {
      evidenceService.getVerification(request.latest_evidence_id).then(setVerification).catch(() => setVerification(null));
    }
  };

  const submitDecision = () => {
    if (!reviewTarget?.latest_evidence_id || isDeciding) return;
    setIsDeciding(true);
    setErrorMessage(null);
    evidenceService
      .decide(reviewTarget.latest_evidence_id, { decision, reviewer_comment: comment.trim() || undefined })
      .then((result) => {
        setNotice(
          `검증 결과를 기록했습니다: ${VERIFICATION_STATUS_LABEL[result.verification_status] ?? result.verification_status}` +
            (result.blockchain_tx_id ? " (블록체인 기록됨)" : ""),
        );
        setReviewTarget(null);
        load();
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "검증 처리에 실패했습니다."),
      )
      .finally(() => setIsDeciding(false));
  };

  return (
    <div className="flex flex-col gap-6">
      {notice ? <p className="text-sm text-primary">{notice}</p> : null}
      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>증빙 검증 큐</CardTitle>
        </CardHeader>
        <CardContent>
          {requests === null ? (
            <Skeleton className="h-24 w-full" />
          ) : requests.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">검증할 증빙 요청이 없습니다.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>증빙 유형</TableHead>
                  <TableHead>사유</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead>최근 변경</TableHead>
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
                    <TableCell className="text-sm text-muted-foreground">{request.updated_at.slice(0, 10)}</TableCell>
                    <TableCell>
                      {request.latest_evidence_id &&
                      ["Submitted", "Reviewing"].includes(request.verification_status) ? (
                        <Button size="sm" onClick={() => openReview(request)}>
                          검토
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

      <Dialog open={reviewTarget !== null} onOpenChange={(open) => !open && setReviewTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              증빙 검증
              {reviewTarget ? ` — ${EVIDENCE_TYPE_LABEL[reviewTarget.evidence_type] ?? reviewTarget.evidence_type}` : ""}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            {verification ? (
              <p className="text-sm text-muted-foreground">
                현재 상태:{" "}
                {VERIFICATION_STATUS_LABEL[verification.verification_status] ?? verification.verification_status}
                {verification.reviewer_comment ? ` · 기존 코멘트: ${verification.reviewer_comment}` : ""}
              </p>
            ) : null}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="decision">결정</Label>
              <select
                id="decision"
                value={decision}
                onChange={(event) => setDecision(event.target.value as "approve" | "reject" | "hold")}
                className={selectClass}
              >
                <option value="approve">승인</option>
                <option value="reject">반려</option>
                <option value="hold">보류(검토 중)</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="reviewer-comment">검토 코멘트</Label>
              <Input
                id="reviewer-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                placeholder="예: 등기부등본 상 근저당 말소 확인"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewTarget(null)}>
              취소
            </Button>
            <Button
              variant={decision === "reject" ? "destructive" : "default"}
              onClick={submitDecision}
              disabled={isDeciding}
            >
              {isDeciding ? "처리 중..." : "결정 기록"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
