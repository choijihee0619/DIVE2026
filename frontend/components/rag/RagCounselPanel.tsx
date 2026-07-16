"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ragService } from "@/services/ragService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import type { RagAnswerData } from "@/types/rag";

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

/** RAG 상담 패널: POST /rag/answer 실데이터(tenant/advisor 공용). */
export function RagCounselPanel() {
  const router = useRouter();
  const clearSession = useSessionStore((state) => state.clearSession);

  const [topic, setTopic] = useState<string>(TOPICS[0]);
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RagAnswerData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const canSubmit = question.trim().length > 0 && !isLoading;

  const submit = () => {
    if (!canSubmit) return;
    setIsLoading(true);
    setErrorMessage(null);
    setResult(null);
    ragService
      .answer({ topic, question: question.trim(), top_k: 3 })
      .then(setResult)
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
        setErrorMessage(
          error instanceof ApiError ? `${error.message} (${error.errorCode})` : "답변을 불러오지 못했습니다.",
        );
      })
      .finally(() => setIsLoading(false));
  };

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>AI 전세 상담</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              submit();
            }}
          >
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rag-topic">상담 주제</Label>
              <select
                id="rag-topic"
                value={topic}
                onChange={(event) => setTopic(event.target.value)}
                className="h-8 w-full max-w-xs rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                {TOPICS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rag-question">질문</Label>
              <textarea
                id="rag-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="예: 집주인이 보증금을 돌려주지 않으면 어떻게 해야 하나요?"
                rows={3}
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>
            <div>
              <Button type="submit" disabled={!canSubmit}>
                {isLoading ? "답변 생성 중..." : "질문하기"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {errorMessage ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
            <p className="text-sm text-destructive">{errorMessage}</p>
            <Button variant="outline" onClick={submit} disabled={isLoading}>
              다시 시도
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {isLoading ? (
        <Card aria-label="답변 생성 중">
          <CardContent className="flex flex-col gap-2 py-6">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-2/3" />
          </CardContent>
        </Card>
      ) : null}

      {result ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>답변</CardTitle>
            <Badge variant={result.is_mock ? "outline" : "secondary"}>
              {result.is_mock ? "목업 응답" : "실데이터 기반"}
            </Badge>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
            <Separator />
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-medium">참고 자료 {result.sources.length}건</h3>
              {result.sources.map((source) => (
                <div key={source.label} className="rounded-lg border border-border p-3">
                  <div className="mb-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{source.label}</span>
                    {source.topic ? <Badge variant="outline">{source.topic}</Badge> : null}
                    {typeof source.score === "number" ? (
                      <span>유사도 {(source.score * 100).toFixed(1)}%</span>
                    ) : null}
                  </div>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{source.summary}</p>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">{result.disclaimer}</p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
