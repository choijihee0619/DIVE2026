"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useSessionStore } from "@/stores/useSessionStore";
import { ROLE_HOME_ROUTE } from "@/types/enums";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { BrandLogo } from "@/components/common/BrandLogo";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** 260721 목업 1번 랜딩 — 로고, 슬로건, 주소 검색바, 역할 3분기 카드. */
const ROLE_CARDS = [
  { key: "tenant", label: "임차인", tone: "bg-brand-cyan" },
  { key: "landlord", label: "임대인", tone: "bg-brand-lime" },
  { key: "hug", label: "HUG", tone: "bg-brand-cyan" },
] as const;

export default function RootPage() {
  const router = useRouter();
  const user = useSessionStore((state) => state.user);
  const isHydrating = useSessionStore((state) => state.isHydrating);
  const [address, setAddress] = useState("");

  useEffect(() => {
    if (isHydrating || !user) return;
    router.replace(ROLE_HOME_ROUTE[user.role]);
  }, [isHydrating, user, router]);

  if (isHydrating || user) {
    return (
      <main className="flex min-h-svh items-center justify-center">
        <LoadingSpinner label="이동 중..." />
      </main>
    );
  }

  const startDiagnosis = () => {
    if (address.trim().length > 0) {
      toast.info("로그인 후 입력한 주소로 위험 진단을 이어갑니다.");
    }
    router.push("/login?role=tenant");
  };

  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-card px-6 py-16">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="flex w-full max-w-3xl flex-col items-center"
      >
        <motion.div variants={fadeUp}>
          <BrandLogo size="lg" />
        </motion.div>

        <motion.p variants={fadeUp} className="mt-10 text-xl font-bold tracking-tight text-ink">
          모든 사람들이 집으로 행복한 세상을 만듭니다.
        </motion.p>

        <motion.form
          variants={fadeUp}
          className="mt-8 flex w-full items-center gap-3 rounded-full border-[3px] border-hug-navy bg-card py-3 pl-7 pr-4 shadow-card focus-within:shadow-card-lg"
          onSubmit={(event) => {
            event.preventDefault();
            startDiagnosis();
          }}
        >
          <label htmlFor="landing-address" className="shrink-0 text-lg font-bold text-ink">
            주소 :
          </label>
          <input
            id="landing-address"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder="예) 부산광역시 부산진구 동천로 10-1"
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400"
          />
          <button
            type="submit"
            aria-label="안심 리포트 진단 시작"
            className="flex size-10 shrink-0 items-center justify-center rounded-full bg-hug-navy text-white transition-transform hover:scale-105 active:scale-95"
          >
            <Plus size={22} strokeWidth={3} />
          </button>
        </motion.form>

        <div className="mt-12 grid w-full grid-cols-1 gap-6 sm:grid-cols-3">
          {ROLE_CARDS.map((card) => (
            <motion.button
              key={card.key}
              type="button"
              variants={fadeUp}
              whileHover={{ y: -8, scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => router.push(`/login?role=${card.key}`)}
              className={cn(
                "flex h-64 items-center justify-center rounded-[36px] text-3xl font-extrabold text-white shadow-card transition-shadow hover:shadow-card-lg",
                card.tone,
              )}
            >
              {card.label}
            </motion.button>
          ))}
        </div>

        <motion.p variants={fadeUp} className="mt-10 text-sm text-muted-foreground">
          계약 전 예방 → 전자계약 → 거주 중 모니터링 → 사고 후 회수, 하나의 루프
        </motion.p>
      </motion.div>
    </main>
  );
}
