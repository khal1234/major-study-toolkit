---
paths:
  - "site/template/**"
  - "tools/buildlib/render.py"
---

# 뷰어 템플릿 — 경로 규칙 (2026-09-11 AGENTS.md 에서 옮김)

> 템플릿·렌더러를 `Read` 할 때 실린다. 뷰어 수정은 `site/template/viewer.template.html` 한 곳뿐이다(절대 규칙 1).
> 고쳤으면 `docs/viewer-change-log.txt` 에 한 줄(CLAUDE.md 「변경점 기준선」).

## ★ 뷰어는 페이지에 안 실린다 — 자리표는 첫 `<script>` 블록에만 (2026-08-15)

템플릿의 `<style>`·`<script>` 중 **자리표(`{{…}}`)가 없는 블록은 빌드가 `site/_assets/` 로
뽑아낸다**(실측 근거: 페이지 335KB 중 뷰어가 143KB인데 장마다 똑같이 다시 실렸다 —
30과목 300장이면 중복만 ~42MB). 템플릿은 여전히 **유일한 수정 지점**이라 고치는 법은 안 바뀐다.
→ **딱 하나만 지키면 된다: 자리표는 첫 `<script>` 블록(`var CH = …` 가 있는 곳)에만 넣는다.**
아래 블록에 넣으면 그 블록이 통째로 페이지로 되돌아와 143KB가 장마다 다시 실린다.
왜 이렇게 갈랐는지·해시 이름이 낡은 갈래를 어떻게 살리는지는 `buildlib/render.prepare_viewer`
독스트링이 정본이고, 잠금은 `test_checks.py::test_viewer_is_split_into_shared_assets`.

## 함정

- `hidden` 속성 + 저자 `display:` 충돌 → 템플릿의 `[hidden]{display:none!important}` 가드를 지우지 않는다.

