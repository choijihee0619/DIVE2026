import { RagCounselPanel } from "@/components/rag/RagCounselPanel";

/** ADV-02 AI 상담 지원(RAG) — 상담사용 동일 엔진. */
export default function AdvisorCounselPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">AI 상담 지원</h1>
        <p className="mt-1.5 text-muted-foreground">유사사례·공식자료 검색으로 상담 응대를 보조합니다.</p>
      </div>
      <RagCounselPanel />
    </div>
  );
}
