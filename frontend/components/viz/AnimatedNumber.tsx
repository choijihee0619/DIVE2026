"use client";

import { useEffect, useRef, useState } from "react";
import { animate, useInView, useReducedMotion } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  /** 소수 자릿수(기본 0). */
  decimals?: number;
  /** 표기 커스텀(예: 억 단위 축약). 지정 시 decimals는 무시된다. */
  format?: (value: number) => string;
  durationSec?: number;
  className?: string;
}

/** 뷰포트 진입 시 0→value로 카운트업하는 숫자. 대시보드 KPI 공용. */
export function AnimatedNumber({
  value,
  decimals = 0,
  format,
  durationSec = 1.1,
  className,
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (reduced) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration: durationSec,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: setDisplay,
    });
    return () => controls.stop();
  }, [inView, value, durationSec, reduced]);

  const text = format
    ? format(display)
    : display.toLocaleString("ko-KR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });

  return (
    <span ref={ref} className={className ? `tnum ${className}` : "tnum"}>
      {text}
    </span>
  );
}
