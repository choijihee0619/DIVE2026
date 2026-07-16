# processed/rag 안내

작성일: 2026-07-14

| 파일 | 내용 |
|---|---|
| `rag_chunks_260714.jsonl` | 원본 청크 1,009건 (수정 금지, 최초 생성본) |
| `rag_chunks_260714_reviewed.jsonl` | PII 재검수 스캔 결과가 추가된 버전 (`metadata.pii_scan_v2`) |

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
3. 신규·수정 청크 적재 후 `/usr/local/bin/python3 scripts/embed_rag_chunks.py` 재실행
