"use client";

/**
 * 매물 등기부 열람 카드 — GET /properties 목록에서 매물별 등기부 열람 페이지로 이동한다.
 * 계약 목록 API 권한이 없는 역할(아이엔상담사)과 임대인 홈에서 공용으로 사용. 작성일 2026-07-21.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { ScrollText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { propertyService } from "@/services/propertyService";
import type { Property } from "@/types/property";

export function RegistryAccessCard() {
  const [properties, setProperties] = useState<Property[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    propertyService
      .list()
      .then((data) => setProperties(data.items))
      .catch(() => setFailed(true));
  }, []);

  return (
    <Card className="rounded-2xl border-line shadow-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-extrabold">
          <ScrollText size={16} className="text-hug-blue" />
          매물 등기부 열람
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          계약 매물의 실제 등기부(표제부·갑구·을구)를 확인합니다. 집합건물은 동·호수 입력 후 조회됩니다.
        </p>
      </CardHeader>
      <CardContent>
        {failed ? (
          <p className="py-4 text-center text-sm text-destructive">매물 목록을 불러오지 못했습니다.</p>
        ) : properties === null ? (
          <Skeleton className="h-20 w-full" />
        ) : properties.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">등록된 매물이 없습니다.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {properties
              .filter((property) => property.address.road_address)
              .map((property) => (
                <li key={property.property_id}>
                  <Link
                    href={`/registry/${property.property_id}`}
                    className="flex items-center gap-3 rounded-xl border border-line p-3 text-sm transition-colors hover:bg-hug-sky/50"
                  >
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-hug-sky text-hug-blue">
                      <ScrollText size={14} />
                    </span>
                    <span className="min-w-0 flex-1 truncate font-semibold">
                      {property.address.road_address}
                      {property.address.dong ? ` ${property.address.dong}동` : ""}
                      {property.address.ho ? ` ${property.address.ho}호` : ""}
                    </span>
                    <span className="shrink-0 text-xs font-bold text-hug-blue">등기부 보기 →</span>
                  </Link>
                </li>
              ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
