---
name: worktree-read-context-bloat
description: Use before reading a file that lives in a different git worktree, branch checkout, or sibling project folder than the one this session's CLAUDE.md/AGENTS.md already loaded from. Reading such a file can pull that other folder's own instruction files into context a second time.
---

# 남의 워크트리를 Read 하면 지침이 통째로 다시 실린다

출처: 전공정리 세션 메모리 이관(2026-09-01), 실측: 87,882자 → 52,259자.

## 무엇이 문제인가

멀티 워크트리 git 프로젝트(과목별 워크트리, `main` 워크트리 등)에서, **자기 세션이
이미 로드한 CLAUDE.md/AGENTS.md와 별개로** 다른 워크트리 폴더 아래의 파일을 `Read`
하면, 그 폴더의 CLAUDE.md·AGENTS.md가 **또 한 번** 컨텍스트에 실릴 수 있다. 지침은
한 번 실리면 충분한데, 폴더를 넘나들며 읽을 때마다 다시 실려 컨텍스트가 눈에 띄게
불어난다.

## 체크

- 지금 읽으려는 경로가 **이 세션의 워크트리/프로젝트 루트 밖**에 있는가?
- 그렇다면 그 폴더 전체를 `Read`로 열지 말고, 필요한 내용만 **`git show
  <브랜치>:<경로>`** 같은 방식으로 지침 파일 로딩 없이 뽑아낸다.
- 이미 그 폴더의 지침이 한 번 실렸다면(이번 세션에서), 그 뒤로는 그 폴더의 다른
  파일을 `Read`해도 지침이 또 실리지는 않는다 — 문제는 **처음 읽을 때** 발생한다.
