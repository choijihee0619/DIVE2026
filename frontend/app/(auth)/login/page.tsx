"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { BrandLogo } from "@/components/common/BrandLogo";
import { authService } from "@/services/authService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import { ROLE_HOME_ROUTE } from "@/types/enums";
import { staggerContainer, fadeUp } from "@/lib/motion";

const loginSchema = z.object({
  email: z.string().min(1, "이메일을 입력하세요.").email("올바른 이메일 형식이 아닙니다."),
  password: z.string().min(1, "비밀번호를 입력하세요."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

/** 랜딩 역할 카드 → 데모 계정 프리필(데모 계정·공통 비밀번호는 공개 사양). */
const ROLE_DEMO_EMAIL: Record<string, string> = {
  tenant: "tenant01@example.com",
  landlord: "landlord01@example.com",
  advisor: "advisor01@example.com",
  hug: "hugadmin01@example.com",
  admin: "sysadmin01@example.com",
};

/** 화면에 노출할 계정 목록 — 임차인 B(tenant02, 사고 처리 스토리)를 포함한다. */
const DEMO_ACCOUNTS = [
  "tenant01@example.com",
  "tenant02@example.com",
  "landlord01@example.com",
  "advisor01@example.com",
  "hugadmin01@example.com",
  "sysadmin01@example.com",
];

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setSession = useSessionStore((state) => state.setSession);
  const [submitting, setSubmitting] = useState(false);

  const roleParam = searchParams.get("role");
  const prefillEmail = roleParam ? ROLE_DEMO_EMAIL[roleParam] : undefined;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: prefillEmail ? { email: prefillEmail, password: "P@ssw0rd!" } : undefined,
  });

  const onSubmit = async (values: LoginFormValues) => {
    setSubmitting(true);
    try {
      const data = await authService.login(values);
      setSession(data.access_token, data.expires_in, data.user);
      toast.success(`${data.user.display_name}님 환영합니다.`);
      const next = searchParams.get("next");
      router.push(next ?? ROLE_HOME_ROUTE[data.user.role]);
    } catch (error) {
      const message = error instanceof ApiError ? error.message : "로그인에 실패했습니다.";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const firstError = errors.email?.message ?? errors.password?.message;

  return (
    <main className="flex min-h-svh flex-col items-center justify-center bg-card px-6 py-16">
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="show"
        className="flex w-full max-w-md flex-col items-center"
      >
        <motion.div variants={fadeUp}>
          <BrandLogo size="lg" />
        </motion.div>

        {/* 260721 목업 2번 — ID/PW 라운드 필드 + 네이비 로그인 버튼 */}
        <motion.form
          variants={fadeUp}
          onSubmit={handleSubmit(onSubmit)}
          noValidate
          className="mt-14 flex w-full flex-col gap-3"
        >
          <label className="flex items-center gap-3 rounded-2xl border-2 border-hug-navy bg-card px-5 py-3.5 focus-within:shadow-card">
            <span className="shrink-0 text-base font-extrabold text-ink">ID :</span>
            <input
              type="email"
              autoComplete="email"
              aria-label="이메일"
              aria-invalid={Boolean(errors.email)}
              placeholder="이메일"
              className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400"
              {...register("email")}
            />
          </label>
          <label className="flex items-center gap-3 rounded-2xl border-2 border-hug-navy bg-card px-5 py-3.5 focus-within:shadow-card">
            <span className="shrink-0 text-base font-extrabold text-ink">PW :</span>
            <input
              type="password"
              autoComplete="current-password"
              aria-label="비밀번호"
              aria-invalid={Boolean(errors.password)}
              placeholder="비밀번호"
              className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-neutral-400"
              {...register("password")}
            />
          </label>
          {firstError ? (
            <p role="alert" className="px-2 text-sm font-semibold text-danger-600">
              {firstError}
            </p>
          ) : null}
          <motion.button
            type="submit"
            disabled={submitting}
            whileTap={{ scale: 0.98 }}
            className="mt-1 flex items-center justify-center rounded-2xl bg-hug-navy py-3.5 text-base font-extrabold tracking-[0.3em] text-white transition-opacity hover:opacity-90 disabled:opacity-60"
          >
            {submitting ? <LoadingSpinner size={18} label="로그인 중..." /> : "로그인"}
          </motion.button>
          <button
            type="button"
            onClick={() => toast.info("데모 버전에서는 준비된 데모 계정으로 로그인해 주세요.")}
            className="flex items-center justify-center rounded-2xl border-2 border-hug-navy bg-card py-3.5 text-base font-extrabold tracking-[0.3em] text-ink transition-colors hover:bg-neutral-100"
          >
            회원가입
          </button>
        </motion.form>

        <motion.p variants={fadeUp} className="mt-5 text-sm font-bold text-ink">
          ID 찾기 <span className="mx-2 text-neutral-400">|</span> PW 찾기
        </motion.p>

        <motion.div
          variants={fadeUp}
          className="mt-8 w-full rounded-2xl bg-neutral-100 p-4 text-xs text-muted-foreground"
        >
          <p className="mb-1 font-bold text-foreground">데모 계정 (공통 비밀번호: P@ssw0rd!)</p>
          <ul className="grid grid-cols-1 gap-0.5 sm:grid-cols-2">
            {DEMO_ACCOUNTS.map((email) => (
              <li key={email}>{email}</li>
            ))}
          </ul>
        </motion.div>
      </motion.div>
    </main>
  );
}
