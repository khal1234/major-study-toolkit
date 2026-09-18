# -*- coding: utf-8 -*-
"""한 과목만 보는 도구를 **전 과목에 한 번씩** 돌린다.

    python tools/for_each_subject.py fix_math_slash_fraction.py --apply
    python tools/for_each_subject.py audit_content.py --fail-only
    python tools/for_each_subject.py --only 수치해석,응용유체역학 fix_math_slash_fraction.py

★ **왜 있나 (열린 날 2026-09-07 · 평탄화).** `audit_content.discover_data_dir()` 은 «과목 =
  워크트리» 시절에 **첫 과목 폴더 하나**를 돌려주게 짜였다. 21과목이 한 트리에 온 뒤에도 그대로라,
  그 모듈을 쓰는 `fix_*`·감사 전부가 **`계측공학` 만 보고 「바꿀 것 없음」을 찍었다** — 0건이 아니라
  스무 과목을 한 번도 안 본 것인데 출력이 통과와 같았다(AGENTS 「폴백으로 하나만 넣어 두기」).

★ **과목 목록을 여기 박지 않는다.** `audit_content.subject_dirs()` 가 `data/` 를 읽어 정한다 —
  과목이 늘면 이 파일은 안 고친다.

★ **판정하지 않는다.** 어느 과목이 실패했는지 모아서 마지막에 목록으로 내고, 하나라도 실패하면
  exit 1 이다(빌드가 「한 장 걸려도 끝까지 돈다」로 바꾼 것과 같은 형태 — 첫 실패에서 멈추면 한
  과목이 스무 과목의 순회를 통째로 막는다).

**사람이 판정하는 자리:** 실패한 과목을 지금 고칠지 미룰지. 이 자는 고르지 않는다.
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def parse_argv(argv):
    """`(과목 한정 목록 or None, 도구, 도구 인자)`. 순수 함수 — 테스트가 직접 부른다."""
    only, rest = None, list(argv)
    if rest and rest[0] == "--only":
        if len(rest) < 2:
            raise ValueError("--only 뒤에 과목 이름이 없다")
        only = [s for s in rest[1].split(",") if s.strip()]
        rest = rest[2:]
    if not rest:
        raise ValueError("돌릴 도구 이름이 없다")
    return only, rest[0], rest[1:]


def main(argv=None):
    import audit_content                                                    # noqa: E402
    try:
        only, tool, tool_args = parse_argv(argv if argv is not None else sys.argv[1:])
    except ValueError as exc:
        sys.exit(str(exc) + "\n" + __doc__.split("\n\n")[1].strip())

    tool_path = tool if os.path.isabs(tool) else os.path.join(HERE, tool)
    if not os.path.isfile(tool_path):
        sys.exit("그런 도구가 없다: " + tool_path)

    subjects = [os.path.basename(p) for p in audit_content.subject_dirs()]
    if only:
        missing = [s for s in only if s not in subjects]
        if missing:
            sys.exit("그런 과목 폴더가 없다: " + ", ".join(missing))
        subjects = [s for s in subjects if s in only]
    if not subjects:
        # 「대상이 아닌 과목은 실패가 아니다」(AGENTS 알려진 함정) — 찍고 exit 0.
        print("[해당 없음] data/ 아래 과목이 없다 — 0개 과목")
        return 0

    failed = []
    for subject in subjects:
        env = dict(os.environ, SUBJECT=subject)
        # ★ `flush=True` 가 없으면 부모의 버퍼가 자식 출력보다 늦게 나가 **머리글이 전부
        #   맨 아래에 몰린다** — 어느 과목의 출력인지 화면에서 못 가린다(2026-09-07 첫 실행 실측).
        print("\n=== " + subject + " " + "=" * max(0, 60 - len(subject)), flush=True)
        code = subprocess.run([sys.executable, tool_path] + tool_args,
                              cwd=ROOT, env=env).returncode
        if code != 0:
            failed.append((subject, code))

    print("\n[전 과목] %d개 훑음 · 실패 %d개" % (len(subjects), len(failed)))
    for subject, code in failed:
        print("  · " + subject + " — exit " + str(code))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
