import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** ADV-00 상담 큐. 실제 화면 구현은 다음 단계(명세서 15장)에서 진행한다. */
export default function AdvisorQueuePage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>상담 큐</CardTitle>
      </CardHeader>
      <CardContent>신규 상담/이관 대상 목록은 MSW 연동 단계에서 구현됩니다.</CardContent>
    </Card>
  );
}
