"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { staggerContainer, fadeUp } from "@/lib/motion";

export type SignalLevel = "ok" | "warn" | "danger" | "info";

const LAMP: Record<SignalLevel, string> = {
  ok: "bg-hug-green",
  warn: "bg-warning-500",
  danger: "bg-danger-500",
  info: "bg-hug-blue",
};

const PILL: Record<SignalLevel, string> = {
  ok: "bg-hug-mint text-hug-green-deep",
  warn: "bg-warning-100 text-warning-700",
  danger: "bg-danger-100 text-danger-600",
  info: "bg-hug-sky text-hug-blue",
};

const PILL_LABEL: Record<SignalLevel, string> = {
  ok: "양호",
  warn: "주의",
  danger: "위험",
  info: "정보",
};

export interface RiskSignal {
  level: SignalLevel;
  title: ReactNode;
  detail?: ReactNode;
  /** 우측 필 텍스트 커스텀(기본: 양호/주의/위험). */
  pillLabel?: string;
}

interface RiskSignalListProps {
  signals: RiskSignal[];
  className?: string;
}

/** 시안 2-2 위험 신호 리스트 — 신호등 램프 + 우측 판정 필, 순차 등장 모션. */
export function RiskSignalList({ signals, className }: RiskSignalListProps) {
  return (
    <motion.ul
      variants={staggerContainer}
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: "-40px" }}
      className={cn("flex flex-col", className)}
    >
      {signals.map((signal, index) => (
        <motion.li
          key={index}
          variants={fadeUp}
          className="flex items-center gap-3 border-b border-dashed border-line py-2.5 text-sm last:border-b-0"
        >
          <span className={cn("size-2.5 shrink-0 rounded-full", LAMP[signal.level])}>
            {signal.level === "danger" ? (
              <span className="block size-2.5 animate-pulse-soft rounded-full bg-danger-500" />
            ) : null}
          </span>
          <span className="min-w-0 flex-1">
            <b className="font-semibold">{signal.title}</b>
            {signal.detail ? <span className="text-muted-foreground"> — {signal.detail}</span> : null}
          </span>
          <span
            className={cn(
              "shrink-0 rounded-full px-2.5 py-0.5 text-xs font-bold",
              PILL[signal.level],
            )}
          >
            {signal.pillLabel ?? PILL_LABEL[signal.level]}
          </span>
        </motion.li>
      ))}
    </motion.ul>
  );
}
