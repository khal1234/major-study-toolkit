---
name: textbook-narrative-resemblance
description: Use when writing or reviewing theory prose for any subject chapter, especially when section order happens to match the textbook's table of contents. Trigger before finalizing a chapter's section structure, and whenever audit_content flags a 1:1 section-order match — that flag is a signal to inspect prose, not an automatic failure.
---

# 교재 서술 유사성(독자성) 판단

`tools/audit_problem_originality.py`류 기계 검사는 **12단어 연속 일치**(표절 수준)만 잡는다.
실제로 문제가 되는 건 그보다 약한 "닮은 서술" — 문장 구조·설명 순서·비유가 교재를 그대로 옮긴
느낌인데 단어 단위로는 안 겹치는 경우다. 이건 기계가 원리적으로 못 잡는다(2026-07-22 사고,
고체역학 ch02·동역학 ch12 — 절 순서가 교재와 1:1이라 서술까지 닮아 보였다. 2026-08-02에
"순서 1:1 자체는 FAIL이 아니라 [판정 필요] 신호"로 정정됨).

## 체크

`audit_content`가 절 순서 1:1 일치를 신고하면, 그 자리에서 절을 흔들지 말고 먼저 이걸 확인한다:

1. **이 순서가 의존 관계 때문에 필연적인가**(뒤 절이 앞 절의 결과를 전제하는가)? 그렇다면
   순서를 유지하는 게 맞다 — 억지로 섞으면 독자가 더 헷갈린다.
2. **본문 서술(설명 순서·예시·비유)이 교재와 닮았는가?** 순서 일치와 서술 유사성은 별개다.
   서술이 실제로 닮았다면 그 문단만 다시 쓴다(절 순서는 안 건드려도 됨).
3. 유지하기로 했으면 `chNN.textbook-map.md`에 `## 순서 판정` 절을 두고 **무엇을 검토했나 ·
   왜 유지했나 · 독자성을 무엇으로 확보했나**를 적는다 — 기록이 없으면 다음 세션에서 같은
   신고가 또 뜬다.

## 판정선

이 판단은 `completion-evidence-first`가 아니다 — "완료됐다는 증거"의 문제가 아니라, **애초에
기계가 잴 수 없는 축(서술의 닮음)을 사람이 대신 재는 도메인 작업**이다. 예시 소재 자체 발굴,
삽화 재현 금지도 같은 축의 다른 얼굴이다(AGENTS.md 규칙 12).
