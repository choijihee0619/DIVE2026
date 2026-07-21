"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Calculator } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { mlService } from "@/services/mlService";
import { ApiError } from "@/services/apiClient";
import { ML_CLAIM_TYPES, ML_PRODUCTS, type RecoveryPredictResult } from "@/types/ml";
import { AnimatedNumber } from "@/components/viz/AnimatedNumber";
import { ShapBars } from "@/components/viz/ShapBars";
import { cn } from "@/lib/utils";

const inputClass =
  "h-10 w-full rounded-xl border border-line bg-card px-3.5 text-sm outline-none tnum placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40";

const GRADE_PILL: Record<string, string> = {
  HIGH: "bg-hug-mint text-hug-green-deep",
  MED: "bg-warning-100 text-warning-700",
  LOW: "bg-danger-100 text-danger-600",
};

/** 신규 채권 조건을 입력하면 /ml/recovery/predict로 회수율·소요일·스코어와 SHAP 요인을 실계산하는 카드. */
export function RecoveryPredictCard() {
  const [productName, setProductName] = useState<string>(ML_PRODUCTS[0]);
  const [claimType, setClaimType] = useState<string>(ML_CLAIM_TYPES[1]);
  const [claimedAmount, setClaimedAmount] = useState("450000000");
  const [incurredAmount, setIncurredAmount] = useState("450000000");
  const [auctionDate, setAuctionDate] = useState("2025-11-01");
  const [incurredDate, setIncurredDate] = useState("2025-03-01");
  const [result, setResult] = useState<RecoveryPredictResult | null>(null);
  const [isPredicting, setIsPredicting] = useState(false);

  const predict = (event: React.FormEvent) => {
    event.preventDefault();
    if (isPredicting) return;
    setIsPredicting(true);
    mlService
      .recoveryPredict({
        product_name: productName,
        claim_type: claimType,
        claimed_amount: Number(claimedAmount) || 0,
        incurred_amount: Number(incurredAmount) || 0,
        auction_filed_date: auctionDate,
        incurred_date: incurredDate,
      })
      .then(setResult)
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "예측에 실패했습니다."),
      )
      .finally(() => setIsPredicting(false));
  };

  return (
    <Card className="rounded-2xl border-line shadow-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base font-extrabold">
          <Calculator size={16} className="text-hug-blue" />
          신규 채권 회수 예측
          <span className="rounded-full bg-hug-sky px-2.5 py-0.5 text-xs font-bold text-hug-blue">
            LightGBM + SHAP 실계산
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <form className="flex flex-col gap-3" onSubmit={predict}>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-product">상품</Label>
              <select id="pred-product" value={productName} onChange={(e) => setProductName(e.target.value)} className={inputClass}>
                {ML_PRODUCTS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-claim">채권구분</Label>
              <select id="pred-claim" value={claimType} onChange={(e) => setClaimType(e.target.value)} className={inputClass}>
                {ML_CLAIM_TYPES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-claimed">청구금액 (원)</Label>
              <input id="pred-claimed" type="number" min={0} value={claimedAmount} onChange={(e) => setClaimedAmount(e.target.value)} className={inputClass} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-incurred">발생금액 (원)</Label>
              <input id="pred-incurred" type="number" min={0} value={incurredAmount} onChange={(e) => setIncurredAmount(e.target.value)} className={inputClass} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-auction">경공매 신청일</Label>
              <input id="pred-auction" type="date" value={auctionDate} onChange={(e) => setAuctionDate(e.target.value)} className={inputClass} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pred-incdate">채권 발생일</Label>
              <input id="pred-incdate" type="date" value={incurredDate} onChange={(e) => setIncurredDate(e.target.value)} className={inputClass} />
            </div>
          </div>
          <Button type="submit" disabled={isPredicting} className="mt-1 rounded-xl font-bold">
            {isPredicting ? "예측 중..." : "회수 예측 실행"}
          </Button>
        </form>

        <div>
          {result ? (
            <motion.div
              key={result.priority_score + result.pred_recovery_ratio}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="flex h-full flex-col gap-3"
            >
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-xl bg-neutral-100 p-3">
                  <p className="text-[11px] font-semibold text-muted-foreground">예상 회수율</p>
                  <p className="text-xl font-extrabold tnum">
                    <AnimatedNumber value={result.pred_recovery_ratio * 100} decimals={1} durationSec={0.7} />%
                  </p>
                  <span className={cn("mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold", GRADE_PILL[result.pred_recovery_grade])}>
                    {result.pred_recovery_grade}
                  </span>
                </div>
                <div className="rounded-xl bg-neutral-100 p-3">
                  <p className="text-[11px] font-semibold text-muted-foreground">예상 소요일</p>
                  <p className="text-xl font-extrabold tnum">
                    <AnimatedNumber value={result.pred_days_to_dividend} durationSec={0.7} />일
                  </p>
                </div>
                <div className="rounded-xl bg-neutral-100 p-3">
                  <p className="text-[11px] font-semibold text-muted-foreground">우선순위 스코어</p>
                  <p className="text-xl font-extrabold text-hug-blue tnum">
                    <AnimatedNumber value={result.priority_score} decimals={1} durationSec={0.7} />
                  </p>
                </div>
              </div>
              <p className="text-xs text-muted-foreground tnum">
                예상 회수액 <b>{(result.expected_recovery_won / 1e8).toFixed(1)}억 원</b> · 포트폴리오{" "}
                {result.portfolio_size.toLocaleString("ko-KR")}건 대비 상위 스코어
              </p>
              <ShapBars
                factors={result.top_factors.map((factor) => ({
                  label: `${factor.label}=${factor.value}`,
                  value: factor.shap,
                }))}
              />
              <p className="mt-auto text-[11px] text-muted-foreground">{result.basis}</p>
            </motion.div>
          ) : (
            <div className="flex h-full min-h-40 items-center justify-center rounded-xl border border-dashed border-line text-sm text-muted-foreground">
              조건을 입력하고 &ldquo;회수 예측 실행&rdquo;을 누르면 결과와 SHAP 요인이 표시됩니다.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
