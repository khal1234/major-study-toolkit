---
name: fetch-before-declaring-stale
description: Use before concluding that a bot, cron job, or automation "has stopped working" based on a local git clone looking inactive. If anything commits directly to the remote (a bot, CI, another machine), the local clone falls behind on its own — that's not the same as the automation being dead.
---

# 로컬이 뒤처진 것과 자동화가 죽은 것은 다르다

출처: knu-bot 세션 메모리 이관(2026-09-01, HANDOFF.md에 2회 재발: 2026-08-18·08-25).

크론이나 봇이 **원격에 직접** 커밋하는 리포는 로컬 클론이 그 커밋을 안 당겨오면
빠르게 뒤처져 보인다. 그 뒤처짐을 "며칠째 안 움직인다 = 자동화가 죽었다"로 오판하기
쉽다 — 실제로는 원격에 이미 새 커밋이 쌓여 있는데 로컬만 안 본 것일 수 있다.

체크: 자동화가 멈췄다고 결론 내리기 전에 **`git fetch`부터 하고 원격 기준으로
마지막 활동 시각을 다시 잰다.** 로컬 `git log`만 보고 "안 돈다"고 판정하지 않는다.

`long-run-hazards`의 "크론이 조용히 안 도는 것"과는 다른 문제다 — 그건 스케줄 자체가
꺼진 경우이고, 이건 스케줄은 돌고 있는데 **관측 지점(로컬 클론)이 낡아서** 안 도는
것처럼 보이는 경우다.
