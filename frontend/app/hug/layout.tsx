import { AppShell } from "@/components/common/AppShell";
import { UserRole } from "@/types/enums";

export default function HugLayout({ children }: { children: React.ReactNode }) {
  return <AppShell allowedRoles={[UserRole.HUG_ADMIN]}>{children}</AppShell>;
}
