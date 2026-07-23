# 사고위험 PU Learning PoC — 2026-07-23

## 결론

발제사 조언에 따라 RTMS 전세 실거래를 확정 정상으로 두지 않고 **미라벨(U)** 로 처리했다.
실제 사고목록과 RTMS를 계약 단위로 제외 조인할 공통키가 없으므로, 기존 case-control은
비교 baseline으로만 유지하고 LightGBM bagging PU를 주 PoC로 사용한다.

출력은 검증된 개별 사고확률이 아니다. PoC 기본 출력은 `pu_risk_score`와 포트폴리오
`risk_percentile`이며, `prior_aligned_estimate`는 HOUSTA 집계 사고율에 평균을 맞춘
`aggregate_prior_aligned_unvalidated` 추정치다.

## 표본

| 구분 | 건수 |
|---|---:|
| 알려진 사고 P | 18,054 |
| RTMS 미라벨 U | 18,765 |
| 공통 시도 | 8 |
| bag 수 | 10 |

### P 원천별 실제 모델 포함 건수

| 원천 | 건수 |
|---|---:|
| 임대보증_사고현황_합성 | 18,054 |

P와 U를 합친 뒤 동일 feature vector가 train/calibration/test 사이에 중복되지 않도록
전역 그룹 분할했다(global overlap=0).
P split={'train': 12501, 'calibration': 2729, 'test': 2824, 'group_overlap_count': 0}, U split={'train': 13194, 'calibration': 2547, 'test': 3024, 'group_overlap_count': 0}.

## Proxy 진단

확정 정상 라벨이 없으므로 아래 ROC/PR은 실제 사고예측 성능이 아니라 **P와 U의 분리도**다.
Brier·정확도·ECE는 계산하지 않았다.

| 지표 | 값 |
|---|---:|
| P-vs-U proxy ROC-AUC | 0.9108 |
| P-vs-U proxy PR-AUC | 0.9025 |
| U 상위 10% 기준 P recall | 0.7167 |
| U 상위 10% 기준 proxy lift | 6.63 |
| U 상위 20% 기준 P recall | 0.7975 |
| 평균 bag score 표준편차 | 0.026175 |
| bag 평균 상관 | 0.989423 |
| Elkan–Noto 1 초과 clip 비율 | 0.3376 |
| c 평균 ± 표준편차 | 0.733427 ± 0.00429 |

높은 proxy AUC는 합성 P와 RTMS U의 데이터 출처 차이를 포함하므로 기존 case-control
0.921보다 좋아졌다는 의미가 아니다.

## 집계 prior 정렬

| 항목 | 값 |
|---|---|
| 참조 prior | 1.6000% |
| 출처 | housta_region_risk_20260720.csv |
| 출처 SHA-256 | 122ff25feb83cfa6c642e5475bd967543b7d1b1e9ceee2e2473d836ac0c61ae8 |
| 근거 | 보증사고 '25.8월 최근3개월 평균 |
| calibration U 평균 | 1.6000% |
| 독립 test U 평균 | 1.8563% |
| test 정렬 오차 | 0.2563% |
| 상태 | `aggregate_prior_aligned_unvalidated` |

## 산출물

- 모델: `accident_clf_pu_poc_260723.joblib`
- 모델 SHA-256: `dbcae7bdad1228819dbb8c267941ba5719e66008926dc2abf15362af3f8d9537`
- 지표: `accident_clf_pu_poc_metrics_260723.json`
- 재현성: seed=42, bag=10

## 한계

- P는 합성 사고군이며 임의 표집(SCAR) 가정을 충족한다고 검증되지 않았다.
- U는 HUG 보증가입 모집단이 아닌 RTMS 전체 전세실거래로 실제 사고가 일부 포함될 수 있다.
- P와 U의 지역·주택유형·보증금 분포가 달라 모델이 사고위험과 데이터 출처 차이를 함께 학습할 수 있다.
- P의 기준연도는 보증종료연도, U는 거래연도라 현 데이터로 시간순 외부검증을 할 수 없다.
- 원본 P 95,122건 중 공통 지역 support에 남은 18,054건만 학습했으며, 세종에 집중된 전세가율 사고원천 69,435건은 U에 세종 표본이 없어 전량 제외됐다.
- RTMS 기존 파일은 일부 시군구·월의 첫 페이지 중심 표본이라 전국 대표성이 없다.
- HOUSTA 1.6%는 공개 집계 기준의 참조 prior이며 RTMS 개별계약의 동일 코호트 사고율이 아니다.
- 확정 정상 라벨이 없어 proxy ROC/PR을 실제 HUG 성능으로 해석할 수 없다.

## 운영 승격 조건

1. HUG 보증계약키·사고 여부·관찰종료일이 연결된 성숙 코호트를 확보한다.
2. 실제 정상 종료계약으로 시간순·임대인/물건 그룹 외부검증을 수행한다.
3. 실제 모집단 class prior를 다시 추정하고 Platt/isotonic calibration을 비교한다.
4. Brier·ECE·PR-AUC와 검토용량별 recall/precision을 검증한 뒤 API/UI에 연결한다.
