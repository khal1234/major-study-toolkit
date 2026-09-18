# -*- coding: utf-8 -*-
"""챕터 하나의 **번호를 갈아 끼운다** — 파일 이름부터 검수 스냅샷까지 한 번에.

열린 날 2026-08-27. 사용자:

    *[발화 생략]*

번호가 「만든 순서」로 붙어 있었다(91 중간 · 92 기말 · 93 중간 2판). 시험별로 묶으면
**91·92 가 중간, 93·94 가 기말**이라 외울 것이 없어진다. 같은 일이 기말을 두 벌로 가를 때
또 오므로 일회성 편집 대신 도구로 올렸다.

★ **손으로 하면 반드시 빠뜨리는 자리가 있다.** 번호는 한 곳에 안 산다 —

    ⑴ 파일 이름            data/<과목>/chNN.json
    ⑵ 파일 안의 chapterNumber
    ⑶ 그 장의 문항·삽화 id  (chNN-e01 · fig-chNN-e01-…)
    ⑷ index.json           chapters[].file · chapters[].chapterNumber
    ⑸ index.json           strictChapters 의 **모든** 키 목록
    ⑹ textbook-pdf-map.json 의 키
    ⑺ 검수 스냅샷           data/<과목>/.review-snapshot/chNN*.json
    ⑻ 다른 장의 내부 링크   [[chNN:앵커id|…]]
    ⑼ 독자성 판정 키        problem-originality-verdicts.json 의 chNN-…

★ **이 도구가 안 하는 것 둘** — 사람이 판정한다:
    · 산문 속의 「92장」 같은 말 (숫자만 보고 고치면 교재 장 번호까지 바꾼다)
    · 검산 스크립트(`verify_*_answer.py`)의 케이스 이름 — 공통 파일이라 과목 선언 중에는 못 만진다

    python tools/renumber_chapter.py --from ch93 --to ch92 [--apply]

목적지 파일이 이미 있으면 거부한다. **맞바꾸려면 임시 번호를 거쳐 세 번 부른다**
(chA → chTMP → … → chTMP → chB).
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CH_RE = re.compile(r"^ch\d{2}$")


def data_root():
    """이 리포의 `data/<과목>` — 과목 이름을 코드에 박지 않는다(공통 도구 규칙)."""
    base = os.path.join(REPO, "data")
    roots = [os.path.join(base, p) for p in sorted(os.listdir(base))
             if os.path.isdir(os.path.join(base, p))] if os.path.isdir(base) else []
    return roots[0] if len(roots) == 1 else None


def sub_text(text, old, new):
    """`chNN` 이 **낱말로** 붙은 자리만 바꾼다 — 교재 쪽 번호나 긴 수를 안 건드린다."""
    n = 0
    for pat, rep in ((old + "-", new + "-"),          # 문항·삽화 id
                     (old + ".json", new + ".json"),  # 파일 이름 참조
                     (old + ":", new + ":"),          # 내부 링크 [[chNN:...]]
                     (old + ".", new + ".")):         # chNN.textbook-map.md 따위
        n += text.count(pat)
        text = text.replace(pat, rep)
    return text, n


def rewrite_file(path, old, new, apply_it):
    if not os.path.isfile(path):
        return 0
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    out, n = sub_text(text, old, new)
    if n and apply_it:
        with io.open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return n


def main(argv):
    old = new = None
    apply_it = "--apply" in argv
    for i, a in enumerate(argv):
        if a == "--from" and i + 1 < len(argv):
            old = argv[i + 1]
        elif a.startswith("--from="):
            old = a.split("=", 1)[1]
        elif a == "--to" and i + 1 < len(argv):
            new = argv[i + 1]
        elif a.startswith("--to="):
            new = a.split("=", 1)[1]
    if not (old and new) or not CH_RE.match(old) or not CH_RE.match(new):
        sys.exit(__doc__)
    if old == new:
        sys.exit("같은 번호다 — 할 일이 없다")

    root = data_root()
    if root is None:
        sys.exit("data/ 아래 과목 폴더를 하나로 특정할 수 없다")
    src = os.path.join(root, old + ".json")
    dst = os.path.join(root, new + ".json")
    if not os.path.isfile(src):
        sys.exit("없는 챕터: " + src)
    if os.path.isfile(dst):
        sys.exit("목적지가 이미 있다: %s — 맞바꾸려면 임시 번호를 거칠 것" % dst)

    hits = []

    # ⑴⑵⑶ 챕터 파일 자체
    with io.open(src, encoding="utf-8") as fh:
        text = fh.read()
    body, n_ids = sub_text(text, old, new)
    body = body.replace('"chapterNumber": %d' % int(old[2:]),
                        '"chapterNumber": %d' % int(new[2:]))
    hits.append((old + ".json → " + new + ".json", n_ids + 1))

    # ⑷⑸⑹⑻⑼ 이웃 파일들 — 같은 치환 규칙 하나로 덮는다
    others = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isfile(p) and p != src and (name.endswith(".json") or name.endswith(".md")):
            others.append(p)
    for p in others:
        n = rewrite_file(p, old, new, apply_it)
        if n:
            hits.append((os.path.basename(p), n))

    # ⑺ 검수 스냅샷
    snap = os.path.join(root, ".review-snapshot")
    moves = []
    if os.path.isdir(snap):
        for name in sorted(os.listdir(snap)):
            if name.startswith(old + ".") or name == old + ".json":
                moves.append((os.path.join(snap, name),
                              os.path.join(snap, new + name[len(old):])))

    print("[번호 갈아끼우기] %s → %s" % (old, new))
    for what, n in hits:
        print("  %-40s %d곳" % (what, n))
    for a, b in moves:
        print("  스냅샷  %s → %s" % (os.path.basename(a), os.path.basename(b)))

    if not apply_it:
        print("[미적용] 실제로 바꾸려면 --apply")
        return 0

    with io.open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(body)
    os.remove(src)
    for a, b in moves:
        os.replace(a, b)

    with io.open(dst, encoding="utf-8") as fh:
        ch = json.load(fh)
    if ch.get("chapterNumber") != int(new[2:]):
        sys.exit("chapterNumber 가 안 바뀌었다 — 손으로 확인할 것")
    left = [q.get("id") for q in (ch.get("problems") or [])
            if str(q.get("id")).startswith(old + "-")]
    if left:
        sys.exit("옛 번호가 문항 id 에 남아 있다: " + ", ".join(left[:3]))
    print("[적용] %s · JSON 유효 · 문항 %d개"
          % (os.path.basename(dst), len(ch.get("problems") or [])))
    print("  ★ 산문 속의 「%d장」 같은 말과 검산기 케이스 이름은 **사람이** 고친다."
          % int(old[2:]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
