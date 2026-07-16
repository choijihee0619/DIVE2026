import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** TEN-00 임차인 홈. 실제 화면 구현은 다음 단계(명세서 15장)에서 진행한다. */
export default function TenantHomePage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>임차인 홈</CardTitle>
      </CardHeader>
      <CardContent>진행 계약, 위험등급, 알림은 다음 단계에서 연동됩니다.</CardContent>
    </Card>
  );
}
