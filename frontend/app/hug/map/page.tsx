"use client";

/**
 * HUG 사고율 지도 (README §19.5) — 시군구 코로플레스 + 전세사기피해주택 버블 오버레이.
 *
 * - 경계: `public/geo/sigungu.json` (VWorld LT_C_ADSIGG_INFO, scripts/build_sigungu_geojson.py 생성).
 *   각 feature의 `src_cd`가 housta `adm_cd`(2025-08 구코드) 조인 키 — 2026 행정개편(전남광주 통합·
 *   인천 재편·화성 분구) 근사 매핑 포함, 매핑 불가(제물포구)는 회색.
 * - 색: 사고율(%) 단일 붉은 계열 밝기 램프(순차형). **사고 3건 미만은 회색** — 3개월 평균이라
 *   표본이 적으면 사고율이 튀기 때문(예: 사고 1건에 100%).
 * - 버블: 피해주택 수 비례 원(시군구 대표점) — 인천 미추홀구 등 다발지 강조.
 * - echarts는 외부 타일 서버가 필요 없어(leaflet 대비) 자체 완결·CSP 안전. 작성일 2026-07-22.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { MapPinned } from "lucide-react";
import * as echarts from "echarts/core";
import { MapChart, ScatterChart } from "echarts/charts";
import { GeoComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import ReactEChartsCore from "echarts-for-react/lib/core";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { hugService } from "@/services/hugService";
import type { RegionRiskData, RegionSigunguRow, VictimsData } from "@/types/hug";
import { staggerContainer, fadeUp } from "@/lib/motion";

echarts.use([MapChart, ScatterChart, GeoComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

/** 색상 판정에 필요한 최소 사고 건수 — 미만이면 회색(표본 부족). */
const MIN_ACCIDENT_CNT = 3;

/** 순차형(단일 붉은 계열, 밝→어둡) — 사고율 크기만 인코딩한다. */
const SEQUENTIAL_RED = ["#FEE9E3", "#F9BBA8", "#F0876B", "#DE4F2E", "#A82811"];
const NO_DATA_GRAY = "#E2E5EA";

interface SigunguFeatureProps {
  sig_cd: string;
  name: string;
  full_nm: string;
  cx: number;
  cy: number;
  src_cd: string | null;
}

interface SigunguGeoJSON {
  type: "FeatureCollection";
  features: { type: "Feature"; properties: SigunguFeatureProps; geometry: unknown }[];
}

/** victim CSV의 sido_short → GeoJSON full_nm 접두 (2026 개편 명칭 기준). */
const SIDO_PREFIX: Record<string, string> = {
  서울시: "서울특별시",
  부산시: "부산광역시",
  대구시: "대구광역시",
  인천시: "인천광역시",
  광주시: "전남광주통합특별시",
  대전시: "대전광역시",
  울산시: "울산광역시",
  세종시: "세종특별자치시",
  경기: "경기도",
  강원: "강원특별자치도",
  충북: "충청북도",
  충남: "충청남도",
  전북: "전북특별자치도",
  전남: "전남광주통합특별시",
  경북: "경상북도",
  경남: "경상남도",
  제주: "제주특별자치도",
  제주시: "제주특별자치도",
};

