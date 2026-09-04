# -*- coding: utf-8 -*-
"""과목이 **규칙이 바뀌기 전에 쓴 콘텐츠**를 아직 안 고쳤는지 — 전 과목을 훑어 후보만 낸다.

    python tools/audit_convention_drift.py
    python tools/audit_convention_drift.py --only=appsolids,appthermo
    python tools/audit_convention_drift.py --check=slide-mode

열린 날 2026-08-29. 원인 — 사용자 질문 [사용자 발화 인용 생략].
답은 «없었다»였다: `common_guard.py`는 공통 **파일**이 최신인지만 보고, 파일을 받은 뒤
**이미 써 둔 콘텐츠가 새 규칙에 맞는지**는 아무도 안 본다. 실사고 — 슬라이드모드 규격이
2026-08-18에 생겼는데 그 문서를 가리키는 줄은 2026-08-29 에야 AGENTS.md 에 들어갔고,
그 사이(8/18~8/29)에 만들어진 과목은 전부 구멍이 났다 — 한 과목이 그 첫 사례로 걸렸다.

★ **이 도구는 판정하지 않는다.** «figure 가 없다»가 곧 결함은 아니다 — 순수 대수 유도는
그림이 필요 없을 수 있다. 후보만 내고 사람이 챕터별로 본다(`audit_figure_balance.py`와 같은 태도).

★ **과목 이름을 박지 않는다.** 갈래 목록은 `git worktree list`, 과목 폴더는 `git ls-tree`로
찾는다 — `audit_subject_progress.py`와 같은 패턴이다(AGENTS 「공통 도구에 과목별 사실을
박지 않는다」). 새 과목이 생기거나 없어져도 이 파일을 안 고친다.

★ **`git show <갈래>:<경로>`로만 읽는다** — 남의 워크트리를 파일시스템으로 안 연다(반쯤 고친
상태를 정본으로 오인하는 사고를 구조적으로 막는다).

체크 목록(늘어날 수 있다 — 함수 하나 = 검사 하나):
  1. slide-mode  — `kind:"derivation"` 카드에 `figure` 키가 있는가(정본 2026-08-18 슬라이드모드 사양)
  2. fig-width   — 삽화 viewBox 폭이 640인가(정본 위 문서의 「viewBox 폭은 640으로」절, 2026-08-29 실측)
  3. hand-arc    — 각도 호가 `svg_arc_arrow.py`를 거쳤는가(습관 휴리스틱, 정확성은 빌드가 이미 잠근다)
  4. rate-dot    — 산문에 완성형 '닷 붙은 글자'(ṁ·Ẇ 등)가 날것으로 남아 있는가
                   (`tools/fix_rate_dot.py` 의 `convert()` 를 그대로 불러 쓴다 — 판정 로직을
                   두 벌 두면 갈린다. 2026-08-07 에 열렸는데 **빌드 lint 가 없어** 새로 쓰는
                   콘텐츠가 오늘도 재발할 수 있다 — 이 체크가 유일한 방지선이다)

★ **넷째 체크는 다른 셋과 성격이 다르다** — slide-mode·fig-width·hand-arc 는 "습관·스타일"
후보만 내지만, rate-dot 은 `fix_rate_dot.py` 가 이미 "고친다"고 정의해 둔 정확한 변환이 있다
(순수 함수 `convert()`). 그래서 이 체크의 히트는 **판정 불필요 — `python tools/fix_rate_dot.py
--chapter=chNN.json --apply` 를 그 과목 세션에서 돌리면 끝**이다.

새 체크를 추가할 때: 함수 이름을 `check_<이름>`으로, `CHECKS` 딕셔너리에 등록, 리턴은
`[(subject, chapter, item_id, 한줄사유), ...]` 리스트 하나로 통일한다.
"""
import json
import re
import subprocess
import sys

import fix_rate_dot

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def git(*args):
    """★ `core.quotepath=false` 가 필수다 — 과목 폴더가 전부 한글이다 (audit_subject_progress 와 동일 사고)."""
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") if r.returncode == 0 else ""


def branches():
    out = []
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("branch "):
            name = line.split("/")[-1].strip()
            if name and name != "main":
                out.append(name)
    return out


def subject_dir(branch):
    for line in git("ls-tree", "--name-only", branch, "data/").splitlines():
        name = line.strip().rstrip("/")
        if name and name != "data":
            return name
    return None


def chapter_files(branch, folder):
    names = [n.split("/")[-1] for n in
             git("ls-tree", "--name-only", branch, folder + "/").splitlines()
             if n.strip().endswith(".json") and "/ch" in n]
    return sorted(names)


def blob(branch, path):
    text = git("show", branch + ":" + path)
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


VIEWBOX_RE = re.compile(r"viewBox=['\"]\s*[-\d.]+\s+[-\d.]+\s+([\d.]+)\s+[-\d.]+")


def check_slide_mode(chapter, chapter_name):
    hits = []
    for f in (chapter.get("derivation") or {}).get("formulas") or []:
        if f.get("kind") != "derivation":
            continue
        if "figure" not in f:
            hits.append((chapter_name, f.get("id", "?"), "슬라이드 figure 없음(구식 카드 후보)"))
    return hits


def check_fig_width(chapter, chapter_name):
    hits = []

    def scan(collection, owner_prefix):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                svg = d.get("svg", "")
                m = VIEWBOX_RE.search(svg)
                if m and abs(float(m.group(1)) - 640) > 0.5:
                    hits.append((chapter_name, d.get("id", "?"),
                                 owner_prefix + " viewBox 폭 " + m.group(1) + " (640 아님)"))
            fig = item.get("figure")
            if isinstance(fig, dict):
                svg = fig.get("svg", "")
                m = VIEWBOX_RE.search(svg)
                if m and abs(float(m.group(1)) - 640) > 0.5:
                    hits.append((chapter_name, fig.get("id", "?"),
                                 owner_prefix + " 슬라이드 viewBox 폭 " + m.group(1) + " (640 아님)"))

    scan((chapter.get("theory") or {}).get("sections"), "theory")
    scan((chapter.get("derivation") or {}).get("formulas"), "derivation")
    scan(chapter.get("practice"), "practice")
    scan(chapter.get("problems"), "problems")
    return hits


