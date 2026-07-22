"use client";

/**
 * COMMON 등기부 열람 화면 — GET /properties/{id}/registry/latest 실데이터.
 *
 * 임차인·임대인·아이엔상담사·HUG 관리자 모두 계약 매물의 실제 등기부(표제부/갑구/을구)를
 * 확인할 수 있는 공용 페이지. 동·호수를 입력해 CODEF 재조회(refresh)도 가능하다.
 * 작성일 2026-07-21.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { RefreshCcw, ScrollText, ShieldAlert, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { RoleGuard } from "@/components/common/RoleGuard";
import { Header } from "@/components/common/Header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { propertyService } from "@/services/propertyService";
import { ApiError } from "@/services/apiClient";
import type { Property, RegistrySnapshot } from "@/types/property";
import { UserRole } from "@/types/enums";
import { formatDeposit } from "@/lib/contract-labels";
import { staggerContainer, fadeUp } from "@/lib/motion";
import { Term } from "@/components/common/Term";
import { cn } from "@/lib/utils";

const ALL_ROLES = Object.values(UserRole);

const PROVIDER_LABEL: Record<string, string> = {
  codef_sandbox: "CODEF 샌드박스",
  codef_demo: "CODEF 데모",
  codef_prod: "CODEF 운영",
};

const DEMO_SCENARIO_LABEL: Record<string, string> = {
  normal: "정상 (권리관계 양호)",
  mortgage: "근저당 설정",
  complex_rights: "복합 권리부담",
  seizure: "압류·가압류",
};

function publishDateLabel(raw?: string) {
  if (!raw || raw.length !== 8) return raw ?? "-";
  return `${raw.slice(0, 4)}-${raw.slice(4, 6)}-${raw.slice(6, 8)}`;
}

export default function RegistryViewerPage() {
  const { propertyId } = useParams<{ propertyId: string }>();

  const [property, setProperty] = useState<Property | null>(null);
  const [snapshot, setSnapshot] = useState<RegistrySnapshot | null>(null);
  const [noSnapshot, setNoSnapshot] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [dong, setDong] = useState("");
  const [ho, setHo] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const load = useCallback(() => {
    propertyService
      .get(propertyId)
      .then((p) => {
        setProperty(p);
        setDong((prev) => prev || String(p.address.dong ?? ""));
        setHo((prev) => prev || String(p.address.ho ?? ""));
      })
      .catch((error: unknown) =>
        setErrorMessage(error instanceof ApiError ? error.message : "매물 정보를 불러오지 못했습니다."),
      );
    propertyService
      .latestRegistry(propertyId)
      .then((s) => {
        setSnapshot(s);
        setNoSnapshot(false);
      })
      .catch(() => setNoSnapshot(true));
  }, [propertyId]);

  useEffect(() => {
    load();
  }, [load]);

  const refresh = (event?: React.FormEvent) => {
    event?.preventDefault();
    if (isRefreshing) return;
    setIsRefreshing(true);
    propertyService
      .refreshRegistry(propertyId, { dong, ho })
      .then((s) => {
        setSnapshot(s);
        setNoSnapshot(false);
        if (s.source_system === "api_live") {
          toast.success("등기부를 조회했습니다.");
        } else if (s.source_system === "demo_scenario") {
          toast.info("샌드박스는 주소 무관 고정표본이라, 매물 주소별 데모 시나리오로 표시합니다.");
        } else {
          toast.warning("등기부 실조회에 실패해 Mock 데이터로 대체되었습니다.");
        }
      })
      .catch((error: unknown) =>
        toast.error(error instanceof ApiError ? error.message : "등기부 조회에 실패했습니다."),
      )
      .finally(() => setIsRefreshing(false));
  };

  const isLive = snapshot?.source_system === "api_live";
  const isDemo = snapshot?.source_system === "demo_scenario";
  const detail = snapshot?.register_detail ?? null;
  const features = snapshot?.features ?? {};
  const roadAddress = property?.address.road_address ?? "";

  const refreshForm = (
    <form className="flex flex-wrap items-end gap-3" onSubmit={refresh}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="registry-dong">동</Label>
        <Input
          id="registry-dong"
          value={dong}
          onChange={(event) => setDong(event.target.value)}
          placeholder="예: 801"
          className="w-28"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="registry-ho">호수</Label>
        <Input
          id="registry-ho"
          value={ho}
          onChange={(event) => setHo(event.target.value)}
          placeholder="예: 804"
          className="w-28"
        />
      </div>
      <Button type="submit" disabled={isRefreshing} className="rounded-full">
        <RefreshCcw size={14} className={isRefreshing ? "animate-spin" : ""} />
        {isRefreshing ? "조회 중..." : snapshot ? "등기부 재조회" : "등기부 조회"}
      </Button>
      <span className="text-xs text-muted-foreground">
        집합건물(아파트·오피스텔 등)은 동·호수까지 입력해야 해당 세대의 등기부가 특정됩니다.
      </span>
    </form>
  );

  return (
    <RoleGuard allowedRoles={ALL_ROLES}>
      <div className="flex min-h-svh flex-col">
        <Header />
        <main className="mx-auto w-full max-w-5xl flex-1 px-6 pb-12 pt-2">
          <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
            <motion.div variants={fadeUp}>
              <p className="text-sm font-semibold text-muted-foreground">등기부 열람</p>
              <h1 className="mt-1 flex flex-wrap items-center gap-2 text-2xl font-extrabold tracking-tight">
                <ScrollText size={22} className="text-hug-blue" />
                {detail?.doc_title || "등기사항전부증명서"}
                {snapshot ? (
                  isLive ? (
                    <Badge variant="secondary">
                      실조회 · {PROVIDER_LABEL[snapshot.provider ?? ""] ?? snapshot.provider}
                    </Badge>
                  ) : isDemo ? (
                    <Badge variant="secondary">
                      데모 시나리오 · 주소별
                      {snapshot.demo_scenario
                        ? ` (${DEMO_SCENARIO_LABEL[snapshot.demo_scenario] ?? snapshot.demo_scenario})`
                        : ""}
                    </Badge>
                  ) : (
                    <Badge variant="outline">Mock 폴백</Badge>
                  )
                ) : null}
              </h1>
              <p className="mt-1.5 text-muted-foreground">
                {roadAddress
                  ? `${roadAddress}${dong ? ` ${dong}동` : ""}${ho ? ` ${ho}호` : ""}`
                  : "매물 정보를 불러오는 중입니다."}
              </p>
            </motion.div>

            {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

            <motion.div variants={fadeUp}>
              <Card className="rounded-2xl border-line shadow-card">
                <CardHeader>
                  <CardTitle className="text-base font-extrabold">등기부 조회</CardTitle>
                </CardHeader>
                <CardContent>{refreshForm}</CardContent>
              </Card>
            </motion.div>

            {snapshot === null && !noSnapshot ? (
              <Skeleton className="h-48 w-full rounded-2xl" />
            ) : null}

            {noSnapshot && snapshot === null ? (
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardContent className="flex items-center gap-3 py-8">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-hug-sky text-hug-blue">
                      <ScrollText size={18} />
                    </span>
                    <p className="text-sm text-muted-foreground">
                      아직 조회된 등기부가 없습니다. 위의 동·호수를 확인한 뒤 &lsquo;등기부 조회&rsquo;를 실행해 주세요.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            ) : null}

            {snapshot && isDemo ? (
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-hug-sky bg-hug-sky/30 shadow-card">
                  <CardContent className="flex items-start gap-3 py-4">
                    <ShieldAlert size={18} className="mt-0.5 shrink-0 text-hug-blue" />
                    <div className="text-sm text-hug-navy">
                      <p className="font-bold">주소별 데모 시나리오입니다 (실제 권리관계 아님).</p>
                      <p className="mt-0.5">
                        {snapshot.demo_notice ??
                          "CODEF 샌드박스는 주소와 무관하게 고정 표본을 반환하므로, 매물 주소로 배정한 데모 시나리오를 표시합니다."}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ) : null}

            {snapshot && !isLive && !isDemo ? (
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-warning-200 bg-warning-100/50 shadow-card">
                  <CardContent className="flex items-start gap-3 py-4">
                    <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warning-700" />
                    <div className="text-sm text-warning-700">
                      <p className="font-bold">실제 등기부가 아닌 Mock 데이터입니다.</p>
                      <p className="mt-0.5">
                        등기부 실조회에 실패해 데모용 데이터로 대체되었습니다. 재조회를 시도해 주세요.
                        {snapshot.fallback_reason ? ` (사유: ${snapshot.fallback_reason})` : ""}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ) : null}

            {snapshot ? (
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-base font-extrabold">권리관계 요약</CardTitle>
                    <span className="text-xs text-muted-foreground tnum">
                      조회 시각 {snapshot.created_at.slice(0, 16).replace("T", " ")}
                    </span>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <div className="flex flex-wrap gap-2">
                      {features.has_seizure === true ? (
                        <span className="flex items-center gap-1.5 rounded-full bg-danger-100 px-3 py-1 text-xs font-bold text-danger-600">
                          <ShieldAlert size={13} />
                          <Term k="seizure">압류·가압류</Term> {features.seizure_rows_active ?? 0}건 (유효)
                        </span>
                      ) : features.has_seizure === false ? (
                        <span className="flex items-center gap-1.5 rounded-full bg-hug-mint px-3 py-1 text-xs font-bold text-hug-green-deep">
                          <ShieldCheck size={13} />
                          <Term k="seizure">압류·가압류</Term> 없음
                        </span>
                      ) : null}
                      {typeof features.mortgage_count === "number" ? (
                        <span
                          className={cn(
                            "rounded-full px-3 py-1 text-xs font-bold",
                            features.mortgage_count > 0
                              ? "bg-warning-100 text-warning-700"
                              : "bg-hug-mint text-hug-green-deep",
                          )}
                        >
                          <Term k="mortgage">근저당</Term> {features.mortgage_count}건
                          {typeof features.mortgage_max_total_won === "number" && features.mortgage_max_total_won > 0
                            ? ` · 채권최고액 합계 ${formatDeposit(features.mortgage_max_total_won)}`
                            : ""}
                        </span>
                      ) : null}
                      {Object.entries(features.rights_keywords ?? {}).map(([keyword, count]) => (
                        <span
                          key={keyword}
                          className="rounded-full bg-hug-sky px-3 py-1 text-xs font-bold text-hug-blue tnum"
                        >
                          {keyword} {count}
                        </span>
                      ))}
                    </div>
                    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
                      {[
                        ["부동산 표시", detail?.realty || "-"],
                        ["열람 기준일", publishDateLabel(detail?.publish_date || String(features.publish_date ?? ""))],
                        ["관할 등기소", detail?.competent_office || detail?.publish_office || "-"],
                        ["조회 주소", snapshot.query_address ?? "-"],
                      ].map(([label, value]) => (
                        <div key={label} className="flex flex-col gap-0.5">
                          <dt className="text-xs text-muted-foreground">{label}</dt>
                          <dd className="break-all font-semibold">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </CardContent>
                </Card>
              </motion.div>
            ) : null}

            {detail?.sections.map((section, index) => (
              <motion.div variants={fadeUp} key={`${section.section}-${section.title}-${index}`}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base font-extrabold">
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-0.5 text-xs font-bold",
                          section.section === "갑구"
                            ? "bg-hug-sky text-hug-blue"
                            : section.section === "을구"
                              ? "bg-warning-100 text-warning-700"
                              : "bg-neutral-100 text-neutral-600",
                        )}
                      >
                        {section.section}
                      </span>
                      {section.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {section.headers.map((header, headerIndex) => (
                            <TableHead key={`${header}-${headerIndex}`} className="whitespace-nowrap">
                              {header}
                            </TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {section.rows.map((row, rowIndex) => (
                          <TableRow
                            key={rowIndex}
                            className={row.canceled ? "text-muted-foreground/70" : undefined}
                          >
                            {row.cells.map((cell, cellIndex) => (
                              <TableCell
                                key={cellIndex}
                                className={cn(
                                  "min-w-24 whitespace-pre-line align-top text-xs leading-relaxed",
                                  row.canceled && "line-through decoration-danger-500/40",
                                )}
                              >
                                {cell}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                    {section.rows.some((row) => row.canceled) ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        취소선 표시는 말소된 기재사항입니다.
                      </p>
                    ) : null}
                  </CardContent>
                </Card>
              </motion.div>
            ))}

            {snapshot && isLive && !detail ? (
              <motion.div variants={fadeUp}>
                <Card className="rounded-2xl border-line shadow-card">
                  <CardContent className="py-6 text-sm text-muted-foreground">
                    이 스냅샷에는 등기부 원문이 저장되어 있지 않습니다. &lsquo;등기부 재조회&rsquo;를 실행하면 원문이
                    포함된 최신 등기부를 확인할 수 있습니다.
                  </CardContent>
                </Card>
              </motion.div>
            ) : null}
          </motion.div>
        </main>
      </div>
    </RoleGuard>
  );
}
