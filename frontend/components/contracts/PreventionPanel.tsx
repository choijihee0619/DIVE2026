"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BellCheck, FileUp, Loader2, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { hugContractService } from "@/services/hugContractService";
import { evidenceService } from "@/services/evidenceService";
import { notificationService } from "@/services/notificationService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { ContractPreventionData, EvidenceBundle, PreventiveAction } from "@/types/hugContract";
import type { AppNotification } from "@/types/notification";
import { UserRole } from "@/types/enums";
import { PREVENTION_STATUS_LABEL, formatDate, toWorkText } from "@/lib/hug-labels";
import { cn } from "@/lib/utils";

const CHECKPOINT_ORDER = ["D90", "D60", "D30"] as const;
const CHECKPOINT_LABEL: Record<string, string> = { D90: "D-90", D60: "D-60", D30: "D-30" };

const BUNDLE_TONE: Record<string, string> = {
  Completed: "bg-hug-mint text-hug-green-deep",
  InReview: "bg-hug-sky text-hug-blue",
  Pending: "bg-neutral-200 text-neutral-600",
  Overdue: "bg-danger-100 text-danger-600",
};

/** 예방조치(action) 상태 라벨 — 케이스 상태(PREVENTION_STATUS_LABEL)와 축이 다르다. */
const ACTION_STATUS_LABEL: Record<string, string> = {
  Requested: "요청됨",
  InProgress: "이행 중",
  Submitted: "완료 제출됨",
  Verifying: "검증 중",
  Completed: "이행 완료",
  Rejected: "반려",
  Overdue: "기한 초과",
  Cancelled: "취소",
};

const ITEM_BADGE: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  Pending: { label: "제출 필요", variant: "destructive" },
  Submitted: { label: "제출됨 · 확인 중", variant: "secondary" },
  Reviewing: { label: "검토 중", variant: "secondary" },
  Verified: { label: "확인 완료", variant: "default" },
  Rejected: { label: "반려 · 재제출", variant: "destructive" },
};

interface PreventionPanelProps {
  contractId: string;
}

