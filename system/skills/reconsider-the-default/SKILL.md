---
name: reconsider-the-default
description: Use when about to reach for a tool, library, method, or approach "because it's already there / already installed / already how this has always been done" — especially at the start of a new task, or when a task feels slower/more awkward than it should. Also use periodically to re-examine a long-settled tool/library/approach choice even when nothing is currently going wrong with it — friction is not required to trigger this. Checks whether a constraint (explicit or just habit) is quietly blocking a better alternative from ever being considered.
---

# 정착된 선택은 외부 자극 없이는 재검토가 안 된다

## 핵심 발견 (2026-08-31, XSanity OCR 실측 — 사용자 판정: 전 프로젝트)

XSanity가 곡 제목 판독에 계속 Tesseract를 썼는데, 공용 폴더가 "다른 OCR도 검토해봐"라고
찔러서야 실측했더니 PaddleOCR이 압도적이었다(대조 후 정확도 96% vs Tesseract 0%).
XSanity 스스로: *[발화 생략]* 사용자가 이걸
전 프로젝트에 걸리는 문제로 판정했다.

## 왜 이게 일어나는가 — 제약은 양날이다

같은 날 강의 자료(프롬프트 엔지니어링의 "제약조건"·"기술스택" 요소)를 보고 사용자가
연결한 통찰: *[발화 생략]*

- 제약(명시적 지시든, "이미 있으니까"라는 암묵적 습관이든)은 **선택지를 좁혀서
  실행을 빠르게 만드는 값**이 있다.
- 동시에 **그 좁힘 자체가 대안 탐색을 막는 비용**이 된다.
- 둘 중 어느 쪽이 큰지는 "그 제약이 의도적으로 좁힌 것인가, 아니면 그냥 한 번도
  안 재본 기본값인가"로 갈린다 — 전자는 지켜야 하고, 후자는 재검토 대상이다.

## 체크리스트

1. **지금 쓰려는 도구·라이브러리·방법을 왜 쓰는지 스스로 답해본다.** 답이
   "이미 있어서/설치돼 있어서/원래 이렇게 해왔어서"뿐이라면, 그건 **의도적 제약이
   아니라 그냥 안 재본 기본값**이다.
2. **작업이 예상보다 느리거나 어색하게 느껴지면, 그 원인이 "이 방법 자체의 한계"
   인지 먼저 의심한다.** 방법을 못 바꾸는 게 아니라 안 바꿔본 것일 수 있다.
3. **사용자가 명시적으로 건 제약(기술스택·[발화 생략])은 그대로 지킨다** — 이건
   의도적 좁힘이라 재검토 대상이 아니다. 구별할 것: 사용자가 건 제약 vs 내가(혹은
   이전 세션이) 습관적으로 굳힌 기본값.
4. 재검토했는데 기존 선택이 여전히 맞다면 — **그 사실(무엇을 비교했고 왜 기존
   것을 유지하는지)을 남긴다.** 남기지 않으면 다음에 또 처음부터 재검토해야 한다.

## 반응형만으로는 부족하다 — 탐색 예산을 0으로 두지 않는다

위 체크리스트는 전부 **불편함·마찰이 이미 느껴진 뒤**에 재검토하는 반응형이다.
그런데 지역 최적(local optimum)에 갇히는 방식은 마찰이 없어도 일어난다 — 지금
방법이 "그럭저럭 잘 되고 있으면" 재검토할 계기 자체가 안 생긴다.

- 사용자(2026-08-31): *[발화 생략]*
- 슬라임몰드(*Physarum polycephalum*)의 탐색 방식과, 강화학습의
  **탐색-활용 트레이드오프(exploration-exploitation tradeoff)**가 같은 원리를
  가리킨다 — 알고 있는 길만 계속 쓰는 게 "활용", 가끔 모르는 길에 자원을 쓰는 게
  "탐색"이고, 활용만 하면 지역 최적에 갇힌다.
- **적용:** 지금 쓰는 방법이 잘 돌아가고 있어도, 오래 정착된 선택(도구·라이브러리·
  접근 방식)은 **가끔은 마찰 없이도** "다른 방법이 지금보다 나을까"를 한 번씩
  찔러본다. 매번 할 필요는 없다 — 판단 두께는 **되돌릴 수 있는가·눈에 띄는가·
  오래가는가·여러 사람/세션이 보는가**(어떤 프로젝트든 성립하는 일반 기준. 공용 폴더가
  있는 프로젝트라면 `규칙/프로젝트-층.md`가 이 네 축을 정본으로 다룬다)로 정한다 —
  오래 정착됐고 자주 쓰는 것일수록 탐색 예산을 조금씩 배정한다.

## 관련이지만 다른 것

`reuse-before-rebuild` Skill과 방향이 반대다 — 그건 "이미 있는 걸 무시하고 새로
만들지 마라"이고, 이건 "이미 쓰는 걸 의심 없이 계속 쓰지 마라"다. 상황에 맞는
쪽을 골라 쓴다: **로직/파서**는 재사용 쪽으로, **도구/방법 선택**은 재검토 쪽으로
기본값이 다르다.
