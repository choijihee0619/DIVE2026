import { AppShell } from "@/components/common/AppShell";
import { UserRole } from "@/types/enums";

export default function LandlordLayout({ children }: { children: React.ReactNode }) {
  return <AppShell allowedRoles={[UserRole.LANDLORD]}>{children}</AppShell>;
}
