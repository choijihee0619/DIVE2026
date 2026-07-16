import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** ADM-00 사용자·권한 관리. 실제 화면 구현은 다음 단계(명세서 15장)에서 진행한다. */
export default function AdminUsersPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>사용자·권한 관리</CardTitle>
      </CardHeader>
      <CardContent>사용자 테이블은 MSW 연동 단계에서 구현됩니다.</CardContent>
    </Card>
  );
}
