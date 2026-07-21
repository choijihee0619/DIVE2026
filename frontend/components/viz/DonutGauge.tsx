"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

interface DonutGaugeProps {
  /** 0~1. 채워지는 비율. */
  ratio: number;
  size?: number;
  strokeWidth?: number;
  /** 트랙 위에 채워지는 색(CSS 색상값). */
  color?: string;
  trackColor?: string;
  /** 중앙 콘텐츠. */
  children?: ReactNode;
  className?: string;
}

/**
 * 계약 상세 "계약 현황 요약"의 도넛 게이지(목업 4번). 진입 시 호가 차오르는 모션.
 */
export function DonutGauge({
  ratio,
  size = 148,
  strokeWidth = 12,
  color = "var(--color-hug-blue)",
  trackColor = "var(--color-hug-sky)",
  children,
  className,
}: DonutGaugeProps) {
  const reduced = useReducedMotion();
  const clamped = Math.max(0, Math.min(1, ratio));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={`진행률 ${Math.round(clamped * 100)}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: reduced ? circumference * (1 - clamped) : circumference }}
          whileInView={{ strokeDashoffset: circumference * (1 - clamped) }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1], delay: 0.15 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        {children}
      </div>
    </div>
  );
}
