import Link from "next/link";
import { cn } from "@/lib/utils";

interface BrandLogoProps {
  href?: string;
  size?: "sm" | "lg";
  className?: string;
}

/** "HUG X ㈜아이엔" 공동 브랜드 텍스트 로고(목업 상단 로고 대응, 이미지 에셋 없이 타이포로 구성). */
export function BrandLogo({ href = "/", size = "sm", className }: BrandLogoProps) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-baseline gap-1.5 font-extrabold tracking-tight",
        size === "lg" ? "text-3xl" : "text-lg",
        className,
      )}
    >
      <span className="text-hug-blue">HUG</span>
      <span className={cn("font-semibold text-ink-soft", size === "lg" ? "text-xl" : "text-xs")}>×</span>
      <span className="text-hug-navy">㈜아이엔</span>
    </Link>
  );
}
