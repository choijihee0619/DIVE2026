"use client";

import { cn } from "@/lib/utils";

export interface FactorSentenceItem {
  /** 요인 이름 (예: "발생금액") */
  name: string;
  /** 표시용 값 (예: "4.8억", "구상채권") — 없으면 값 없이 문장 조립 */
  value?: string;
  /** SHAP 기여도 — 양수 올림(▲), 음수 내림(▼) */
  shap: number;
}

interface FactorSentencesProps {
  factors: FactorSentenceItem[];
  className?: string;
}

/** 마지막 글자 받침 유무 → "이라서"/"라서". 닫는 괄호는 건너뛰고, 한글·숫자 외에는 병기. */
function raseo(word: string): string {
  const trimmed = word.replace(/[)\]}"']+$/, "");
  const last = trimmed.charAt(trimmed.length - 1);
  const code = last.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 ? "이라서" : "라서";
  if (last >= "0" && last <= "9") return "013678".includes(last) ? "이라서" : "라서";
  return "(이)라서";
}

/** |shap| 상대 크기 → 정도 부사. */
function magnitude(abs: number, max: number): string {
  if (abs >= max * 0.66) return "크게 ";
  if (abs >= max * 0.33) return "";
  return "약간 ";
}

/**
 * SHAP 요인 자동 문장화 (README §19.6) — "{요인} 값이 {값}이라서 회수율을 크게
 * 올렸습니다" 형태로 조립. 알고리즘 수치 대신 업무 언어로 읽히는 판단 근거.
 */
export function FactorSentences({ factors, className }: FactorSentencesProps) {
  const max = Math.max(...factors.map((f) => Math.abs(f.shap)), 0.0001);
  return (
    <ul className={cn("flex flex-col gap-1 text-xs", className)}>
      {factors.map((factor) => {
        const up = factor.shap >= 0;
        return (
          <li key={`${factor.name}-${factor.value ?? ""}`} className="flex items-start gap-1.5">
            <span aria-hidden className={cn("shrink-0 text-[10px] leading-4.5 font-bold", up ? "text-hug-blue" : "text-danger-600")}>
              {up ? "▲" : "▼"}
            </span>
            <span className="leading-relaxed text-muted-foreground">
              <b className="font-semibold text-foreground">{factor.name}</b>
              {factor.value ? (
                <>
                  {" 값이 "}
                  <b className="font-semibold text-foreground tnum">{factor.value}</b>
                  {raseo(factor.value)}
                </>
              ) : (
                " 요인이"
              )}{" "}
              회수율을 {magnitude(Math.abs(factor.shap), max)}
              <b className={cn("font-semibold", up ? "text-hug-blue" : "text-danger-600")}>
                {up ? "올렸습니다" : "내렸습니다"}
              </b>
              .
            </span>
          </li>
        );
      })}
    </ul>
  );
}
