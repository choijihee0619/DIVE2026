import { AppShell } from "@/components/common/AppShell";
import { UserRole } from "@/types/enums";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AppShell allowedRoles={[UserRole.SYSTEM_ADMIN]}>{children}</AppShell>;
}
