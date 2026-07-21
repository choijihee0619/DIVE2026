import { RagCounselPanel } from "@/components/rag/RagCounselPanel";

/** TEN-05 AI 전세 상담(RAG) — 260721 목업 6번. */
export default function TenantCounselPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
          AI 전세 상담
          <span className="rounded-full border border-line bg-card px-2.5 py-0.5 text-xs font-bold text-muted-foreground">
            Beta
          </span>
        </h1>
        <p className="mt-1.5 text-muted-foreground">전세 계약 관련 궁금한 내용을 AI가 맞춤형으로 상담해드려요.</p>
      </div>
      <RagCounselPanel />
    </div>
  );
}
