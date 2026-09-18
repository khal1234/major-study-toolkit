# START — 에이전트가 첫 세션에서 따르는 순서

> **에이전트에게.** 이 저장소는 참고 자료가 아니다. **네가 이 폴더에서 일하는 방식 그 자체다.**
> `CLAUDE.md`(Codex 는 `AGENTS.md` → `CLAUDE.md`)의 규칙을 네 작업 규칙으로 채택하고, 도구는
> `tools/` 에 있는 것을 먼저 쓴다(새로 짜기 전에 `docs/도구-등록부.md` 를 Grep 한다).
> 「참고할 만한 구조가 있네」 하고 평소 방식으로 돌아가면 이 틀을 받은 의미가 없다.

## 1. 설치 상태를 잰다 (묻지 않고 먼저 한다)

```bash
python setup.py                 # 무엇이 깔렸고 무엇이 빠졌나 — 보여 주기만 한다
python tools/test_checks.py     # 틀이 이 컴퓨터에서 도나(10/10 이어야 한다)
```

빠진 것이 있으면 사용자에게 **한 번에** 권한다: `python setup.py --rules --skills`
(Codex 면 `--codex`). 깔고 나면 **세션을 새로 열어야** 규칙·스킬이 실린다고 알린다.

## 2. 첫 과목을 사용자와 세운다

`data/` 에 과목이 없으면 사용자에게 **이 넷만** 묻는다(한 메시지로):

1. 과목 이름과 영문 짧은 이름(예: 동역학 / dynamics)
2. 교재 이름·판, 교재 PDF가 있는 폴더 경로
3. 시험 문제 지문이 영어인가 한국어인가
4. 먼저 정리할 장

받으면 `python setup.py --subject <과목> --slug <영문> --textbook-dir "<경로>" --pitfall-book "<저자> 본문 경고"`
를 돌리고, `data/<과목>/SUBJECT.md` 의 빈칸을 답으로 채운다.

## 3. 첫 장을 만든다

- 규칙은 `.claude/rules/content.md`(장 JSON)·`figures.md`(삽화)를 **쓰기 전에** 읽는다.
- 교재는 `python tools/extract_textbook.py --pdf <파일명 조각> --pages <쪽>` 으로 읽는다. **원문을 JSON에
  옮기지 않는다** — 자기 말로 다시 쓴다(CLAUDE.md 절대 규칙 2·3).
- `python tools/register_chapter.py --chapter=chNN --number=N --title="…"` 로 장을 등록한다.
- `python tools/build_site.py` 가 **exit 0** 이 될 때까지 데이터를 고친다(검사를 완화하지 않는다).
- 끝나면 `site/<과목>/chNN.html` 을 사용자에게 열어 보여 주고, 검수받을 것을 한 번에 묻는다.

## 4. 끝낼 때

`docs/인계.md` 맨 위에 한 줄(도구 · 마지막 커밋 · 어디까지 · 다음) — 다음 세션이 거기서 시작한다.
