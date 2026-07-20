# processed/housta 안내

작성일: 2026-07-20  
원본: `raw/housta/` (HUG 빅데이터 개방 포털 → data.go.kr 공개파일, `scripts/collect_housta_data.py`로 수집)  
정규화: `scripts/process_housta_data.py`

| 파일 | 행 | 내용 | 활용 |
|---|---:|---|---|
| `housta_region_risk_20260720.csv` | 272 | 시군구별 사고건수·사고금액·**사고율(%)** + 법정동코드(adm_cd). '25.8월 기준 최근 3개월 평균. `is_summary=1`은 소계 행 | 안심 리포트 "지역 사고율 신호", 사고율 지도 |
| `housta_issuance_region_monthly_20260720.csv` | 6,906 | 전세보증금반환보증 시도×연월×주택유형 발급건수·보증금액 (2016.01~) | 발급 모수(정상 대조군 보완), 시계열 시각화 |
| `housta_victim_locations_20260720.csv` | 416 | 경공매지원서비스 신청자의 전세사기피해주택 시군구별 수 (2023.7~2025.3, 연도별 시트) | 피해 분포 지도 레이어 |
| `housta_annual_seoul_20260720.csv` | 8 | 서울 연도별(2020~2023) 사고/대위변제 건수·금액(억원) | 발표용 추세 근거 |
| `housta_product_accident_rate_20260720.csv` | 10 | 전세금안심대출보증 연도별 신청·사고건수 → **사고율(%)** 파생 | 상품별 사고율 추세 |

## 주의

- `region_risk`의 사고율(%)은 HUG가 공표한 값을 그대로 사용한다(자체 산식으로 재계산하지 않음). 근거 표기: "HUG 빅데이터 개방 포털, '25.8월 기준".
- `adm_cd`는 법정동코드 5자리로 도로명주소 API(admCd 앞 5자리)와 조인 가능.
- 합성데이터(발제 제공)와 달리 **실제 집계 공공데이터**이므로 발표 시 구분 표기한다.
- 수집 이력: `metadata/housta_collect_20260720.json`
