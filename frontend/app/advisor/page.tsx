"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bot, ListTodo, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { counselService } from "@/services/counselService";
import { ragService } from "@/services/ragService";
import { RegistryAccessCard } from "@/components/common/RegistryAccessCard";
import { ApiError } from "@/services/apiClient";
import {
  COUNSEL_SOURCE_LABEL,
  COUNSEL_STATUS_LABEL,
  type CounselQueueItem,
  type CounselStatus,
} from "@/types/counsel";
import type { RagAnswerData } from "@/types/rag";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<CounselStatus, string> = {
  Waiting: "bg-warning-100 text-warning-700",
  InProgress: "bg-hug-sky text-hug-blue",
  Answered: "bg-hug-mint text-hug-green-deep",
  Closed: "bg-neutral-200 text-neutral-600",
};

/** rag_chunks 토픽에 존재하지 않는 분류 라벨이 오면 일반문의로 폴백. */
const RAG_TOPICS = new Set([
  "보증금미반환",
  "전세사기",
  "묵시적갱신분쟁",
  "경매·공매",
  "이중·다운계약",
  "원상복구·정산",
  "전출선근저당후",
  "기타·일반문의",
]);

function timeLabel(iso: string) {
  return new Date(iso).toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });
}

/** ADV-00 상담 큐(시안 4-1): 자동분류 태그·우선순위 + 선택 건 유사사례·AI 답변 초안·상태 처리. */
export default function AdvisorQueuePage() {
  const [items, setItems] = useState<CounselQueueItem[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [draft, setDraft] = useState<RagAnswerData | null>(null);
  const [isDrafting, setIsDrafting] = useState(false);
  const [answerNote, setAnswerNote] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  const load = useCallback(() => {
    counselService
      .list({ size: 50 })
      .then((data) => {
        setItems(data.items);
        setSelectedId((prev) => prev ?? data.items[0]?.counsel_id ?? null);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "상담 큐를 불러오지 못했습니다."),
      );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const selected = useMemo(
    () => (items ?? []).find((item) => item.counsel_id === selectedId) ?? null,
    [items, selectedId],
  );

  /** 선택 변경 시 초안·답변 입력 초기화. */
  useEffect(() => {
    setDraft(null);
    setAnswerNote(selected?.answer_note ?? "");
  }, [selectedId, selected?.answer_note]);

  /** 동일 RAG 엔진으로 유사사례+답변 초안 생성 — 분류된 분쟁유형을 토픽으로 사용. */
  const generateDraft = () => {
    if (!selected || isDrafting) return;
    const classifiedTopic = selected.classification.dispute_type;
    const topic = classifiedTopic && RAG_TOPICS.has(classifiedTopic) ? classifiedTopic : "기타·일반문의";
    setIsDrafting(true);
    ragService
      .answer({ topic, question: selected.text.slice(0, 2000), top_k: 3 })
      .then(setDraft)
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "초안 생성에 실패했습니다."),
      )
      .finally(() => setIsDrafting(false));
  };

  const updateStatus = (status: CounselStatus, note?: string) => {
    if (!selected || isUpdating) return;
    setIsUpdating(true);
    counselService
      .update(selected.counsel_id, status, note)
      .then((updated) => {
        setItems((prev) => (prev ?? []).map((item) => (item.counsel_id === updated.counsel_id ? updated : item)));
        toast.success(`상담 상태가 "${COUNSEL_STATUS_LABEL[status]}"(으)로 변경되었습니다.`);
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "상태 변경에 실패했습니다."),
      )
      .finally(() => setIsUpdating(false));
  };

  const waitingCount = (items ?? []).filter((item) => item.status === "Waiting").length;

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
          <ListTodo size={22} className="text-hug-blue" />
          상담 큐
          {items ? (
            <span className="rounded-full bg-warning-100 px-2.5 py-0.5 text-xs font-bold text-warning-700 tnum">
              대기 {waitingCount}건
            </span>
          ) : null}
        </h1>
        <p className="mt-1.5 text-muted-foreground">
          챗봇이 이관한 문의가 분쟁유형·진행단계 자동분류와 함께 유입됩니다. 유사사례와 AI 초안으로 응대
          시간을 줄이세요.
        </p>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-5">
        {/* 큐 테이블 */}
        <motion.div variants={fadeUp} className="xl:col-span-3">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">접수 목록 {items ? `· ${items.length}건` : ""}</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              {items === null ? (
                <Skeleton className="h-48 w-full" />
              ) : items.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  대기 중인 상담이 없습니다. 임차인 챗봇에서 &ldquo;상담사 이관 요청&rdquo; 시 유입됩니다.
                </p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-bold text-muted-foreground">
                      <th className="py-2 pr-2">접수</th>
                      <th className="px-2">요약</th>
                      <th className="px-2">분쟁유형(자동)</th>
                      <th className="px-2">단계(자동)</th>
                      <th className="px-2">우선순위</th>
                      <th className="px-2">상태</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item, index) => (
                      <motion.tr
                        key={item.counsel_id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05, duration: 0.3 }}
                        onClick={() => setSelectedId(item.counsel_id)}
                        className={cn(
                          "cursor-pointer border-b border-line/70 transition-colors last:border-b-0",
                          selectedId === item.counsel_id ? "bg-hug-sky/60" : "hover:bg-neutral-100",
                          item.priority === "high" && "bg-warning-100/40",
                        )}
                      >
                        <td className="py-2.5 pr-2 text-muted-foreground tnum">{timeLabel(item.created_at)}</td>
                        <td className="max-w-52 truncate px-2 font-semibold" title={item.text}>
                          {item.text.replace(/^\[[^\]]*\]\s*/, "")}
                        </td>
                        <td className="px-2">
                          <span className="rounded-full bg-danger-100 px-2 py-0.5 text-xs font-bold text-danger-600">
                            {item.classification.dispute_type ?? "미분류"}
                          </span>
                        </td>
                        <td className="px-2">
                          <span className="rounded-full bg-hug-sky px-2 py-0.5 text-xs font-bold text-hug-blue">
                            {item.classification.consultation_stage ?? "—"}
                          </span>
                        </td>
                        <td className={cn("px-2 font-bold", item.priority === "high" && "text-danger-600")}>
                          {item.priority === "high" ? "높음" : "보통"}
                        </td>
                        <td className="px-2">
                          <span className={cn("rounded-full px-2 py-0.5 text-xs font-bold", STATUS_TONE[item.status])}>
                            {COUNSEL_STATUS_LABEL[item.status]}
                          </span>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* 선택 건 상세 */}
        <motion.div variants={fadeUp} className="flex flex-col gap-4 xl:col-span-2">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-extrabold">선택 건 · 상담 전문</CardTitle>
            </CardHeader>
            <CardContent>
              {selected ? (
                <>
                  <p className="whitespace-pre-wrap rounded-xl bg-neutral-100 p-3 text-sm">{selected.text}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-muted-foreground">
                    <span className="rounded-full bg-neutral-200 px-2 py-0.5 font-semibold">
                      {COUNSEL_SOURCE_LABEL[selected.source]}
                    </span>
                    {selected.classification.classified ? (
                      <span className="rounded-full bg-neutral-200 px-2 py-0.5 font-semibold tnum">
                        분류 신뢰도 {((selected.classification.dispute_confidence ?? 0) * 100).toFixed(0)}% ·{" "}
                        {((selected.classification.stage_confidence ?? 0) * 100).toFixed(0)}%
                      </span>
                    ) : null}
                    {selected.contract_id ? (
                      <span className="rounded-full bg-neutral-200 px-2 py-0.5 font-mono font-semibold">
                        {selected.contract_id}
                      </span>
                    ) : null}
                  </div>
                </>
              ) : (
                <p className="py-4 text-center text-sm text-muted-foreground">좌측에서 상담 건을 선택하세요.</p>
              )}
            </CardContent>
          </Card>

          {selected ? (
            <Card className="rounded-2xl border-line shadow-card">
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-sm font-extrabold">
                  <Bot size={15} className="text-hug-blue" />
                  유사사례 · AI 답변 초안
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {draft ? (
                  <>
                    <div className="max-h-44 overflow-y-auto whitespace-pre-wrap rounded-xl border border-dashed border-line p-3 text-xs leading-relaxed">
                      {draft.answer}
                    </div>
                    <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                      {draft.sources.map((source) => (
                        <li key={source.label} className="truncate">
                          <span
                            className={cn(
                              "mr-1.5 rounded px-1.5 py-0.5 font-bold",
                              source.transcript ? "bg-hug-mint text-hug-green-deep" : "bg-hug-sky text-hug-blue",
                            )}
                          >
                            {source.transcript ? "사례" : "공식"}
                          </span>
                          {source.label}
                          {typeof source.score === "number" ? ` (유사도 ${(source.score * 100).toFixed(0)}%)` : ""}
                        </li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-full"
                      onClick={() => {
                        setAnswerNote(draft.answer);
                        toast.success("초안을 답변란에 붙여넣었습니다. 검토 후 완료 처리하세요.");
                      }}
                    >
                      초안 사용
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    className="rounded-xl"
                    disabled={isDrafting}
                    onClick={generateDraft}
                  >
                    <Sparkles size={14} />
                    {isDrafting ? "생성 중..." : "유사사례 검색 + 초안 생성"}
                  </Button>
                )}
              </CardContent>
            </Card>
          ) : null}

          {selected ? (
            <Card className="rounded-2xl border-line shadow-card">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-extrabold">응대 처리</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2.5">
                <textarea
                  rows={4}
                  value={answerNote}
                  onChange={(event) => setAnswerNote(event.target.value)}
                  placeholder="답변 내용을 작성하거나 AI 초안을 사용하세요."
                  className="w-full rounded-xl border border-line bg-card px-3.5 py-2.5 text-xs leading-relaxed outline-none placeholder:text-muted-foreground focus-visible:border-ring"
                />
                <div className="flex flex-wrap gap-2">
                  {selected.status === "Waiting" ? (
                    <Button
                      size="sm"
                      className="rounded-full"
                      disabled={isUpdating}
                      onClick={() => updateStatus("InProgress")}
                    >
                      상담 시작
                    </Button>
                  ) : null}
                  {/* 백엔드 상태 머신: Waiting→InProgress→Answered (Waiting에서 Answered 직행 불가) */}
                  {selected.status === "InProgress" ? (
                    <Button
                      size="sm"
                      className="rounded-full bg-hug-green hover:bg-hug-green-deep"
                      disabled={isUpdating || answerNote.trim().length === 0}
                      onClick={() => updateStatus("Answered", answerNote.trim())}
                    >
                      답변 완료
                    </Button>
                  ) : null}
                  {selected.status !== "Closed" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-full"
                      disabled={isUpdating}
                      onClick={() => updateStatus("Closed", answerNote.trim() || undefined)}
                    >
                      종결
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </motion.div>
      </div>

      {/* 상담 응대 시 매물 권리관계 확인용 — 등기부 열람(2026-07-21 추가) */}
      <motion.div variants={fadeUp}>
        <RegistryAccessCard />
      </motion.div>
    </motion.div>
  );
}
