"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ShapFactor {
  label: string;
  /** 기여도. 음수=하향(빨강), 양수=상향(초록). */
  value: number;
}

interface ShapBarsProps {
  factors: ShapFactor[];
  className?: string;
}

/**
 * SHAP 요인 기여 바(시안 5-1). |value| 최대치를 100%로 정규화해
 * 좌측 라벨 · 중앙 바(차오르는 모션) · 우측 수치로 표시.
 */
export function ShapBars({ factors, className }: ShapBarsProps) {
  const max = Math.max(...factors.map((f) => Math.abs(f.value)), 0.0001);
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {factors.map((factor, index) => {
        const negative = factor.value < 0;
        const width = (Math.abs(factor.value) / max) * 100;
        return (
          <div
            key={factor.label}
            className="grid grid-cols-[96px_1fr_44px] items-center gap-2 text-xs"
          >
            <span className="truncate text-muted-foreground" title={factor.label}>
              {factor.label}
            </span>
            <div className="h-2 overflow-hidden rounded-full bg-neutral-200">
              <motion.i
                className={cn("block h-full rounded-full", negative ? "bg-danger-500" : "bg-hug-green")}
                initial={{ width: 0 }}
                whileInView={{ width: `${width}%` }}
                viewport={{ once: true }}
                transition={{ duration: 0.7, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>
            <span className={cn("text-right font-bold tnum", negative ? "text-danger-600" : "text-hug-green-deep")}>
              {factor.value > 0 ? "+" : ""}
              {factor.value.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
