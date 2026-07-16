"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { LoadingSpinner } from "@/components/common/LoadingSpinner";
import { authService } from "@/services/authService";
import { ApiError } from "@/services/apiClient";
import { useSessionStore } from "@/stores/useSessionStore";
import { ROLE_HOME_ROUTE } from "@/types/enums";

const loginSchema = z.object({
  email: z.string().min(1, "이메일을 입력하세요.").email("올바른 이메일 형식이 아닙니다."),
  password: z.string().min(1, "비밀번호를 입력하세요."),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const DEMO_ACCOUNTS = [
  "tenant01@example.com",
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

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
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

  return (
    <main className="flex min-h-svh items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-xl">HUG 안심전세 체인</CardTitle>
          <CardDescription>계정으로 로그인해 역할별 화면으로 이동합니다.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <FieldGroup>
              <Field data-invalid={Boolean(errors.email)}>
                <FieldLabel htmlFor="email">이메일</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={errors.email ? "email-error" : undefined}
                  {...register("email")}
                />
                <FieldError id="email-error" errors={errors.email ? [errors.email] : undefined} />
              </Field>
              <Field data-invalid={Boolean(errors.password)}>
                <FieldLabel htmlFor="password">비밀번호</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={errors.password ? "password-error" : undefined}
                  {...register("password")}
                />
                <FieldError id="password-error" errors={errors.password ? [errors.password] : undefined} />
              </Field>
              <Button type="submit" disabled={submitting} className="w-full">
                {submitting ? <LoadingSpinner size={16} label="로그인 중..." /> : "로그인"}
              </Button>
            </FieldGroup>
          </form>
          <div className="mt-4 rounded-md bg-muted p-3 text-xs text-muted-foreground">
            <p className="mb-1 font-medium text-foreground">데모 계정 (공통 비밀번호: P@ssw0rd!)</p>
            <ul className="space-y-0.5">
              {DEMO_ACCOUNTS.map((email) => (
                <li key={email}>{email}</li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
