"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { fadeUp } from "@/lib/motion";

const TONES = {
  cyan: "bg-brand-cyan text-white",
  lime: "bg-brand-lime text-white",
  blue: "bg-hug-blue text-white",
  green: "bg-hug-green text-white",
  navy: "bg-hug-navy text-white",
} as const;

interface StatPillProps {
  label: string;
  /** 큰 수치 영역. AnimatedNumber 등 자유 구성. */
  children: ReactNode;
  tone?: keyof typeof TONES;
  onClick?: () => void;
  className?: string;
}

/**
 * 260721 목업의 알약형 KPI 카드(내 계약 3건 / 주의 필요 1건 / 궁금한 내용은! AI).
 * 좌측 라벨 + 우측 대형 수치, 완전 라운드.
 */
export function StatPill({ label, children, tone = "cyan", onClick, className }: StatPillProps) {
  return (
    <motion.div
      variants={fadeUp}
      whileHover={onClick ? { y: -3, scale: 1.015 } : undefined}
      whileTap={onClick ? { scale: 0.985 } : undefined}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") onClick();
            }
          : undefined
      }
      className={cn(
        "flex items-center justify-between gap-3 rounded-[32px] px-7 py-6 shadow-card",
        TONES[tone],
        onClick && "cursor-pointer",
        className,
      )}
    >
      <span className="text-base font-semibold whitespace-nowrap">{label}</span>
      <span className="text-4xl font-extrabold leading-none tnum">{children}</span>
    </motion.div>
  );
}
