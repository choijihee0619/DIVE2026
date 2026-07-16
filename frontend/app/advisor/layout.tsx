import { AppShell } from "@/components/common/AppShell";
import { UserRole } from "@/types/enums";

export default function AdvisorLayout({ children }: { children: React.ReactNode }) {
  return <AppShell allowedRoles={[UserRole.ADVISOR, UserRole.VERIFIER]}>{children}</AppShell>;
}
