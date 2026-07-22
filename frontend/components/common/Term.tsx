"use client";

import { CircleHelp } from "lucide-react";
import {
  AUTO_GLOSSARY_TERMS,
  GLOSSARY,
  type GlossaryEntry,
  type GlossaryKey,
} from "@/lib/glossary";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/** 용어 사전 팝오버 본문 — `<Term>`·`<TermHelp>` 공용. */
function GlossaryContent({ entry }: { entry: GlossaryEntry }) {
  return (
    <PopoverContent className="max-w-64 text-left">
      <p className="text-xs font-extrabold">{entry.term}</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{entry.short}</p>
      {entry.long ? (
        <p className="mt-1.5 border-t border-line pt-1.5 text-[11px] leading-relaxed text-muted-foreground">
          {entry.long}
        </p>
      ) : null}
    </PopoverContent>
  );
}

interface TermProps {
  /** 용어 사전 키 (`lib/glossary.ts`) */
  k: GlossaryKey;
  /** 화면 표기 텍스트 — 생략 시 사전의 `term` */
  children?: React.ReactNode;
  /** 점선 밑줄 표시 여부 (배지 등 자체 스타일이 있으면 false) */
  underline?: boolean;
  className?: string;
}

/**
 * 전문용어 인라인 트리거 (README §19.7) — 점선 밑줄, 데스크톱 호버·모바일 탭으로
 * 용어 설명 팝오버를 연다. 키보드 포커스(Enter/Space)로도 열림.
 */
export function Term({ k, children, underline = true, className }: TermProps) {
  const entry = GLOSSARY[k];
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={150}
        className={cn(
          "cursor-help rounded-xs text-inherit outline-none focus-visible:ring-2 focus-visible:ring-ring/40",
          underline &&
            "underline decoration-neutral-400 decoration-dotted decoration-[1.5px] underline-offset-[3px] hover:decoration-hug-blue",
          className,
        )}
      >
        {children ?? entry.term}
      </PopoverTrigger>
      <GlossaryContent entry={entry} />
    </Popover>
  );
}

/* 자동 매칭 준비물 — 긴 표면형 우선으로 정렬해 "근저당권"이 "근저당"보다 먼저 잡히게 한다. */
const AUTO_SORTED = [...AUTO_GLOSSARY_TERMS].sort((a, b) => b[0].length - a[0].length);
const AUTO_KEY = new Map(AUTO_SORTED);
const AUTO_PATTERN = new RegExp(
  `(${AUTO_SORTED.map(([surface]) => surface.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
  "g",
);

/**
 * 데이터 문자열(위험 요인·특약·권장 조치 등) 안의 전문용어를 자동으로 `<Term>`으로
 * 감싸서 렌더링. 사전에 없는 부분은 일반 텍스트 그대로.
 */
export function GlossaryText({ text }: { text: string }) {
  const parts = text.split(AUTO_PATTERN);
  if (parts.length === 1) return <>{text}</>;
  return (
    <>
      {parts.map((part, index) => {
        const key = AUTO_KEY.get(part);
        return key ? (
          <Term key={`${index}-${part}`} k={key}>
            {part}
          </Term>
        ) : (
          part
        );
      })}
    </>
  );
}

/** 섹션 제목 옆 ⓘ 변형 — 아이콘 호버·탭으로 용어 설명을 연다. */
export function TermHelp({ k, className }: { k: GlossaryKey; className?: string }) {
  const entry = GLOSSARY[k];
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={100}
        aria-label={`${entry.term} 설명`}
        className={cn(
          "inline-flex cursor-help items-center align-[-2px] text-muted-foreground outline-none transition-colors hover:text-hug-blue focus-visible:ring-2 focus-visible:ring-ring/40",
          className,
        )}
      >
        <CircleHelp size={14} />
      </PopoverTrigger>
      <GlossaryContent entry={entry} />
    </Popover>
  );
}
