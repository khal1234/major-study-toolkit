---
name: unit-symbol-notation-conflict
description: Use when introducing or reviewing a physics/engineering symbol (variable name) in any subject's content — especially single letters like C, N, W, L, m, s, g, K, V — that could visually collide with an SI unit abbreviation. Trigger before writing a new symbol into theory text, derivations, or figures, and when auditing existing chapters for notation drift.
---

# 단위-기호 표기 충돌 판단

물리·공학 기호(변수명)와 단위 약자가 같은 글자를 쓰는 경우, 로만체(단위)와 이탤릭체(기호)만으로는
독자가 못 가르는 자리가 반복해서 났다. 실사고: `K`(스프링 상수 vs 켈빈), `g`(중력가속도 vs 그램)가
각각 2026-08-02, 07-31에 걸렸다 — 같은 자리에서 두 번 났으므로 세 번째도 온다.

## 체크

새 기호를 쓰기 전에 묻는다: **이 글자가 이 과목에서 쓰는 단위 약자와 겹치는가?**

흔한 충돌 후보: `C`(커패시턴스/쿨롱 vs 섭씨), `N`(힘 단위 뉴턴 vs 개수), `W`(일/에너지 vs 와트),
`L`(길이 vs 인덕턴스 단위), `m`(질량 vs 미터), `s`(변위/거리 vs 초), `V`(전압 vs 부피).

겹치면 아래 중 하나로 명시적으로 갈라 쓴다(이 리포는 표기 자체를 자동으로 못 가른다 — 사람 판단):

- 로만/이탤릭 구분을 본문에서 명시(첫 등장 시 "이하 이탤릭 $m$은 질량, 로만 m은 미터")
- 다른 기호를 골라 충돌을 원천 차단(교재가 이미 그렇게 쓰면 교재 표기를 따른다)
- 단위를 항상 완전한 형태로 병기해 문맥으로 가른다

## 판정선

이건 `ask-vs-decide`가 아니다 — 승인/권한 판단이 아니라 **표기 관행(로만 vs 이탤릭)의 도메인
판단**이다. 이 프로젝트의 검사기(`buildlib/checks_content.py`)는 한 글자가 두 물리량을 가리키는
것(C44)은 잡지만, 기호-단위 충돌 자체는 기계로 못 가른다 — 새 기호를 쓸 때마다 사람이 이 체크를
직접 돈다.

## 기록

재발하면 `기록/feedback-ledger.md`(나루)에 한 줄 남기고, 세 번째 재발부터는 그 과목의
`terms.json`에 고정 표기로 등록해 다음 챕터에 자동 상속되게 한다(유체역학 V 속도/부피 충돌 사례
참고).
