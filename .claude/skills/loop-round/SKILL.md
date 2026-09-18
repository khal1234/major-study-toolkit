---
name: loop-round
description: Use when running inside /loop or about to call ScheduleWakeup — per-round rules (delay fixed at 60s, a round closes one numbered item and commits, no per-round reports, wakeup_guard on/off/measure).
---

# 루프 회차 규칙 (2026-09-11 AGENTS.md 실행 규율 6·9 에서 옮김)

## 규율 6 — `/loop` 안에서도 끊지 않는다

- `delaySeconds` 60초는 다음 깨어남까지의 최소 간격이지 한 턴의 상한이 아니다.
  ★ `ScheduleWakeup` 자신의 일반 안내(유휴 틱 20~30분)는 *외부 신호를 기다리는* 경우의 것이라
  따르지 않는다 — 기다리는 대상이 없으면 60초로 고정한다.
  - 판정선 ⑴ 회차는 순서 번호 하나를 닫기 전에 끝내지 않는다 ⑵ 진단만 하고 끝내지 않는다(원인을
    찾았으면 그 회차 안에서 처방까지). 트리거는 `ScheduleWakeup` 을 부르는 자리다.
  - 회차마다 보고하지 않는다 — 회차 중에는 한 줄 상태, 기록은 인박스·커밋 메시지, 표 보고는 루프가
    끝날 때 한 번. 빌드는 `--quiet` 가 기본이다.
- → 공용 폴더 `규칙/끊지-말고-끝내고-보고한다.md` · 원장 2026-07-30 · 2026-08-12 · 2026-08-29.

## 규율 9 — 재예약은 훅이 감시한다

- ★ **문맥 크기는 멈춤 사유가 아니다**(2026-09-18 사용자 *[발화 생략]*) — 하네스가 자동 압축한다. 문맥 훅의 `/compact` 제안은 루프가 **끝난 뒤** 보고에만 싣는다.
  `off` 는 `--reason user|blocked|done` 이 필수이고 다른 사유는 거부된다(`off_reason_issue`).
- 켜기·끄기만 사람이 한다(`python tools/wakeup_guard.py on` · `off --reason …` · `status`). 루프 모드인데 그 턴에
  `ScheduleWakeup` 이 없으면 Stop 훅이 멈춤을 막는다 — 끝낼 것이면 `off` 를 먼저. 깃발이 꺼져 있으면
  12시간 뒤 만료된다.
- **회차에 커밋이 0이면 같은 훅이 막는다**(2026-09-08, 같은 지적 4회째). 한 항목이 막혔으면
  **같은 턴 안에서** 다음 항목으로 이어 간다 — 예약을 걸고 60초를 버리는 것이 아니다.
  전부 막혔으면 회차를 늘리지 말고 루프를 끝내고 보고한다. 눈금 `wakeup_guard.py measure`.
- ★ **PC 는 안 끈다.** 잠금 `test_wakeup_guard_blocks_a_turn_without_a_wakeup`.
