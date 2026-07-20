# processed/rag 안내

작성일: 2026-07-14 (2026-07-20 갱신)

| 파일 | 내용 |
|---|---|
| `rag_chunks_260714.jsonl` | 원본 청크 1,009건 (수정 금지, 최초 생성본) |
| `rag_chunks_260714_reviewed.jsonl` | PII 재검수 스캔 결과가 추가된 버전 (`metadata.pii_scan_v2`) |
| `rag_chunks_khug_260720.jsonl` | **안심전세포털 공식 콘텐츠 70청크** (`source: khug_portal`). 전세사기 개념·유형별 사례 8p·계약 단계별 유의사항 4p·보증가입·안전계약 컨설팅·피해지원 프로그램·경공매 지원/원스톱(특별법) 등 23페이지. `scripts/crawl_khug_portal.py`로 생성 |

## khug_portal 청크 적재·임베딩 절차 (2026-07-20)

1. `backend/.venv/bin/python scripts/load_rag_jsonl.py "개별수집데이터 및 API/processed/rag/rag_chunks_khug_260720.jsonl"` → `dive2026.rag_chunks` 업서트
2. `backend/.venv/bin/python scripts/embed_rag_chunks.py` → 임베딩 없는 청크만 추가 임베딩
3. Atlas `TLSV1_ALERT_INTERNAL_ERROR`가 재발하면 클러스터 실행 상태와 Security > Network Access의 현재 공인 IP 허용 여부를 확인한 뒤 1→2 순서로 재실행할 것.
4. 공식자료 청크는 `pii_removed: true`(공개 안내자료). 상담데이터 청크와 `source` 필드로 구분되므로 RAG 답변 UI의 "공식자료/상담사례" 출처 배지에 그대로 사용 가능.

## PII 재검수 현황 (2026-07-14)

전화번호·주민등록번호·이메일·계좌의심패턴·상세주소(동/호/번지) 5종 정규식 확장 스캔을
1,009건 전체에 적용했다. 결과는 `metadata/pii_review_260714.md` 참고.

- 5종 패턴 전부 0건 검출 (발제사가 이미 비식별 처리한 데이터와 부합)
- 그러나 자유서술형 문장 안의 실명·회사명·준식별자는 정규식으로 탐지 불가하므로
  `pii_removed`는 여전히 `false`로 유지했다. 실제 고객·계약 데이터를 추가하기 전에는 반드시 사람 검수를 완료한다.
- 권장 절차: `pii_review_260714.md` 3절 참고. 무작위 30건 표본 검수부터 시작 권장.

## 임베딩 현황 (2026-07-15)

- 개발용 비식별 상담 청크 1,009건 임베딩 완료
- 모델: `text-embedding-3-large`
- 출력 차원: 1024
- MongoDB 컬렉션: `dive2026.rag_chunks`
- Atlas Vector Search 인덱스: `rag_chunks_vector_index` (`ready`)
- 실제 고객 개인정보나 계약 원문은 현재 임베딩 대상에 포함하지 않음

## 다음 단계

1. 사람 검수 완료 후 `metadata.pii_removed: true`, `metadata.pii_scan_v2.human_reviewed: true` 갱신
2. FAQ·보증안내문 등 상담데이터 외 RAG 대상 추가 시 동일 청크 규칙(500~900자, overlap 80~150자) 적용
3. 신규·수정 청크 적재 후 `backend/.venv/bin/python scripts/embed_rag_chunks.py` 재실행
