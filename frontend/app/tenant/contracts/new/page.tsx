"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { contractService } from "@/services/contractService";
import { propertyService } from "@/services/propertyService";
import { ApiError } from "@/services/apiClient";
import type { Property } from "@/types/property";
import { HOUSING_TYPE_LABEL, LANDLORD_TYPE_LABEL } from "@/lib/domain-labels";

const selectClass =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

/** TEN-02 계약 등록: GET /properties 매물 선택 + POST /contracts. */
export default function ContractNewPage() {
  const router = useRouter();

  const [properties, setProperties] = useState<Property[] | null>(null);
  const [propertyId, setPropertyId] = useState("");
  const [deposit, setDeposit] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [landlordType, setLandlordType] = useState("INDIVIDUAL");
  const [housingType, setHousingType] = useState("MULTI_HOUSEHOLD");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    propertyService
      .list()
      .then((data) => {
        setProperties(data.items);
        if (data.items.length > 0) setPropertyId(data.items[0].property_id);
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "매물 목록을 불러오지 못했습니다."),
      );
  }, []);

  const canSubmit =
    propertyId && Number(deposit) > 0 && startDate && endDate && startDate < endDate && !isSubmitting;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    contractService
      .create({
        property_id: propertyId,
        deposit: Number(deposit),
        contract_start_date: startDate,
        contract_end_date: endDate,
        landlord_type: landlordType,
        housing_type: housingType,
      })
      .then((contract) => router.push(`/tenant/contracts/${contract.contract_id}`))
      .catch((error: unknown) => {
        setErrorMessage(error instanceof ApiError ? error.message : "계약 등록에 실패했습니다.");
        setIsSubmitting(false);
      });
  };

  return (
    <Card className="max-w-2xl">
      <CardHeader>
        <CardTitle>계약 등록</CardTitle>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-4" onSubmit={submit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="property">매물</Label>
            <select
              id="property"
              value={propertyId}
              onChange={(event) => setPropertyId(event.target.value)}
              className={selectClass}
              disabled={properties === null}
            >
              {(properties ?? []).map((property) => (
                <option key={property.property_id} value={property.property_id}>
                  {property.address.road_address ?? property.property_id}
                  {property.address.dong ? ` ${property.address.dong}동` : ""}
                  {property.address.ho ? ` ${property.address.ho}호` : ""}
                </option>
              ))}
            </select>
            {properties !== null && properties.length === 0 ? (
              <p className="text-xs text-destructive">등록된 매물이 없습니다.</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="deposit">보증금 (원)</Label>
            <Input
              id="deposit"
              type="number"
              min={1}
              value={deposit}
              onChange={(event) => setDeposit(event.target.value)}
              placeholder="예: 300000000"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="start-date">계약 시작일</Label>
              <Input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="end-date">계약 종료일</Label>
              <Input id="end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="landlord-type">임대인 유형</Label>
              <select
                id="landlord-type"
                value={landlordType}
                onChange={(event) => setLandlordType(event.target.value)}
                className={selectClass}
              >
                {Object.entries(LANDLORD_TYPE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="housing-type">주택 유형</Label>
              <select
                id="housing-type"
                value={housingType}
                onChange={(event) => setHousingType(event.target.value)}
                className={selectClass}
              >
                {Object.entries(HOUSING_TYPE_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}
          <div>
            <Button type="submit" disabled={!canSubmit}>
              {isSubmitting ? "등록 중..." : "계약 등록"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