HAND_ARC_RE = re.compile(r"[Aa]\s+[-\d.]")


def check_hand_drawn_arc(chapter, chapter_name):
    """각도 호를 `svg_arc_arrow.py` 없이 손으로 그렸을 가능성 — **정확성이 아니라 습관**을 잰다.

    정본 도구의 출력은 `A42.00 42.00 0 0 0 …`처럼 **`A` 뒤에 공백이 없다**(f-string 그대로
    이어붙인다). 손으로 쓴 arc 는 대개 `A 30 30 0 0 1 …`처럼 `A` 뒤에 공백이 있다 — 실사고
    (각도 25도를 손으로 잡았다가 화살촉에 다 먹혀 T자로 보였다, 2026-08-29)가 이 체크를 열었다.
    ★ 기하 정확성(접선 방향·화살촉 비례)은 `checks_svg.arc_arrowhead_issues`가 **이미 매 빌드
    때 잡는다** — 이 체크는 그것과 겹치지 않는다. 잡는 것은 "정확했는가"가 아니라
    "생성기를 거쳤는가"뿐이고, 손으로 써도 우연히 공백 없이 쓰면 못 잡는다(휴리스틱의 한계).
    """
    hits = []

    def scan(collection):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                if HAND_ARC_RE.search(d.get("svg", "")):
                    hits.append((chapter_name, d.get("id", "?"),
                                 "각도 호에 A 뒤 공백 — svg_arc_arrow.py 미사용 후보"))
            fig = item.get("figure")
            if isinstance(fig, dict) and HAND_ARC_RE.search(fig.get("svg", "")):
                hits.append((chapter_name, fig.get("id", "?"),
                             "각도 호에 A 뒤 공백 — svg_arc_arrow.py 미사용 후보"))

    scan((chapter.get("theory") or {}).get("sections"))
    scan((chapter.get("derivation") or {}).get("formulas"))
    scan(chapter.get("practice"))
    scan(chapter.get("problems"))
    return hits


def check_rate_dot(chapter, chapter_name):
    """산문에 완성형 닷 글자가 남아 있는가 — 판정 로직은 `fix_rate_dot.convert()` 그대로 재사용."""
    hits = []

    def scan(node, owner, item_id):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in fix_rate_dot.SKIP_KEYS:
                    continue
                scan(v, owner, item_id)
        elif isinstance(node, list):
            for v in node:
                scan(v, owner, item_id)
        elif isinstance(node, str):
            if fix_rate_dot.convert(node) != node:
                hits.append((chapter_name, item_id,
                             owner + " 필드에 닷 글자 날것 — fix_rate_dot.py 미적용 후보"))

    for item in (chapter.get("theory") or {}).get("sections") or []:
        scan(item, "theory", item.get("id", "?"))
    for item in (chapter.get("derivation") or {}).get("formulas") or []:
        scan(item, "derivation", item.get("id", "?"))
    for item in chapter.get("practice") or []:
        scan(item, "practice", item.get("id", "?"))
    for item in chapter.get("problems") or []:
        scan(item, "problems", item.get("id", "?"))
    return hits


CHECKS = {
    "slide-mode": check_slide_mode,
    "fig-width": check_fig_width,
    "hand-arc": check_hand_drawn_arc,
    "rate-dot": check_rate_dot,
}


def main():
    only = None
    which = None
    for flag in sys.argv[1:]:
        if flag.startswith("--only="):
            only = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}
        elif flag.startswith("--check="):
            which = {s.strip() for s in flag.split("=", 1)[1].split(",") if s.strip()}

    active = {k: v for k, v in CHECKS.items() if not which or k in which}
    if not active:
        sys.exit("알 수 없는 --check 값 — 후보: " + ", ".join(CHECKS))

    print("규칙 표류 후보 — " + ", ".join(active) + " (판정은 사람이, 이 자는 후보만 낸다)\n")

    total_by_check = {k: 0 for k in active}
    for branch in branches():
        if only and branch not in only:
            continue
        folder = subject_dir(branch)
        if not folder:
            continue
        files = chapter_files(branch, folder)
        subject_hits = {k: [] for k in active}
        for name in files:
            ch = blob(branch, folder + "/" + name)
            if not ch:
                continue
            chname = name.rsplit(".", 1)[0]
            for key, fn in active.items():
                subject_hits[key].extend(fn(ch, chname))

        any_hit = any(subject_hits.values())
        if not any_hit:
            continue
        print("-- " + branch + " (" + folder.split("/")[-1] + ") --")
        for key in active:
            hits = subject_hits[key]
            total_by_check[key] += len(hits)
            if not hits:
                continue
            print("  [" + key + "] " + str(len(hits)) + "건")
            for chname, item_id, why in hits[:12]:
                print("     " + chname + " " + item_id + " — " + why)
            if len(hits) > 12:
                print("     ... 외 " + str(len(hits) - 12) + "건")
        print()

    print("합계 — " + " · ".join(k + " " + str(v) + "건" for k, v in total_by_check.items()))
    print("※ 판정하지 않는다 — 순수 대수 유도처럼 그림이 필요 없는 카드도 있고, "
          "640 아닌 폭이 의도적인 삽화도 있을 수 있다. 후보를 사람이 챕터별로 본다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
