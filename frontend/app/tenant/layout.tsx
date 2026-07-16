import { AppShell } from "@/components/common/AppShell";
import { UserRole } from "@/types/enums";

export default function TenantLayout({ children }: { children: React.ReactNode }) {
  return <AppShell allowedRoles={[UserRole.TENANT]}>{children}</AppShell>;
}
