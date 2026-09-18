---
paths:
  - "tools/**/*.py"
  - ".claude/hooks/*.py"
---

# 공통 도구·훅 작성 — 경로 규칙 (2026-09-11 AGENTS.md 에서 옮김)

> 도구·훅 소스를 `Read` 할 때 실린다. 새 도구를 `Write` 로 만들 때는 먼저 기존 도구 하나를 `Read` 한다
> (`guard_write` 가 이 규칙이 안 실린 세션의 새 파일 쓰기를 막는다). 새 스크립트를 짜기 전에
> `docs/도구-등록부.md` 를 먼저 본다(CLAUDE.md 「도구 등록부」).

## ★ 공통 도구에 과목별 사실을 박지 않는다 — 폴백도 안 된다 (신설 2026-08-01)

여러 과목에서 반복해 걸린 부류다 — 도구 하나를 고치는 것으로 닫지 않는다.

- **공통 코드(`tools/**`·`site/template/**`)는 과목 이름·챕터 목록·교재 경로를 알면 안 된다.**
  그런 것은 `data/<과목>/` 의 파일이 갖는다(선례 `textbook-pdf-map.json`·`textbook-motifs.json`).
- **「폴백으로 하나만 넣어 두기」가 가장 흔한 함정이다.** 실사고(`audit_problem_originality.PDF_FOR`):
  열역학 5챕터 사전이 폴백으로 남아 ⑴ 공통이 그 과목을 계속 알고 있었고 ⑵ 다른 과목은 매핑이 없다는
  사실조차 안 드러난 채 `합계 — 정상 0` 을 찍었다. **0건이 아니라 한 건도 안 본 것**인데 출력이 통과와
  같았다. → **모든 과목이 같은 경로로만 동작하게 한다. 원조 과목도 예외를 두지 않는다.**
- **왜 반복되나 — 만드는 사람은 언제나 한 과목 안에 있다.** 판정 기준은 *[발화 생략]* 가 아니라
  **[발화 생략]** 다.
- 기계 방지: 새 공통 도구를 만들 때 `test_checks.py` 에 ⑴ 소스에 과목 이름·과목별 사전이 없는지
  ⑵ 순회 대상을 `audit_content.CHAPTERS` 로 잡는지를 케이스로 넣는다. 선례
  `test_tools_do_not_hardcode_a_subject` · `test_originality_pdf_map_is_subject_local` ·
  `test_no_subject_hardcoded_data_root` · `test_shared_tests_do_not_assume_subject_data`.

## 도구 함정 (재발 금지)

- **인코딩은 `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`.** `io.TextIOWrapper` 로 감싸면
  `build_review.py` 가 `build_site.py` 를 runpy 로 부를 때 이중 래핑이 되어 첫 wrapper 가 GC 되며 buffer 를
  닫는다(`ValueError: I/O operation on closed file`). **`tools/*.py` 의 인코딩을 손대면 반드시
  `build_review.py --all` 까지 재검증한다** — 단독 실행으로는 안 드러난다.
- **바깥에서 들어오는 텍스트는 무조건 UTF-8 로 명시해 읽는다.** Windows 기본이 cp949 라 명시하지 않으면
  한글이 **예외도 없이 조용히** 깨진다 — 훅 페이로드는 `read_payload()`, `subprocess.run(text=True)` 에는
  `encoding="utf-8"`. ASCII 만 보는 규칙은 멀쩡해서 **가드가 도는 것처럼 보이는 것**이 이 부류의 무서운
  점이다(실제로 과목 경계가 통째로 죽어 있었다). → `guard_bash.read_payload()` 독스트링 · `test_guard_rules`.
- **나가는 쪽도 마찬가지다 — `stderr` 를 안 고치면 「오류 메시지만」 깨진다**(2026-08-12). 실측: 도구 79개가
  `sys.stdout.reconfigure` 를 부르는데 stderr 를 고친 것은 하나뿐이었다. 정상 출력은 멀쩡한데 **사람이 가장
  읽어야 할 글만** 깨진다. → `sys.exit("한글…")`·`print(…, file=sys.stderr)` 를 쓰는 도구는
  `sys.stderr.reconfigure(encoding="utf-8", errors="replace")` 도 함께 둔다. 잠금 `test_tool_failures_are_readable`.
- **「대상이 아닌 과목」은 실패가 아니다.** 과목이 선언해야 도는 도구가 선언 없는 과목에서 exit 1 을 내면
  배치와 사람 둘 다 «실패했다» 로 읽는다. 선언이 곧 opt-in 이므로 그 경우는 `[해당 없음] … 0건` 을 찍고
  **exit 0** 으로 끝낸다.
