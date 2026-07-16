# processed/ml 관련 안내

이번 데이터 수집·전처리 단계에서는 `interim/`까지 컬럼 표준화(snake_case·ISO 날짜·원 단위 int·0~1 비율)를 완료했다.

`processed/ml/`에 정식 학습용 Feature 테이블(`processed_risk_features_v1.parquet` 등, 가이드 9장)은 아직 만들지 않았다. 이유:

- RiskClassification의 핵심 Feature(`jeonse_ratio`, `mortgage_ratio`, `rights_burden_ratio`, `has_seizure`)는 등기부(CODEF)·실거래가·공시가격을 케이스 단위로 결합해야 계산 가능한데, 현재 발제사 제공 데이터에는 등기부/실거래가가 없고 사고 발생 이후의 결과 데이터(대위변제·경매·배당)만 있다.
- 제공된 7개 HUG/경매/배당 CSV에는 케이스를 서로 연결할 공통 식별자(사고ID 등)가 없어 파일 간 조인이 불가능하다(`metadata/column_inventory_260714.md` 참고).

따라서 `interim/hug/`, `interim/auction/`, `interim/dividend/`의 8개 parquet 파일이 이번 단계의 산출물이며, ML 개발자는 Colab `01_EDA.ipynb`에서 이 interim 파일들을 직접 불러와 EDA부터 시작하면 된다. RecoveryPrediction(대위변제 회수율/소요기간) 쪽은 `interim_dividend_...parquet`의 `recovery_ratio`, `days_filing_to_dividend`가 Label로 바로 쓸 수 있다.

RAG용 데이터는 `processed/rag/rag_chunks_260714.jsonl`(938건 상담 -> 1,009 chunk)로 준비되었다. `metadata.pii_removed`가 전부 `false`로 표시되어 있으니, 임베딩 전에 반드시 사람이 한 번 검수해야 한다(자동 정규식 스캔은 전화번호·주민등록번호 패턴만 확인했고 40% 결측인 `special_note`, 자유서술형 `situation_summary`는 검수하지 않았다).

## 2026-07-14 갱신

- RAG PII 자동 스캔을 전화번호/주민번호/이메일/계좌의심패턴/상세주소(동·호·번지)까지 확장해 1,009건 전체를 재스캔했다 (`processed/rag/rag_chunks_260714_reviewed.jsonl`, `metadata/pii_review_260714.md`). 5종 패턴 모두 0건 검출됐지만 자유서술문의 실명·준식별자는 여전히 사람 검수가 필요해 `pii_removed`는 `false`로 유지했다.
- ML Feature 테이블이 막혀 있던 이유(등기부·실거래가 부재)를 해소하기 위해 `scripts/collect_raw_data.py`로 juso/rtms/building/business_status/dart/official_price×3/codef 9개 API를 실호출 시도했다. 이 작업 환경 네트워크 제한으로 전부 실패해 `raw/{address,rtms,building,...}/`에는 아직 Mock Fallback만 있다 (`source_system: mock`). 아웃바운드 네트워크가 열린 환경에서 재실행해 실 응답을 확보해야 `processed_risk_features_v1.parquet` 생성으로 넘어갈 수 있다.

## 2026-07-15 갱신

- TLS/CA 문제와 endpoint 설정을 보완한 뒤 `scripts/collect_raw_data.py`를 재실행해 9개 중 6개가 live 수집에 성공했다: 도로명주소, CODEF OAuth 토큰, 건축HUB 건축물대장, 아파트 매매 실거래가, 사업자등록, OpenDART.
- CODEF는 토큰 발급까지만 성공한 상태다. 실제 등기부등본 상품 API 호출과 결과 파싱은 아직 구현/검증 전이므로 등기부 권리관계 Feature(`mortgage_ratio`, `rights_burden_ratio`, `has_seizure`)는 계속 `mock_registry_*.json`을 사용한다.
- 공시가격 3종은 디지털트윈국토/VWorld 인증키로 확인되었고, 등록 서비스 URL(`https://www.khug.or.kr/index.jsp`)은 API endpoint가 아니다. 실제 API URL/레이어명 및 key/domain 또는 Referer 처리 방식 확인 전까지 `mock_official_price_success.json`을 사용한다.
- 개발 시작에는 충분하다. 다만 RiskClassification의 권리관계·담보가치 Feature는 live가 아니라 mock 기반이므로 PoC/화면/파이프라인 개발용으로 쓰고, 성능 검증용 학습 데이터로 과해석하지 않는다.
