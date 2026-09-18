---
name: long-run-hazards
description: Use during any long-running autonomous batch (many tool calls, a loop, a multi-hour session, a large bulk edit across many files) — checks for staleness drift mid-run, hooks whose output may not reach the next turn, unproven blast-radius on bulk edits, and scheduled/cron automation going silently inactive. These are proposed-but-not-yet-mechanized hazards — this Skill is the stopgap until each gets its own hook.
---

# 장기 자율 작업의 숨은 위험

이 넷은 전부 "이렇게 막으면 될 것 같다"는 제안까지는 나왔는데 **아직 훅으로
안 만들어진** 것들이다. 그래서 지금은 이 Skill로 스스로 인지하고 점검하는 수밖에
없다 — 훅이 생기면 이 절은 그 훅을 가리키는 걸로 바꾼다.

## ① 턴 경계에서만 신선도를 확인한다 — 턴 중간의 드리프트를 놓친다

- 실사고(2회): 긴 턴 도중에 `main` 브랜치가 바뀌었는데 아무도 못 봤다. 3개 세션이
  같은 날 같은 인프라 버그를 독립적으로 고치는 일까지 났다.
- 지금 할 수 있는 것: 도구 호출을 오래 반복하는 배치 중간에, 가끔 `git log -1`이나
  기준선 파일의 해시를 다시 확인한다.

## ② Stop 훅의 출력이 다음 턴에 안 이어질 수 있다

- 실사고(2026-08-30, XSanity §115, 아직 새로 발견된 관찰): 세션 자신이 만든 예방 훅
  (`open_items.py`류)이 뭔가를 냈는데, 다음 턴이 그걸 안 읽고 지나갔다.
- 지금 할 수 있는 것: 훅 출력에 의존하는 절차를 설계할 때, "떴다"와 "다음 턴이 그걸
  읽고 반영했다"를 같은 것으로 가정하지 않는다.

## ③ 대량 편집 후 "안 건드린 것"을 증명하지 않는다

- 실사고: 정규식 기반 일괄 치환이 의도 못한 대상(SVG path 명령, 다른 변수명)까지
  건드렸다. "몇 건 고쳤다"는 셌지만 "무엇을 안 건드렸는지"는 증명 안 했다.
- 지금 할 수 있는 것: 5개 파일 넘는 일괄 치환 전에 `--dry-run`으로 미리 훑고,
  제외 규칙마다 "올바로 건너뛴 예"를 하나씩 확인한다.

## ④ 계절성/예약 자동화가 조용히 멈춘다

- 실사고: GitHub Actions가 60일 무활동이면 자동으로 비활성화되는데 아무도 몰랐다.
- 지금 할 수 있는 것: 예약 작업을 다룰 때 "설정에 있다"와 "실제로 최근에 돌았다"를
  구별해서 확인한다(설정 파일이 아니라 실행 이력을 본다).
