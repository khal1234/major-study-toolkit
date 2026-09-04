---
name: svg-checker-blind-spots
description: Use when a figure (SVG) "passes" build lint/checks_svg with zero findings, right before trusting that result, or whenever authoring a figure that uses transform/rotate or multi-path composite shapes (axes, L-shapes). Trigger on any "0 findings" or "all figures pass" claim about SVG geometry checks in this project — verify the checker could actually see the shape before treating silence as correctness.
---

# SVG 검사기 사각지대 인식

이 리포의 `buildlib/checks_svg.py`는 좌표를 직접 계산해서 규격(치수선 간격·화살촉 비율·라벨 여백
등)을 검사한다. 두 번 실측된 함정: 검사기가 **기하학적으로 못 보는 형태**라서 "0건"이 나온 것이지
실제로 규격을 지킨 게 아니었다.

## 실사고 둘

1. **transform 적용 전 좌표로 검사** (2026-08-01, `checks_svg`) — `transform="rotate(...)"`가 걸린
   도형은 원본 좌표계 그대로 검사되어, 실제 화면에 회전된 뒤의 형태와 검사 결과가 다르게 났다.
2. **축을 두 개의 `<path>`로 나눠 그림** (2026-08-07, 열역학 ch06) — L자형 좌표축을 한 path로
   이어 그리지 않고 가로·세로를 별개 path 둘로 쪼개자, 화살촉 검사(C18·C19)가 "축 하나"로
   인식을 못 해 조용히 스킵됐다. 그날 무관한 계기로 재검토하다 findings 11건이 한꺼번에 드러났다.

## 체크

새 삽화를 만들거나 "검사 통과"를 근거로 삼기 전에 묻는다:

- **이 도형에 `transform`이 걸려 있나?** 걸려 있으면 검사가 회전/이동 후 실제 좌표를 보는지
  확인한다(모르면 통과를 믿지 않는다).
- **하나의 논리적 형태(축·화살표·경계선)를 여러 `<path>`로 쪼개 그렸나?** 검사기는 대개
  path 하나 단위로 형태를 인식한다 — 쪼개면 "그 형태 자체가 없다"고 읽혀 검사 대상에서
  빠질 수 있다.
- **"findings 0건"이 나왔을 때, 이 삽화가 검사 대상 형태 카테고리에 실제로 걸리는 종류인가?**
  대상이 아니라서 0건인지, 정말 지켜서 0건인지는 다르다.

## 판정선

이건 `verifier-isolation`(독립 검증자에게 무엇을 주는가)이 아니라 **이 리포 특정 검사기
아키텍처의 구조적 사각지대**를 아는 것이다 — 렌더 PNG 육안 검수(`render_figure_review.py`)를
병행해야 진짜로 닫힌다. AGENTS.md 삽화 규격 절의 "기계가 안 막는다" 목록과 짝이지만, 이건
그중에서도 "기계가 막는다고 선언했는데 실제로는 안 보는" 더 위험한 하위 부류다.
