---
name: web-fetch-etiquette
description: Use whenever fetching external web pages (WebFetch or an HTTP client) as part of a task, especially repeated or bulk fetches to the same site. Covers identifying the client honestly, pacing repeated requests, and not bypassing a site's stated crawl policy.
---

# 외부 페이지를 가져올 때 지키는 예의

출처: 전공정리 세션 메모리 이관(2026-09-01) — 웹 페칭을 하는 모든 프로젝트에 적용되는
일반 습관이라 전역으로 승격했다.

## 지킬 것

- **항상 정직한 User-Agent를 보낸다** — 신원을 숨기거나 브라우저인 척 위장하지 않는다.
- **같은 사이트에 반복 요청을 낼 때는 페이싱한다** — 짧은 시간에 몰아치지 않는다.
  단발 조회가 아니라 여러 페이지·여러 회차에 걸쳐 같은 도메인을 두드릴 계획이면
  요청 사이 간격을 두는 쪽을 기본으로 삼는다.
- **`robots.txt`가 이미 처리되고 있는 경로라면 그 로직을 건드리지 않는다** — 새로
  우회 경로를 만들지 않는다. 그 사이트가 명시적으로 막은 크롤 정책을 회피 목적으로
  파고들지 않는다.

체크: 지금 하려는 페치가 ⑴ 같은 도메인에 짧은 간격으로 여러 번 나가는가 ⑵ 이미
차단된 경로를 우회하려는 시도인가 — 둘 중 하나라도 그렇다면 속도를 늦추거나 방법을
바꾼다.
