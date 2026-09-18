---
name: bash-invocation-hygiene
description: Use before running any Bash command, and when deciding how to reduce permission-prompt friction across a project. Covers writing commands so allow-list prefix matching actually applies, and preferring a wider settings.json allowlist over bypass modes.
---

# Bash 명령을 승인 마찰 없이 쓴다

출처: 전공정리 세션 메모리 이관(2026-09-01) — 이 프로젝트 밖에서도 성립하는 순수
Claude Code 기술 습관이라 전역으로 승격했다.

## ① `cd X && cmd` 로 시작하면 allow 접두 규칙이 안 먹는다

`settings.json`의 allow 규칙은 보통 **명령의 첫 토큰**(실행 파일 이름)을 접두로 본다.
`cd some/dir && npm test` 처럼 `cd` 로 시작하면 그 규칙이 `npm` 이 아니라 `cd` 를 보게
되어 매칭이 깨지고, 원래 자동 허용됐어야 할 안전한 명령에도 승인 프롬프트가 뜬다.

체크: 디렉터리를 옮겨야 하면 `cd` 로 명령을 시작하지 말고 ⑴ 도구가 지원하면 작업
디렉터리 인자를 쓰거나 ⑵ 정말 필요하면 실행 파일 이름으로 명령을 시작하는 형태를
먼저 찾는다. 굳이 `cd &&` 를 써야 한다면 그로 인해 승인이 늘어난다는 것을 알고 쓴다.

## ② 안전한 작업은 자동 허용하고, 되돌리기 힘든 것만 프롬프트를 남긴다

목표는 "프롬프트 자체를 없애는 것"이 아니라 **마찰과 안전의 경계를 정확히 긋는 것**이다.
읽기 전용·로컬 빌드·테스트 같은 안전한 반복 작업은 `settings.json` allow 목록을 넓혀
자동 허용시키고, 커밋·푸시·배포·삭제처럼 되돌리기 어렵거나 공유 상태에 영향을 주는
것만 프롬프트가 뜨게 남긴다.

체크: 같은 안전한 명령에 매번 승인 프롬프트가 뜨는 게 반복되면, bypass 모드로 넘어가지
말고 **그 명령이 왜 allow 목록에 안 걸리는지**(접두 형태·인자 변형 등)부터 본다.
`fewer-permission-prompts` 스킬이 이 진단·목록 갱신을 자동화한다.
