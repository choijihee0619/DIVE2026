"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { staggerContainer, fadeUp } from "@/lib/motion";
import type { SignalLevel } from "@/components/viz/RiskSignals";

const DOT: Record<SignalLevel, string> = {
  ok: "bg-hug-green",
  warn: "bg-warning-500",
  danger: "bg-danger-500",
  info: "bg-hug-blue",
};

export interface TimelineItem {
  time: string;
  title: ReactNode;
  trailing?: ReactNode;
  level?: SignalLevel;
}

interface TimelineListProps {
  items: TimelineItem[];
  className?: string;
}

/** 계약 타임라인(목업 4번) — 세로 점선 + 컬러 도트, 순차 등장. */
export function TimelineList({ items, className }: TimelineListProps) {
  return (
    <motion.ol
      variants={staggerContainer}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-40px" }}
      className={cn("relative flex flex-col", className)}
    >
      <span className="absolute bottom-2 left-[5px] top-2 w-px border-l border-dashed border-line" aria-hidden />
      {items.map((item, index) => (
        <motion.li key={index} variants={fadeUp} className="relative flex items-center gap-3 py-2 pl-5 text-sm">
          <span
            className={cn(
              "absolute left-0 top-1/2 size-[11px] -translate-y-1/2 rounded-full ring-4 ring-card",
              DOT[item.level ?? "info"],
            )}
            aria-hidden
          />
          <span className="w-28 shrink-0 text-xs text-muted-foreground tnum">{item.time}</span>
          <span className="min-w-0 flex-1 font-medium">{item.title}</span>
          {item.trailing ? <span className="shrink-0 text-xs">{item.trailing}</span> : null}
        </motion.li>
      ))}
    </motion.ol>
  );
}