export default function HugRiskMapPage() {
  const [geo, setGeo] = useState<SigunguGeoJSON | null>(null);
  const [regionRisk, setRegionRisk] = useState<RegionRiskData | null>(null);
  const [victims, setVictims] = useState<VictimsData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    fetch("/geo/sigungu.json")
      .then((r) => r.json())
      .then((fc: SigunguGeoJSON) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        echarts.registerMap("sigungu", fc as any);
        setGeo(fc);
      })
      .catch(() => setErrorMessage("시군구 경계 데이터를 불러오지 못했습니다."));
    hugService.regionRisk().then(setRegionRisk).catch(() => setErrorMessage("지역 사고율 데이터를 불러오지 못했습니다."));
    hugService.victims().then(setVictims).catch(() => setVictims({ items: [] }));
  }, []);

  const model = useMemo(() => {
    if (!geo || !regionRisk) return null;
    const rows = regionRisk.sigungu ?? [];
    const rowByCode = new Map<string, RegionSigunguRow>(rows.map((r) => [r.adm_cd, r]));
    const featureBySig = new Map(geo.features.map((f) => [f.properties.sig_cd, f.properties]));

    // 코로플레스: n>=3 지역만 값 배정(나머지는 회색으로 남긴다)
    const mapData: { name: string; value: number }[] = [];
    let maxRate = 0;
    for (const f of geo.features) {
      const row = f.properties.src_cd ? rowByCode.get(f.properties.src_cd) : undefined;
      if (row && row.accident_cnt >= MIN_ACCIDENT_CNT) {
        mapData.push({ name: f.properties.sig_cd, value: row.accident_rate_pct });
        maxRate = Math.max(maxRate, row.accident_rate_pct);
      }
    }

    // 버블: 피해주택 수 — (sido_short, sigungu) 이름 매칭으로 feature 대표점에 배정
    const victimByFeature = new Map<string, number>();
    let unmatched = 0;
    for (const item of victims?.items ?? []) {
      const prefix = SIDO_PREFIX[item.sido_short];
      const candidates = geo.features.filter((f) => {
        const p = f.properties;
        if (p.name === item.sigungu) return !prefix || p.full_nm.startsWith(prefix);
        // 특례시(성남시 등): sido_short가 시명, feature name은 "성남시 분당구" 형태
        return p.name === `${item.sido_short} ${item.sigungu}`.trim();
      });
      if (candidates.length === 1) {
        const cd = candidates[0].properties.sig_cd;
        victimByFeature.set(cd, (victimByFeature.get(cd) ?? 0) + item.victim_house_cnt);
      } else {
        unmatched += 1;
      }
    }
    const bubbleData = [...victimByFeature.entries()]
      .map(([sigCd, cnt]) => {
        const p = featureBySig.get(sigCd);
        return p ? { name: sigCd, value: [p.cx, p.cy, cnt] as [number, number, number] } : null;
      })
      .filter((v): v is NonNullable<typeof v> => v !== null)
      .sort((a, b) => b.value[2] - a.value[2]);

    const rateTop = rows
      .filter((r) => r.accident_cnt >= MIN_ACCIDENT_CNT)
      .sort((a, b) => b.accident_rate_pct - a.accident_rate_pct)
      .slice(0, 10);
    const victimTop = bubbleData.slice(0, 5).map((b) => ({
      label: featureBySig.get(b.name)?.full_nm ?? b.name,
      cnt: b.value[2],
    }));

    return { mapData, maxRate, bubbleData, rowByCode, featureBySig, rateTop, victimTop, unmatched };
  }, [geo, regionRisk, victims]);

  const option = useMemo(() => {
    if (!model) return null;
    const { mapData, maxRate, bubbleData, rowByCode, featureBySig } = model;
    return {
      tooltip: {
        trigger: "item",
        borderColor: "#E3E8EF",
        textStyle: { fontSize: 12 },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        formatter: (params: any) => {
          const props = featureBySig.get(params.name);
          if (!props) return params.name;
          if (params.seriesType === "scatter") {
            return `<b>${props.full_nm}</b><br/>전세사기피해주택 <b>${params.value[2].toLocaleString("ko-KR")}호</b>`;
          }
          const row = props.src_cd ? rowByCode.get(props.src_cd) : undefined;
          if (!row) return `<b>${props.full_nm}</b><br/>2026 행정구역 개편으로 통계 미대응`;
          const head = `<b>${props.full_nm}</b><br/>사고율 <b>${row.accident_rate_pct}%</b> · 사고 ${row.accident_cnt}건`;
          return row.accident_cnt < MIN_ACCIDENT_CNT
            ? `${head}<br/><span style="color:#697386">사고 ${MIN_ACCIDENT_CNT}건 미만 — 표본 부족으로 색상 제외</span>`
            : head;
        },
      },
      visualMap: {
        min: 0,
        max: Math.max(1, Math.ceil(maxRate)),
        text: [`사고율 높음`, `0%`],
        inRange: { color: SEQUENTIAL_RED },
        left: 8,
        bottom: 8,
        itemHeight: 90,
        textStyle: { fontSize: 11, color: "#697386" },
        seriesIndex: 0,
      },
      geo: {
        map: "sigungu",
        nameProperty: "sig_cd",
        roam: true,
        scaleLimit: { min: 0.8, max: 8 },
        left: 8,
        right: 8,
        top: 8,
        bottom: 8,
        itemStyle: { areaColor: NO_DATA_GRAY, borderColor: "#FFFFFF", borderWidth: 0.6 },
        emphasis: { itemStyle: { areaColor: "#C7D6E5" }, label: { show: false } },
        select: { disabled: true },
      },
      series: [
        {
          type: "map",
          map: "sigungu",
          geoIndex: 0,
          nameProperty: "sig_cd",
          data: mapData,
          // 지역명 대신 sig_cd가 노출되는 것을 방지 — 식별은 툴팁이 담당한다
          label: { show: false },
          emphasis: { label: { show: false } },
          select: { disabled: true },
        },
        {
          type: "scatter",
          coordinateSystem: "geo",
          data: bubbleData,
          symbolSize: (value: [number, number, number]) => Math.max(6, Math.min(38, Math.sqrt(value[2]) * 3.2)),
          itemStyle: {
            color: "rgba(10,92,168,0.55)",
            borderColor: "#FFFFFF",
            borderWidth: 1,
          },
          emphasis: { itemStyle: { color: "rgba(10,92,168,0.85)" } },
          z: 5,
        },
      ],
    };
  }, [model]);

  return (
    <motion.div variants={staggerContainer} initial="hidden" animate="show" className="flex flex-col gap-6">
      <motion.div variants={fadeUp}>
        <h1 className="flex items-center gap-2 text-2xl font-extrabold tracking-tight">
          <MapPinned size={22} className="text-hug-blue" />
          한반도 사고율 지도
        </h1>
        <p className="mt-1.5 text-muted-foreground">
          시군구별 전세보증 사고율(최근 3개월 평균)을 면 색으로, 전세사기피해주택 분포를 원 크기로
          표시합니다.
        </p>
      </motion.div>

      {errorMessage ? <p className="text-sm text-destructive">{errorMessage}</p> : null}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <motion.div variants={fadeUp} className="xl:col-span-2">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base font-extrabold">시군구 코로플레스</CardTitle>
              <span className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="inline-block size-3 rounded-sm" style={{ background: NO_DATA_GRAY }} />
                  사고 {MIN_ACCIDENT_CNT}건 미만·통계 미대응
                </span>
                <span className="flex items-center gap-1">
                  <span className="inline-block size-3 rounded-full bg-hug-blue/60" />
                  피해주택 수
                </span>
              </span>
            </CardHeader>
            <CardContent>
              {option ? (
                <ReactEChartsCore
                  echarts={echarts}
                  option={option}
                  notMerge
                  style={{ height: 560, width: "100%" }}
                />
              ) : (
                <Skeleton className="h-[560px] w-full rounded-xl" />
              )}
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                {regionRisk?.basis ?? "보증사고 '25.8월 최근 3개월 평균"} · 피해주택은 경공매지원서비스
                신청 실집계. 3개월 평균 특성상 사고 {MIN_ACCIDENT_CNT}건 미만 지역은 사고율이 크게 튀어
                회색으로 제외했습니다(예: 사고 1건에 100%).
                {model && model.unmatched > 0
                  ? ` 피해주택 ${model.unmatched}건은 행정구역 개편·표기 불일치로 지도 매칭에서 제외.`
                  : ""}
              </p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp} className="flex flex-col gap-5">
          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">
                사고율 상위 시군구
                <span className="ml-2 text-xs font-semibold text-muted-foreground">
                  사고 {MIN_ACCIDENT_CNT}건 이상
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {model ? (
                <ol className="flex flex-col gap-1.5">
                  {model.rateTop.map((row, index) => (
                    <li key={row.adm_cd} className="flex items-center gap-2.5 text-sm">
                      <span className="w-5 shrink-0 text-right font-bold text-muted-foreground tnum">
                        {index + 1}
                      </span>
                      <span className="min-w-0 flex-1 truncate font-semibold">
                        {row.sido} {row.sigungu}
                      </span>
                      <div className="h-2 w-24 shrink-0 overflow-hidden rounded-full bg-neutral-100">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${Math.min(100, (row.accident_rate_pct / model.rateTop[0].accident_rate_pct) * 100)}%`,
                            background: SEQUENTIAL_RED[3],
                          }}
                        />
                      </div>
                      <b className="w-12 shrink-0 text-right tnum">{row.accident_rate_pct}%</b>
                    </li>
                  ))}
                </ol>
              ) : (
                <Skeleton className="h-56 w-full" />
              )}
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-line shadow-card">
            <CardHeader>
              <CardTitle className="text-base font-extrabold">피해주택 다발 지역 TOP 5</CardTitle>
            </CardHeader>
            <CardContent>
              {model ? (
                model.victimTop.length === 0 ? (
                  <p className="text-sm text-muted-foreground">피해주택 데이터가 없습니다.</p>
                ) : (
                  <ol className="flex flex-col gap-1.5">
                    {model.victimTop.map((item, index) => (
                      <li key={item.label} className="flex items-center gap-2.5 text-sm">
                        <span className="w-5 shrink-0 text-right font-bold text-muted-foreground tnum">
                          {index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate font-semibold">{item.label}</span>
                        <b className="shrink-0 tnum">{item.cnt.toLocaleString("ko-KR")}호</b>
                      </li>
                    ))}
                  </ol>
                )
              ) : (
                <Skeleton className="h-32 w-full" />
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  );
}
