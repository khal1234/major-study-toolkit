---
name: local-file-over-artifact
description: Use when deciding whether to publish an Artifact for something whose purpose is the user reviewing or confirming content, not sharing it with others. Publishing has a real cost (a public-by-default link, review overhead) that a plain local file avoids.
---

# 검수 목적이면 아티팩트 대신 로컬 파일로 준다

출처: XSanity 세션 메모리 이관(2026-09-01) — 발행 비용을 사용자가 실제로 언급한
사례가 있다.

Artifact 발행은 공짜가 아니다 — 링크가 생기고, 나중에 공유 여부를 사용자가 다시
판단해야 하고, 발행 자체가 하나의 행위로 쌓인다. **지금 만드는 것의 목적이 "사용자가
보고 확인/검수하는 것"이지 "누군가와 공유하는 것"이 아니라면**, Artifact로 발행하지
말고 로컬 파일로 준다(필요하면 `SendUserFile`로 보낸다).

체크: 이걸 다른 사람과 공유할 계획이 있는가, 아니면 사용자 본인이 한 번 확인하고
끝날 것인가? 후자면 로컬 파일이 기본이다. 판단이 애매하면(나중에 공유할 수도 있는
결과물) 발행하되 그 이유를 짧게 남긴다.
