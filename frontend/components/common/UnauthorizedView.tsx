import Link from "next/link";
import { ShieldAlert } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function UnauthorizedView() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <ShieldAlert size={40} className="text-danger-500" aria-hidden="true" />
      <h1 className="text-xl font-semibold">접근 권한이 없습니다</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        이 화면은 현재 계정의 역할로 접근할 수 없습니다. 다른 계정으로 로그인하거나 홈으로 돌아가세요.
      </p>
      <Link href="/" className={cn(buttonVariants({ variant: "default" }))}>
        홈으로 돌아가기
      </Link>
    </main>
  );
}