/** 예방 탭(§20.5 P3) — D-90/60/30 증빙 bundle 현황·임대인 제출, 신용보강 등록, 예방 알림 확인. */
export function PreventionPanel({ contractId }: PreventionPanelProps) {
  const role = useSessionStore((state) => state.user?.role);
  const [data, setData] = useState<ContractPreventionData | null>(null);
  const [alerts, setAlerts] = useState<AppNotification[] | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadingRequestId, setUploadingRequestId] = useState<string | null>(null);
  const [updatingActionId, setUpdatingActionId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pendingRequestId = useRef<string | null>(null);

  const isLandlord = role === UserRole.LANDLORD;

  const load = useCallback(() => {
    hugContractService
      .prevention(contractId)
      .then((result) => {
        setData(result);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(
          error instanceof ApiError ? error.message : "예방 현황을 불러오지 못했습니다.",
        ),
      );
    notificationService
      .list({ size: 50 })
      .then((result) =>
        setAlerts(
          result.items.filter(
            (item) => item.category === "prevention_alert" && item.contract_id === contractId,
          ),
        ),
      )
      .catch(() => setAlerts([]));
  }, [contractId]);

  useEffect(() => {
    load();
  }, [load]);

  const pickFile = (requestId: string) => {
    pendingRequestId.current = requestId;
    fileInputRef.current?.click();
  };

  const onFileChosen = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    const requestId = pendingRequestId.current;
    event.target.value = "";
    if (!file || !requestId) return;
    setUploadingRequestId(requestId);
    try {
      await evidenceService.submitEvidence(requestId, file);
      toast.success("증빙을 제출했습니다. 임차인·HUG가 동시에 확인합니다.");
      load();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "증빙 제출에 실패했습니다.");
    } finally {
      setUploadingRequestId(null);
    }
  };

  const updateCreditAction = (action: PreventiveAction, status: "InProgress" | "Submitted") => {
    const actionId = action.action_id ?? action._id;
    if (!actionId || updatingActionId) return;
    setUpdatingActionId(actionId);
    hugContractService
      .updateAction(actionId, {
        status,
        note: status === "Submitted" ? "임대인 신용보강 완료 제출" : "임대인 이행 착수",
      })
      .then(() => {
        toast.success(
          status === "Submitted"
            ? "신용보강 완료를 제출했습니다. HUG 검증 후 확정됩니다."
            : "이행 착수를 등록했습니다.",
        );
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "등록에 실패했습니다."),
      )
      .finally(() => setUpdatingActionId(null));
  };

  const acknowledgeAlert = (notificationId: string) => {
    notificationService
      .acknowledge(notificationId)
      .then(() => {
        toast.success("확인 처리했습니다. 확인 시각이 함께 기록됩니다.");
        load();
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "확인 처리에 실패했습니다."),
      );
  };

  if (errorMessage) {
    return <p className="py-4 text-sm text-destructive">{errorMessage}</p>;
  }
  if (!data) {
    return <Skeleton className="h-56 w-full rounded-2xl" />;
  }

  const preventionCase = data.case ?? data.prevention_case ?? null;
  const bundles: EvidenceBundle[] = [...(data.evidence_bundles ?? [])].sort(
    (a, b) => CHECKPOINT_ORDER.indexOf(a.checkpoint) - CHECKPOINT_ORDER.indexOf(b.checkpoint),
  );
  const creditActions = (data.actions ?? []).filter(
    (action) => action.action_type === "CREDIT_ENHANCEMENT_REQUEST",
  );

  return (
    <div className="flex flex-col gap-5">
      {/* 예방 케이스 요약 */}
      <Card className="rounded-2xl border-line shadow-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-1.5 text-base font-extrabold">
            <ShieldCheck size={16} className="text-hug-blue" />
            사전예방 현황
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm">
          {preventionCase ? (
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-bold",
                  BUNDLE_TONE[preventionCase.status] ?? "bg-hug-sky text-hug-blue",
                )}
              >
                {PREVENTION_STATUS_LABEL[preventionCase.status] ?? preventionCase.status}
              </span>
              <span className="text-muted-foreground">
                다음 조치: {toWorkText(preventionCase.next_action) || "정상 모니터링"}
              </span>
              {preventionCase.due_at ? (
                <span className="text-muted-foreground">기한 {formatDate(preventionCase.due_at)}</span>
              ) : null}
            </div>
          ) : (
            <p className="text-muted-foreground">현재 별도 예방 조치 없이 정상 모니터링 중입니다.</p>
          )}
        </CardContent>
      </Card>

      {/* D-체크포인트 증빙 bundle */}
      {bundles.length > 0 ? (
        bundles.map((bundle) => (
          <Card key={bundle.checkpoint} className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2 text-base font-extrabold">
                {CHECKPOINT_LABEL[bundle.checkpoint] ?? bundle.checkpoint} 필수 증빙
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-bold",
                    BUNDLE_TONE[bundle.status] ?? "bg-neutral-200 text-neutral-600",
                  )}
                >
                  {bundle.verified_count}/{bundle.required_count} 확인 완료
                </span>
                <span className="text-xs font-semibold text-muted-foreground">
                  기한 {formatDate(bundle.due_at)}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-col gap-2">
                {bundle.items.map((item) => {
                  const badge = ITEM_BADGE[item.verification_status] ?? {
                    label: item.verification_status,
                    variant: "outline" as const,
                  };
                  const submittable =
                    isLandlord && ["Pending", "Rejected"].includes(item.verification_status);
                  return (
                    <li
                      key={item.item_key}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line p-3 text-sm"
                    >
                      <Badge variant={badge.variant}>{badge.label}</Badge>
                      <span className="font-semibold">{item.label}</span>
                      {item.is_overdue ? (
                        <span className="text-xs font-bold text-danger-600">기한 초과</span>
                      ) : null}
                      <span className="min-w-0 flex-1" />
                      {submittable ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={uploadingRequestId === item.evidence_request_id}
                          onClick={() => pickFile(item.evidence_request_id)}
                        >
                          {uploadingRequestId === item.evidence_request_id ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <FileUp size={14} />
                          )}
                          제출
                        </Button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        ))
      ) : (
        <p className="rounded-xl border border-line bg-neutral-100 px-4 py-3 text-sm text-muted-foreground">
          아직 생성된 D-체크포인트 증빙 요청이 없습니다. 만기 90일 이내에 자동 생성됩니다.
        </p>
      )}

      {/* 신용보강 조치 — 임대인 완료 등록 */}
      {creditActions.length > 0 ? (
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader>
            <CardTitle className="text-base font-extrabold">신용보강 조치</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {creditActions.map((action) => {
                const actionId = action.action_id ?? action._id ?? "";
                const canStart = isLandlord && ["Requested", "Overdue", "Rejected"].includes(action.status);
                const canSubmit =
                  isLandlord &&
                  ["Requested", "InProgress", "Overdue", "Rejected"].includes(action.status);
                return (
                  <li
                    key={actionId}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line p-3 text-sm"
                  >
                    <span className="font-semibold">근저당 감액 등 신용보강</span>
                    <span className="text-xs text-muted-foreground">
                      상태 {ACTION_STATUS_LABEL[action.status] ?? action.status}
                      {action.due_at ? ` · 기한 ${formatDate(action.due_at)}` : ""}
                    </span>
                    <span className="min-w-0 flex-1" />
                    {canStart ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={updatingActionId === actionId}
                        onClick={() => updateCreditAction(action, "InProgress")}
                      >
                        이행 착수
                      </Button>
                    ) : null}
                    {canSubmit ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={updatingActionId === actionId}
                        onClick={() => updateCreditAction(action, "Submitted")}
                      >
                        완료 제출
                      </Button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {/* 예방 알림 확인 */}
      {alerts && alerts.length > 0 ? (
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader>
            <CardTitle className="text-base font-extrabold">이 계약의 예방 알림</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {alerts.map((alert) => (
                <li
                  key={alert.notification_id}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-line p-3 text-sm"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold">{alert.title}</span>
                    <span className="text-xs text-muted-foreground">{alert.body}</span>
                  </span>
                  {alert.acknowledged_at ? (
                    <span className="flex items-center gap-1 text-xs font-bold text-hug-green-deep">
                      <BellCheck size={14} />
                      확인 {formatDate(alert.acknowledged_at)}
                    </span>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => acknowledgeAlert(alert.notification_id)}>
                      확인 처리
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
      <input ref={fileInputRef} type="file" className="hidden" onChange={onFileChosen} />
    </div>
  );
}
