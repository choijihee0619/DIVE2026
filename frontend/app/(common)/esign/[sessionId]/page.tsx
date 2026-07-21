"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { CircleCheck, CircleX, FileSignature, Link2, Plus, Sparkles, UserRound } from "lucide-react";
import { toast } from "sonner";
import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { UserRole } from "@/types/enums";
import { esignService } from "@/services/esignService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { EsignSession, EsignVerifyResult, PartyRole, SpecialTerm } from "@/types/esign";
import { formatDeposit } from "@/lib/contract-labels";
import { HOUSING_TYPE_LABEL, LANDLORD_TYPE_LABEL } from "@/lib/domain-labels";
import { ContractStepper } from "@/components/viz/ContractStepper";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<PartyRole, string> = { tenant: "임차인", landlord: "임대인" };

const TERM_SOURCE_LABEL: Record<SpecialTerm["source"], string> = {
  ai_recommend: "AI 추천",
  tenant: "임차인 제안",
  landlord: "임대인 제안",
};

const STEP_INDEX: Record<string, number> = { TermsAgreement: 1, Signing: 2, Anchored: 4, Cancelled: 0 };

/** COMMON-02 전자계약 공동세션(시안 2-4): 3초 폴링 동기화, 특약 합의→서명→자동 앵커→위변조 검증. */
export default function EsignSessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const user = useSessionStore((state) => state.user);
  const myRole = (user?.role === "landlord" ? "landlord" : "tenant") as PartyRole;

  const [session, setSession] = useState<EsignSession | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [termText, setTermText] = useState("");
  const [busy, setBusy] = useState(false);
  const [verifyResult, setVerifyResult] = useState<EsignVerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);
  const sessionRef = useRef<EsignSession | null>(null);
  sessionRef.current = session;

  const load = useCallback(() => {
    esignService
      .get(sessionId)
      .then((data) => {
        setSession(data);
        setErrorMessage(null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "세션 정보를 불러오지 못했습니다."),
      );
  }, [sessionId]);

  /** 시안의 "실시간 동기화" — 앵커 완료 전까지 3초 폴링. */
  useEffect(() => {
    load();
    const timer = setInterval(() => {
      if (sessionRef.current?.status === "Anchored") return;
      load();
    }, 3000);
    return () => clearInterval(timer);
  }, [load]);

  const runAction = (action: () => Promise<EsignSession>, successMessage?: string) => {
    if (busy) return;
    setBusy(true);
    action()
      .then((data) => {
        setSession(data);
        if (successMessage) toast.success(successMessage);
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "요청에 실패했습니다."),
      )
      .finally(() => setBusy(false));
  };

  const runVerify = (tampered: boolean) => {
    if (!session || verifying) return;
    setVerifying(true);
    esignService
      .verify(
        session.contract_id,
        tampered ? { deposit: session.contract_summary.deposit + 100_000_000 } : undefined,
      )
      .then(setVerifyResult)
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "검증에 실패했습니다."),
      )
      .finally(() => setVerifying(false));
  };

  const me = session?.participants.find((p) => p.role === myRole);
  const pendingTerms = useMemo(
    () => (session?.special_terms ?? []).filter((t) => t.status === "proposed").length,
    [session],
  );
  const canSign =
    session !== null &&
    session.status !== "Anchored" &&
    session.status !== "Cancelled" &&
    pendingTerms === 0 &&
    me !== undefined &&
    !me.signed;

  return (
    <RoleGuard allowedRoles={[UserRole.TENANT, UserRole.LANDLORD]}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-5xl flex-1 px-6 pb-12 pt-2">
          {errorMessage && !session ? (
            <Card className="rounded-2xl border-line">
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <p className="text-sm text-destructive">{errorMessage}</p>
                <Button variant="outline" onClick={load}>
                  다시 시도
                </Button>
              </CardContent>
            </Card>
          ) : session === null ? (
            <div className="flex flex-col gap-3" aria-label="세션 불러오는 중">
              <Skeleton className="h-24 w-full rounded-2xl" />
              <Skeleton className="h-56 w-full rounded-2xl" />
            </div>
          ) : (
            <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
              <motion.div variants={fadeUp}>
                <p className="text-sm font-semibold text-muted-foreground">전자계약 › 공동세션</p>
                <div className="mt-1 flex flex-wrap items-center gap-2.5">
                  <h1 className="text-2xl font-extrabold tracking-tight">
                    세션 <span className="font-mono">{session.session_code}</span>
                  </h1>
                  {session.participants.map((participant) => (
                    <span
                      key={participant.role}
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold",
                        participant.joined
                          ? "bg-hug-mint text-hug-green-deep"
                          : "bg-neutral-200 text-neutral-600",
                      )}
                    >
                      <span
                        className={cn(
                          "size-2 rounded-full",
                          participant.joined ? "animate-pulse-soft bg-hug-green" : "bg-neutral-400",
                        )}
                      />
                      {ROLE_LABEL[participant.role]} {participant.display_name ?? ""}
                      {participant.joined ? " 접속중" : " 대기중"}
                      {participant.signed ? " · 서명 완료" : ""}
                    </span>
                  ))}
                  <span className="ml-auto text-xs text-muted-foreground">3초 간격 실시간 동기화</span>
                </div>
                {myRole === "tenant" && !session.participants.find((p) => p.role === "landlord")?.joined ? (
                  <p className="mt-2 rounded-xl bg-hug-sky px-4 py-2.5 text-sm text-hug-navy">
                    임대인에게 세션 코드 <b className="font-mono">{session.session_code}</b>를 전달하세요 —
                    임대인 홈 &ldquo;전자계약 세션 입장&rdquo;에서 참여할 수 있습니다.
                  </p>
                ) : null}
              </motion.div>

              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardContent className="pt-6">
                    <ContractStepper
                      steps={[
                        { label: "1 조건 확인" },
                        { label: "2 특약 합의", caption: pendingTerms > 0 ? `대기 ${pendingTerms}건` : undefined },
                        { label: "3 서명" },
                        { label: "4 블록체인 기록" },
                      ]}
                      current={STEP_INDEX[session.status] ?? 0}
                      className="mx-auto max-w-2xl"
                    />
                  </CardContent>
                </Card>
              </motion.div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                <motion.div variants={fadeUp}>
                  <Card className="h-full rounded-2xl border-line shadow-card">
                    <CardHeader>
                      <CardTitle className="text-base font-extrabold">계약 요약</CardTitle>
                    </CardHeader>
                    <CardContent className="flex h-[calc(100%-64px)] flex-col gap-4">
                      <table className="w-full text-sm">
                        <tbody>
                          {[
                            ["계약", session.contract_id],
                            ["매물", session.contract_summary.property_id],
                            ["보증금", formatDeposit(session.contract_summary.deposit)],
                            [
                              "기간",
                              `${session.contract_summary.contract_start_date} ~ ${session.contract_summary.contract_end_date}`,
                            ],
                            [
                              "임대인/주택 유형",
                              `${LANDLORD_TYPE_LABEL[session.contract_summary.landlord_type] ?? session.contract_summary.landlord_type} · ${HOUSING_TYPE_LABEL[session.contract_summary.housing_type] ?? session.contract_summary.housing_type}`,
                            ],
                            [
                              "합의 특약",
                              `${session.special_terms.filter((t) => t.status === "agreed").length}건 (AI 추천 ${session.special_terms.filter((t) => t.source === "ai_recommend").length}건 포함)`,
                            ],
                          ].map(([label, value]) => (
                            <tr key={label} className="border-b border-line/60 last:border-b-0">
                              <td className="w-32 py-2 text-muted-foreground">{label}</td>
                              <td className="py-2 font-semibold tnum">{value}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <div className="mt-auto">
                        {me?.signed ? (
                          <p className="flex items-center gap-2 rounded-xl bg-hug-mint px-4 py-3 text-sm font-bold text-hug-green-deep">
                            <CircleCheck size={16} />
                            서명을 완료했습니다.
                            {session.status !== "Anchored" ? " 상대방 서명을 기다리는 중…" : ""}
                          </p>
                        ) : (
                          <Button
                            className="w-full rounded-xl bg-hug-green py-5 text-base font-extrabold hover:bg-hug-green-deep"
                            disabled={!canSign || busy}
                            onClick={() =>
                              runAction(() => esignService.sign(session.session_id), "서명이 완료되었습니다.")
                            }
                          >
                            <FileSignature size={17} />
                            {pendingTerms > 0 ? `특약 ${pendingTerms}건 합의 후 서명 가능` : "서명하기"}
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>

                <motion.div variants={fadeUp}>
                  <Card className="h-full rounded-2xl border-line shadow-card">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-base font-extrabold">
                        특약 합의
                        <span className="flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-bold text-violet-700">
                          <Sparkles size={12} />
                          위험진단 연동 AI 추천
                        </span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2.5">
                      {session.special_terms.length === 0 ? (
                        <p className="py-4 text-sm text-muted-foreground">제안된 특약이 없습니다.</p>
                      ) : (
                        session.special_terms.map((term) => {
                          const iAgreed = term.agreed_by.includes(myRole);
                          const canAgree = term.status === "proposed" && !iAgreed;
                          const canWithdraw = term.status === "proposed" && term.source === myRole;
                          return (
                            <div
                              key={term.term_id}
                              className={cn(
                                "rounded-xl border p-3",
                                term.status === "agreed"
                                  ? "border-success-200 bg-hug-mint/40"
                                  : term.status === "withdrawn"
                                    ? "border-line opacity-50"
                                    : "border-line",
                              )}
                            >
                              <div className="flex items-start gap-2">
                                <span
                                  className={cn(
                                    "mt-0.5 shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold",
                                    term.source === "ai_recommend"
                                      ? "bg-violet-100 text-violet-700"
                                      : "bg-hug-sky text-hug-blue",
                                  )}
                                >
                                  {TERM_SOURCE_LABEL[term.source]}
                                </span>
                                <p className={cn("min-w-0 flex-1 text-sm font-semibold", term.status === "withdrawn" && "line-through")}>
                                  {term.text}
                                </p>
                                <span
                                  className={cn(
                                    "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold",
                                    term.status === "agreed"
                                      ? "bg-hug-mint text-hug-green-deep"
                                      : term.status === "withdrawn"
                                        ? "bg-neutral-200 text-neutral-600"
                                        : "bg-warning-100 text-warning-700",
                                  )}
                                >
                                  {term.status === "agreed" ? "합의됨" : term.status === "withdrawn" ? "철회" : "대기"}
                                </span>
                              </div>
                              {term.rationale ? (
                                <p className="mt-1 pl-1 text-xs text-muted-foreground">{term.rationale}</p>
                              ) : null}
                              {term.status === "proposed" ? (
                                <div className="mt-2 flex items-center gap-2 pl-1 text-xs">
                                  <span className="text-muted-foreground">
                                    합의: {term.agreed_by.length === 0 ? "없음" : term.agreed_by.map((r) => ROLE_LABEL[r]).join("·")}
                                    /양측
                                  </span>
                                  {canAgree ? (
                                    <Button
                                      size="sm"
                                      className="ml-auto h-7 rounded-full px-3 text-xs"
                                      disabled={busy}
                                      onClick={() =>
                                        runAction(
                                          () => esignService.actOnTerm(session.session_id, term.term_id, "agree"),
                                          "특약에 합의했습니다.",
                                        )
                                      }
                                    >
                                      합의하기
                                    </Button>
                                  ) : null}
                                  {canWithdraw ? (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className={cn("h-7 rounded-full px-3 text-xs", !canAgree && "ml-auto")}
                                      disabled={busy}
                                      onClick={() =>
                                        runAction(
                                          () => esignService.actOnTerm(session.session_id, term.term_id, "withdraw"),
                                          "특약을 철회했습니다.",
                                        )
                                      }
                                    >
                                      철회
                                    </Button>
                                  ) : null}
                                  {!canAgree && !canWithdraw ? (
                                    <span className="ml-auto text-muted-foreground">상대방 합의 대기</span>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                          );
                        })
                      )}

                      {session.status !== "Anchored" && session.status !== "Cancelled" ? (
                        <form
                          className="mt-1 flex items-center gap-2"
                          onSubmit={(event) => {
                            event.preventDefault();
                            const text = termText.trim();
                            if (text.length < 5) {
                              toast.error("특약 내용을 5자 이상 입력하세요.");
                              return;
                            }
                            runAction(() => esignService.proposeTerm(session.session_id, text), "특약을 제안했습니다.");
                            setTermText("");
                          }}
                        >
                          <input
                            value={termText}
                            onChange={(event) => setTermText(event.target.value)}
                            placeholder="특약 직접 제안 (예: 반려동물 사육 시 사전 협의)"
                            className="h-10 min-w-0 flex-1 rounded-full border border-line bg-card px-4 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring"
                          />
                          <Button type="submit" variant="outline" className="h-10 rounded-full" disabled={busy}>
                            <Plus size={15} />
                            제안
                          </Button>
                        </form>
                      ) : null}
                    </CardContent>
                  </Card>
                </motion.div>
              </div>

              {/* 블록체인 기록 + 위변조 검증 */}
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base font-extrabold">
                      <Link2 size={16} className="text-hug-blue" />
                      블록체인 기록 {session.status !== "Anchored" ? "(서명 완료 시)" : ""}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-3">
                    {session.status === "Anchored" ? (
                      <>
                        <div className="rounded-xl bg-hug-navy p-4 font-mono text-xs leading-relaxed text-[#8FE3B8] break-all">
                          contract_hash: {session.contract_hash}
                          <br />
                          tx: {session.tx_hash} · anchored @ {session.anchored_at?.slice(0, 19).replace("T", " ")}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            className="rounded-full"
                            disabled={verifying}
                            onClick={() => runVerify(false)}
                          >
                            원본 무결성 검증
                          </Button>
                          <Button
                            variant="outline"
                            className="rounded-full border-danger-300 text-danger-600 hover:bg-danger-100"
                            disabled={verifying}
                            onClick={() => runVerify(true)}
                          >
                            변조 시나리오 (보증금 +1억)
                          </Button>
                          {session.blockchain_tx_id ? (
                            <Link
                              href={`/blockchain/${session.blockchain_tx_id}`}
                              className="ml-auto text-sm font-semibold text-hug-blue underline underline-offset-2"
                            >
                              트랜잭션 상세 보기 →
                            </Link>
                          ) : null}
                        </div>
                        {verifyResult ? (
                          <motion.div
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={cn(
                              "flex items-start gap-3 rounded-xl border-2 p-4",
                              verifyResult.match
                                ? "border-success-200 bg-hug-mint/50"
                                : "border-danger-300 bg-danger-100/60",
                            )}
                          >
                            {verifyResult.match ? (
                              <CircleCheck size={22} className="shrink-0 text-hug-green" />
                            ) : (
                              <CircleX size={22} className="shrink-0 text-danger-600" />
                            )}
                            <div className="min-w-0 text-sm">
                              <p className={cn("font-extrabold", verifyResult.match ? "text-hug-green-deep" : "text-danger-600")}>
                                {verifyResult.match
                                  ? "해시 일치 — 원본 무결성 확인 ✓"
                                  : "해시 불일치 — 위변조 감지"}
                              </p>
                              <p className="mt-1 break-all font-mono text-xs text-muted-foreground">
                                저장 해시&nbsp;&nbsp;{verifyResult.stored_hash}
                                <br />
                                재계산 해시 {verifyResult.recomputed_hash}
                              </p>
                              {verifyResult.tampered_fields ? (
                                <p className="mt-1 text-xs text-danger-600">
                                  변조 필드: {JSON.stringify(verifyResult.tampered_fields)}
                                </p>
                              ) : null}
                            </div>
                          </motion.div>
                        ) : null}
                        <p className="text-xs text-muted-foreground">
                          원본 해시 재계산 일치 여부로 위변조를 즉시 판별 — 사고·분쟁 시 증거력 확보
                        </p>
                      </>
                    ) : (
                      <p className="flex items-center gap-2 text-sm text-muted-foreground">
                        <UserRound size={15} />
                        양측 서명이 완료되면 계약서 해시가 체인에 자동 앵커링되고, 이 자리에서 위변조 검증을
                        시연할 수 있습니다.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            </motion.div>
          )}
        </main>
      </div>
    </RoleGuard>
  );
}
