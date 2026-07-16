import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** HUG-01 채권관리 대시보드. 실제 화면 구현은 다음 단계(명세서 15장)에서 진행한다. */
export default function HugDashboardPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>채권관리 대시보드</CardTitle>
      </CardHeader>
      <CardContent>사고 접수 사건 우선순위 목록은 MSW 연동 단계에서 구현됩니다.</CardContent>
    </Card>
  );
}
