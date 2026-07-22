"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ShapFactor {
  label: string;
  /** 기여도. 음수=내림(빨강, 좌측), 양수=올림(파랑, 우측). */
  value: number;
}

interface ShapBarsProps {
  factors: ShapFactor[];
  className?: string;
}

/**
 * 요인 기여 발산형 바 (README §19.6). 중앙 축 기준 내림(빨강)은 좌측,
 * 올림(파랑)은 우측으로 뻗는다. |value| 최대치를 반폭 100%로 정규화.
 */
export function ShapBars({ factors, className }: ShapBarsProps) {
  const max = Math.max(...factors.map((f) => Math.abs(f.value)), 0.0001);
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {factors.map((factor, index) => {
        const negative = factor.value < 0;
        const width = (Math.abs(factor.value) / max) * 100;
        const bar = (
          <motion.i
            className={cn(
              "block h-full",
              negative ? "rounded-l-full bg-danger-500" : "rounded-r-full bg-hug-blue",
            )}
            initial={{ width: 0 }}
            whileInView={{ width: `${width}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
          />
        );
        return (
          <div
            key={factor.label}
            className="grid grid-cols-[88px_1fr_52px] items-center gap-2 text-xs"
          >
            <span className="truncate text-muted-foreground" title={factor.label}>
              {factor.label}
            </span>
            <div className="relative grid h-2.5 grid-cols-2 overflow-hidden rounded-full bg-neutral-200">
              <span className="flex justify-end">{negative ? bar : null}</span>
              <span>{negative ? null : bar}</span>
              <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-card" />
            </div>
            <span className={cn("text-right font-bold tnum", negative ? "text-danger-600" : "text-hug-blue")}>
              {negative ? "▼" : "▲"} {factor.value > 0 ? "+" : ""}
              {factor.value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
