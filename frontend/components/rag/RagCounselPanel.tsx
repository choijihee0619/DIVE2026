"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, FileText, NotebookPen, SendHorizontal } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ragService } from "@/services/ragService";
import { counselService } from "@/services/counselService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { RagAnswerData, RagSource } from "@/types/rag";
import { Term, TermHelp } from "@/components/common/Term";
import type { CounselQueueItem } from "@/types/counsel";
import { cn } from "@/lib/utils";

/** rag_chunks 컬렉션에 실재하는 토픽 목록(backend 데이터 기준). */
const TOPICS = [
  "보증금미반환",
  "전세사기",
  "묵시적갱신분쟁",
  "경매·공매",
  "이중·다운계약",
  "원상복구·정산",
  "전출선근저당후",
  "기타·일반문의",
] as const;

interface ChatMessage {
  role: "me" | "ai";
  text: string;
  sources?: RagSource[];
  isMock?: boolean;
}

function nowLabel() {
  return new Date().toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
}

/**
 * RAG 상담 패널(260721 목업 6번 채팅형): POST /rag/answer 실데이터(tenant/advisor 공용).
 * 백엔드는 단발 질의응답이지만 화면에서는 대화 스레드로 누적 표시한다.
 */
export function RagCounselPanel() {
  const router = useRouter();
  const clearSession = useSessionStore((state) => state.clearSession);

  const [topic, setTopic] = useState<string>(TOPICS[0]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResult, setLastResult] = useState<RagAnswerData | null>(null);
  const [openedSource, setOpenedSource] = useState<RagSource | null>(null);
  const [escalation, setEscalation] = useState<CounselQueueItem | null>(null);
  const [isEscalating, setIsEscalating] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const canSubmit = question.trim().length > 0 && !isLoading;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, isLoading]);

  const submit = () => {
    if (!canSubmit) return;
    const asked = question.trim();
    setQuestion("");
    setMessages((prev) => [...prev, { role: "me", text: asked }]);
    setIsLoading(true);
    ragService
      .answer({ topic, question: asked, top_k: 3 })
      .then((result) => {
        setLastResult(result);
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: result.answer, sources: result.sources, isMock: result.is_mock },
        ]);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.httpStatus === 401) {
          clearSession();
          router.replace("/login");
          return;
        }
        if (error instanceof ApiError && error.httpStatus === 403) {
          router.replace("/unauthorized");
          return;
        }
        const message =
          error instanceof ApiError ? `${error.message} (${error.errorCode})` : "답변을 불러오지 못했습니다.";
        setMessages((prev) => [...prev, { role: "ai", text: `죄송합니다. ${message}` }]);
      })
      .finally(() => setIsLoading(false));
  };

  /** 대화 내용을 묶어 상담사 큐로 이관(POST /counsel-queue) — 응답의 자동분류를 우측 패널에 반영. */
  const requestEscalation = () => {
    if (isEscalating || escalation) return;
    const asked = messages.filter((m) => m.role === "me").map((m) => m.text);
    if (asked.length === 0) {
      toast.error("먼저 궁금한 내용을 대화로 남겨 주세요. 대화 내용이 상담사에게 전달됩니다.");
      return;
    }
    setIsEscalating(true);
    counselService
      .create({ text: `[${topic}] ${asked.join("\n")}`, source: "chatbot_escalation" })
      .then((item) => {
        setEscalation(item);
        toast.success("상담사 연결이 요청되었습니다. 대화 내용과 자동분류가 함께 전달돼요.");
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "상담사 연결 요청에 실패했습니다."),
      )
      .finally(() => setIsEscalating(false));
  };

  /** transcript가 있으면 상담사례(그린), 없으면 공식자료(블루)로 구분 표기(시안 2-3). */
  const sourceChipTone = (source: RagSource) =>
    source.transcript
      ? "border-success-200 bg-hug-mint text-hug-green-deep"
      : "border-accent-200 bg-hug-sky text-hug-blue";

  return (
    <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[1fr_300px]">
      {/* 대화 영역 */}
      <Card className="flex h-[calc(100svh-220px)] min-h-[480px] flex-col rounded-2xl border-line shadow-card">
        <CardHeader className="border-b border-line/70 pb-4">
          <CardTitle className="flex items-center gap-2 text-base font-extrabold">
            <span className="flex size-8 items-center justify-center rounded-full bg-hug-blue text-white">
              <Bot size={16} />
            </span>
            AI 전세상담 · 대화
            <select
              aria-label="상담 주제"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              className="ml-auto h-8 rounded-full border border-line bg-card px-3 text-xs font-semibold outline-none focus-visible:border-ring"
            >
              {TOPICS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </CardTitle>
        </CardHeader>
        <CardContent ref={scrollRef} className="flex-1 overflow-y-auto py-5">
          <div className="flex flex-col gap-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-14 text-center text-sm text-muted-foreground">
                <Bot size={28} className="text-hug-blue" />
                <p className="font-semibold text-foreground">전세 계약 관련 궁금한 내용을 AI가 맞춤형으로 상담해드려요.</p>
                <p>예: “집주인이 보증금을 돌려주지 않으면 어떻게 해야 하나요?”</p>
              </div>
            ) : null}
            <AnimatePresence initial={false}>
              {messages.map((message, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 12, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.3, ease: "easeOut" }}
                  className={cn("flex items-end gap-2", message.role === "me" ? "justify-end" : "justify-start")}
                >
                  {message.role === "ai" ? (
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-hug-sky text-hug-blue">
                      <Bot size={14} />
                    </span>
                  ) : null}
                  <div
                    className={cn(
                      "max-w-[82%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap",
                      message.role === "me"
                        ? "rounded-br-md bg-hug-blue text-white"
                        : "rounded-bl-md border border-line bg-card shadow-card",
                    )}
                  >
                    {message.text}
                    {message.sources && message.sources.length > 0 ? (
                      <span className="mt-2.5 flex flex-wrap gap-1.5">
                        {message.sources.map((source) => (
                          <button
                            key={source.label}
                            type="button"
                            onClick={() => (source.transcript ? setOpenedSource(source) : undefined)}
                            className={cn(
                              "rounded-md border px-2 py-0.5 text-[11px] font-bold",
                              sourceChipTone(source),
                              source.transcript ? "cursor-pointer hover:opacity-80" : "cursor-default",
                            )}
                            title={source.summary}
                          >
                            {source.transcript ? "사례" : "공식"} · {source.label}
                            {typeof source.score === "number" ? ` (${(source.score * 100).toFixed(0)}%)` : ""}
                          </button>
                        ))}
                        {message.isMock ? (
                          <Badge variant="outline" className="text-[10px]">
                            목업 응답
                          </Badge>
                        ) : null}
                      </span>
                    ) : null}
                    <span
                      className={cn(
                        "mt-1.5 block text-[10px]",
                        message.role === "me" ? "text-white/70" : "text-muted-foreground",
                      )}
                    >
                      {nowLabel()}
                    </span>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
            {isLoading ? (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-end gap-2"
                aria-label="답변 생성 중"
              >
                <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-hug-sky text-hug-blue">
                  <Bot size={14} />
                </span>
                <div className="flex gap-1 rounded-2xl rounded-bl-md border border-line bg-card px-4 py-3.5 shadow-card">
                  {[0, 1, 2].map((dot) => (
                    <motion.span
                      key={dot}
                      className="size-1.5 rounded-full bg-neutral-400"
                      animate={{ y: [0, -4, 0] }}
                      transition={{ repeat: Infinity, duration: 0.9, delay: dot * 0.15 }}
                    />
                  ))}
                </div>
              </motion.div>
            ) : null}
          </div>
        </CardContent>
        <div className="border-t border-line/70 p-4">
          <form
            className="flex items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="질문을 입력하세요..."
              aria-label="질문"
              className="h-11 min-w-0 flex-1 rounded-full border border-line bg-card px-4 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
            />
            <Button type="submit" disabled={!canSubmit} className="h-11 rounded-full px-5">
              <SendHorizontal size={16} />
              전송
            </Button>
          </form>
          <p className="mt-2 text-[11px] text-muted-foreground">AI 상담은 참고용이며, 법적 효력이 없습니다.</p>
        </div>
      </Card>

      {/* 우측 패널 — 분류/상담사 연결/함께 본 자료/상담 노트 */}
      <div className="flex flex-col gap-4">
        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-extrabold">
              이 대화의 분류
              <span className="rounded-full bg-hug-sky px-2 py-0.5 text-[10px] font-bold text-hug-blue">자동</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {escalation?.classification.classified ? (
              <>
                <Term k="disputeType">분쟁유형</Term>: <b>{escalation.classification.dispute_type}</b>{" "}
                <span className="text-xs text-muted-foreground tnum">
                  ({((escalation.classification.dispute_confidence ?? 0) * 100).toFixed(0)}%)
                </span>
                <br />
                <Term k="counselStage">진행단계</Term>: <b>{escalation.classification.consultation_stage}</b>{" "}
                <span className="text-xs text-muted-foreground tnum">
                  ({((escalation.classification.stage_confidence ?? 0) * 100).toFixed(0)}%)
                </span>
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  비식별 상담 학습 분류 모델 — 상담사 큐 라우팅에 사용
                </p>
              </>
            ) : (
              <>
                <Term k="disputeType">분쟁유형</Term>: <b>{topic}</b>
                <br />
                <Term k="counselStage">진행단계</Term>: <b>{messages.length > 0 ? "상담·검토" : "대기"}</b>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-extrabold">전문 상담이 필요하신가요?</CardTitle>
          </CardHeader>
          <CardContent>
            {escalation ? (
              <div className="rounded-xl bg-hug-mint p-3 text-xs leading-relaxed text-hug-green-deep">
                <p className="font-bold">상담사 배정 대기 중</p>
                <p className="mt-0.5">
                  접수번호 <b className="font-mono">{escalation.counsel_id.slice(0, 8).toUpperCase()}</b> ·
                  우선순위 {escalation.priority === "high" ? "높음" : "보통"}
                </p>
                <p className="mt-0.5 text-hug-green-deep/80">대화 내용이 상담사 큐로 전달되었습니다.</p>
              </div>
            ) : (
              <>
                <p className="mb-3 text-xs leading-relaxed text-muted-foreground">
                  AI가 답할 수 없는 사안은 아이엔 상담사·변호사 상담으로 연결됩니다.
                </p>
                <Button
                  className="w-full rounded-xl bg-hug-green font-bold hover:bg-hug-green-deep"
                  disabled={isEscalating}
                  onClick={requestEscalation}
                >
                  {isEscalating ? "요청 중..." : "상담사 이관 요청"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm font-extrabold">
              <FileText size={14} className="text-hug-blue" />
              함께 본 자료
              <TermHelp k="ragEvidence" />
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs leading-relaxed text-muted-foreground">
            {lastResult && lastResult.sources.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {lastResult.sources.map((source) => (
                  <li key={source.label} className="truncate">
                    · {source.label}
                    {source.topic ? ` (${source.topic})` : ""}
                  </li>
                ))}
              </ul>
            ) : (
              <>
                · 전세사기 유형별 대처방안
                <br />
                · 주택임대차보호법 제3조
                <br />
                · HUG 보증가입 절차
              </>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-line shadow-card">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-1.5 text-sm font-extrabold">
              <NotebookPen size={14} className="text-hug-blue" />
              상담 노트
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-xs text-muted-foreground">현재 대화 내용은 상담 노트에 자동 저장됩니다.</p>
            <Button
              variant="outline"
              className="w-full rounded-xl font-bold"
              onClick={() => toast.info("상담 노트는 상담사 이관 시 함께 전달됩니다.")}
            >
              노트 확인하기 →
            </Button>
          </CardContent>
        </Card>
      </div>

      <Dialog open={openedSource !== null} onOpenChange={(open) => !open && setOpenedSource(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {openedSource?.label} 상담 원문
              {openedSource?.topic ? ` — ${openedSource.topic}` : ""}
            </DialogTitle>
            <DialogDescription>개인정보가 마스킹된 과거 상담 기록 원문입니다.</DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto rounded-lg bg-muted/50 p-4">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{openedSource?.transcript}</p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
