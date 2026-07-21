"use client";

import { Fragment } from "react";
import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export interface StepItem {
  label: string;
  /** 보조 문구(예: 진행 중 / 대기 중 / 완료일). */
  caption?: string;
}

interface ContractStepperProps {
  steps: StepItem[];
  /** 0-base 현재 단계 인덱스. */
  current: number;
  className?: string;
}

/**
 * 계약 진행 5단계 스텝퍼(목업 5번). 완료=체크, 현재=파란 원(펄스), 대기=회색.
 * 연결선은 진행률까지 파란색으로 차오른다.
 */
export function ContractStepper({ steps, current, className }: ContractStepperProps) {
  return (
    <ol className={cn("flex items-start", className)}>
      {steps.map((step, index) => {
        const done = index < current;
        const now = index === current;
        return (
          <Fragment key={step.label}>
            {index > 0 ? (
              <div className="relative mt-[17px] h-0.5 flex-1 bg-line" aria-hidden>
                <motion.div
                  className="absolute inset-y-0 left-0 bg-hug-blue"
                  initial={{ width: 0 }}
                  whileInView={{ width: index <= current ? "100%" : "0%" }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: index * 0.12, ease: "easeOut" }}
                />
              </div>
            ) : null}
            <li className="flex w-24 shrink-0 flex-col items-center gap-1.5 text-center">
              <motion.span
                initial={{ scale: 0.6, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ duration: 0.35, delay: index * 0.12, type: "spring", bounce: 0.4 }}
                className={cn(
                  "flex size-9 items-center justify-center rounded-full border-2 text-sm font-bold",
                  done && "border-hug-green bg-hug-green text-white",
                  now && "border-hug-blue bg-hug-blue text-white shadow-[0_0_0_5px_var(--color-hug-sky)]",
                  !done && !now && "border-line bg-card text-muted-foreground",
                )}
                aria-current={now ? "step" : undefined}
              >
                {done ? <Check size={16} strokeWidth={3} /> : index + 1}
              </motion.span>
              <span
                className={cn(
                  "text-xs font-semibold leading-tight",
                  now ? "text-hug-blue" : done ? "text-hug-green-deep" : "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
              {step.caption ? (
                <span className="text-[11px] leading-none text-muted-foreground">{step.caption}</span>
              ) : null}
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}
