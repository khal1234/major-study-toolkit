---
name: cross-link-anchor-granularity
description: Use when adding any internal cross-reference link ([[chNN:anchor]] or cross-subject [[subject@chNN:anchor]]) in chapter content. Trigger before finalizing a link's target and display text — decide whether it should land on a narrow anchor (a specific figure, derivation, or definition) versus a whole section.
---

# 과목간·과목내 교차링크 앵커 단위 판단

내부 링크 문법(`[[chNN:앵커|문구]]`, 과목간 `[[과목@chNN:앵커|문구]]`)은 정해져 있지만, **어느
단위를 앵커로 잡을지**는 룰이 없고 매번 사람이 판단한다 — 이걸 재는 체커도 카운터도 없다.

## 체크

링크를 걸기 전에 묻는다: **독자가 클릭해서 기대하는 것이 좁은 대상(그림 하나·유도 하나·정의
문단)인가, 아니면 절 전체의 맥락인가?**

- **좁은 앵커가 있으면 반드시 그쪽으로.** "정상유동 과정"을 눌렀는데 그 개념이 아니라 상위 절
  맨 위가 보이면 결함이다(AGENTS.md 내부 링크 규칙). 절 id는 착지할 좁은 대상이 없을 때만
  쓰는 최후 수단이다.
- 절 링크를 쓸 수밖에 없다면 표시 문구에서 "절로 간다"는 게 드러나게 적는다
  (`'과정과 사이클' 절`처럼).
- 같은 화면에 같은 대상으로 가는 링크가 두 번 걸리면 본문 쪽만 남기고 삽화 캡션 쪽을 뺀다.

## 과목간 링크 추가 판단

과목간 링크(`@`)는 **1학기→2학기 되짚기 방향으로만** 쓴다 — 안 배운 내용을 미리 보여주는 자리엔
안 쓴다. 대상이 다른 git 브랜치라 빌드가 실존 여부를 못 검사하므로, 걸기 전에
`git show <브랜치>:data/<과목>/chNN.json`으로 직접 확인한다.

## 판정선

이건 링크 문법 오류가 아니라 **"독자가 클릭 한 번으로 무엇을 얻어야 하는가"라는 편집 판단**이다.
체커가 있는 건 `xlink_target_valid`(대상이 존재하는가)뿐이고, 앵커 단위 자체는 사람이 각 링크마다
판단한다.
