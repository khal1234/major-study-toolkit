# -*- coding: utf-8 -*-
"""CLI entrypoint for the static thermodynamics site builder."""
import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from buildlib.render import (  # noqa: E402
    ROOT,
    TEMPLATE,
    build_chapter,
    build_home,
    build_tables_page,
    copy_lab_pages,
    lint_viewer_css_comments,
    lint_viewer_setting_registry,
    viewer_rev,
)
from buildlib.review import (  # noqa: E402
    AUTO_UNSEEN_TAG,
    _head_sha as git_head,
    accept_review_baseline,
    baseline_move_findings,
    chapter_at_revision,
    has_review_baseline,
    marks_from_built_html,
    read_build_record,
    record_build,
    unacknowledged_swallows,
    unseen_baseline_stale,
)
from buildlib.checks_content import lint_chapter, resolve_review_prerequisites  # noqa: E402
from agent_preflight import run_preflight  # noqa: E402


def _say_ok(*parts):
    """통과한 장의 `[ok]` 줄. `--fail-only` 면 침묵한다.

    ★ 열린 날 2026-09-08. 실행 규율 12 는 *[발화 생략]* 라고 못 박아
    뒀는데 **빌드에는 그 깃발이 없었다.** 모르는 인자는 조용히 무시되므로 켰다고 믿는
    상태가 만들어진다 — 이 세션에서 실제로 한 번 속았다.

    실제 손해는 출력 길이다: 21과목 전 챕터를 돌면 `[ok]` 만 200줄이 넘고, 도구 결과가
    중간에서 잘리면 **실패 목록이 그 잘린 자리에 묻힌다**(실패를 보려고 빌드를 한 번 더
    돌리게 된다 — 전 과목 빌드는 이 리포에서 가장 비싼 명령 중 하나다).

    ★ **줄어드는 것은 「판정이 끝난 줄」뿐이다** — `[FAIL]`·`[warn/미해결]` 은 어떤
    깃발로도 안 줄어든다. 그 둘이 조용해지면 그건 완화이지 요약이 아니다(규칙 10 빨강).
    """
    if "--fail-only" not in sys.argv:
        print("[ok]", *parts)

SUBJECT_CONFIG = {
    "열역학": {
        "coverSub": "Cengel &amp; Boles 10판 ISE 기준 · Moran 보충.",
        # ★★ **2026-08-18 다시 켰다** — 사용자: *[발화 생략]*. 그 화면에 표 읽는 법 튜토리얼을 두라는 요청이라,
        #   꺼 두면 **아무도 못 가는 자리에 설명을 두는 꼴**이 된다.
        #   · 옛 판정(2026-08-06 *[발화 생략]* — 문풀·연습문제와 함께 숨김)의 근거는
        #     «검수 안 한 것을 내보내지 않는다» 였다. 그 근거는 2026-08-14 에 다른 과목들에서
        #     이미 뒤집혔다(*[발화 생략]*).
        #   · **되돌리는 법은 이 한 줄을 `False` 로** — 링크와 `tables.html` 생성이 함께 꺼진다.
        #   한 플래그가 두 자리를 모두 가리는 것이 요점이다 — 2026-07-28 에 링크만 게이트
        #   밖에 있어 공학수학 화면에 수증기 표가 떴던 사고가 그 반대 사례다.
        "steamTables": True,
    },
    "공학수학 1": {
        "coverSub": "Kreyszig 10판 기준 · 유튜브 부교재 보충.",
    },
    "동역학": {
        "coverSub": "Hibbeler 15판 (SI) 기준.",
    },
    # ★ 2026-08-14 사용자 판정으로 **다시 연다** — *[발화 생략]*.
    #   숨기던 근거(2026-08-06, *[발화 생략]*)가
    #   **다른 과목에도 똑같이 해당**하게 되면서 둘만 가리는 것이 기준이 아니게 됐다.
    #   게이트 자체는 그대로 살아 있다 — 다시 숨길 과목이 생기면 `"publish": False` 한 줄이면 된다.
    #   `publish` 는 **배포 번들(`deploy_all.py`)에서만** 본다 — 이 파일의 단독 빌드와
    #   로컬 사이드바(`deploy_all.local_course_tree`)는 애초에 영향을 안 받는다.
    #   `steamTables` 와 같은 자리다 — 과목별 표시 토글의 정본은 이 사전 하나다.
    "기계재료": {
        "coverSub": "재료과학과 공학 10판 기준 · 강의노트 중심.",
    },
    "고체역학": {
        "coverSub": "Gere·Goodno 정역학과 재료역학 (SI) 기준 · Beer 보충.",
    },
    "기계공작법": {
        "coverSub": "Kalpakjian·Schmid, Manufacturing Engineering and Technology (SI) 기준.",
    },
    "유체역학": {
        "coverSub": "Cengel·Cimbala 유체역학 4판 (SI) 기준.",
    },
    "응용열역학": {
        "coverSub": "Moran 8판 기준 · 9판 참조.",
        # ★ 2026-09-08 사용자 지적으로 켠다 — *[발화 생략]*.
        #   `data/응용열역학/tables/steam.json` 은 2026-09-06 에 이미 만들어 두고 **이 한 줄이
        #   없어서 아무도 못 가는 자리에 있었다.** 표를 만든 것과 문을 내는 것이 다른 일이다.
        #   ☐ 아직 Cengel 판이다 — 단위가 kPa 이고 압력 눈금도 열역학판 그대로이며, 냉매 표가
        #     한 장도 없다(물뿐). 그 둘은 `docs/2026-09-08-사용자-지적-인박스.md` 에 열려 있다.
        #     **먼저 켜는 판정은 사용자가 했다** — 물 표라도 갈 수 있는 것이 못 가는 것보다 낫다.
        "steamTables": True,
    },
    "응용고체역학": {
        "coverSub": "Gere, Statics and Mechanics of Materials (SI) 기준.",
    },
    "전기전자공학기초 및 실험": {
        "coverSub": "Rizzoni, Principles and Applications of Electrical Engineering 기준.",
    },
    "공학수학 2": {
        "coverSub": "Zill, Advanced Engineering Mathematics 기준.",
    },
    "행복한 삶과 가족": {
        "coverSub": "교재 없음 — 수업 노트로 정리한다.",
    },
    "기계요소설계": {
        "coverSub": "Shigley 기계설계 11판(ISE) 기준",
    },
    "시스템제어": {
        "coverSub": "Nise 6판 착수 · 8판 정식 필요시 별도 확보",
    },
    "계측공학": {
        "coverSub": "Figliola & Beasley 7판 기준",
    },
    "수치해석": {
        "coverSub": "Chapra & Clough, Applied Numerical Methods with Python 기준",
    },
    "열전달": {
        "coverSub": "Incropera 등 7판(ISV) 기준",
    },
    "응용유체역학": {
        "coverSub": "Munson 8판 임시 착수 · 9판 확보시 교체",
    },
    "진동공학": {
        "coverSub": "S.S. Rao Mechanical Vibrations 6판(SI) 기준",
    },
    "스마트생산시스템": {
        "coverSub": "Groover 4판(2016 Global) 기준 · 8~14주 대응장 미확정",
    },
    "품질 및 신뢰성공학개론": {
        "coverSub": "Montgomery 7판 임시 착수 · 8판 확보시 교체",
    },
}

# ── 학기·분류 — 홈이 묶는 축 (신설 2026-08-15, 사용자 지시) ──────────────────
#
# *[발화 생략]* · *[발화 생략]*
#
# ★ **왜 여기인가.** 이건 «그 과목을 화면에서 어떻게 묶어 보여줄까» 라는 **표시 판정**이고,
#   이 리포에서 그 정본은 `SUBJECT_CONFIG` 하나다(`steamTables`·`publish` 와 같은 자리).
#   과목 `index.json` 의 `semester` 는 **집필 규칙**(앞 학기 개념은 가볍게 되짚는다)의 것이라
#   소비자가 다르다 — 둘 다 두되 **어긋나면 회귀가 잡는다.**
# ★ **표 하나로 적고 위 사전에 합친다.** 항목마다 두 줄씩 흩뿌리면 새 과목이 생긴 날
#   한쪽만 적히고, 그게 이 리포가 반복해 겪은 부류다.
# ★★ **교양 판정의 근거는 강의계획서의 이수구분이고, 실물로 확인했다** (2026-08-15).
#   `행복한 삶과 가족` → **`CLTR0703-001` · 교과구분 교양**
#   `기계공작법`(대조군) → **`MECH0359-002` · 교과구분 전공**
#   강의계획서는 **교재 폴더**에 과목마다 있다(`<교재 폴더>/2. 전공과목/<학기>/<과목>/`).
#   읽는 법은 `python tools/extract_textbook.py --pdf <경로> --pages 1-1`.
# ★★★ **처음에 «리포에 없어 확인 불가» 라고 적었다가 정정했다.** 리포만 훑고 «0건» 을 냈는데
#   교재 폴더는 **읽기 허용 범위 안**이었다 — 규칙 11 이 말하는 *«범위를 확인하지 않은 0건은
#   「없다」가 아니라 「거기까지는 없다」»* 를 그대로 저질렀다. 사용자가 *[발화 생략]* 로 짚어 줬다. **0건을 낼 때는 어디까지 봤는지 먼저 적는다.**
#   현재 교양은 **하나뿐이다**(사용자 확인: *[발화 생략]*).
_TAXONOMY = {
    "열역학": ("2-1", "전공"), "공학수학 1": ("2-1", "전공"), "동역학": ("2-1", "전공"),
    "기계재료": ("2-1", "전공"), "고체역학": ("2-1", "전공"),
    "기계공작법": ("2-2", "전공"), "유체역학": ("2-2", "전공"),
    "응용열역학": ("2-2", "전공"), "응용고체역학": ("2-2", "전공"),
    "전기전자공학기초 및 실험": ("2-2", "전공"), "공학수학 2": ("2-2", "전공"),
    "행복한 삶과 가족": ("2-2", "교양"),
    "기계요소설계": ("3-1", "전공"), "수치해석": ("3-1", "전공"),
    "진동공학": ("3-1", "전공"),
    "계측공학": ("3-1", "전공"),
    # 2026-09-07 — 합치자마자 드러난 미선언 5개. 학기는 짐작하지 않고 그 과목
    # `data/<과목>/index.json` 의 `semester` 를 그대로 옮겼다(어긋나면 회귀가 잡는다).
    # 분류는 전부 전공이다 — 교양은 「행복한 삶과 가족」 하나뿐인 것이 사용자 확인 사실이다.
    "시스템제어": ("3-1", "전공"), "열전달": ("3-1", "전공"),
    "응용유체역학": ("3-1", "전공"),
    "스마트생산시스템": ("4-1", "전공"),
    "품질 및 신뢰성공학개론": ("4-2", "전공"),
}
for _name, (_sem, _cat) in _TAXONOMY.items():
    SUBJECT_CONFIG.setdefault(_name, {}).update(semester=_sem, category=_cat)

# ── 「과목→로컬 포트」 — 이제 **홈 한 장**만 쓴다 ──────────────────────────
#
# 로컬에서 과목은 **워크트리마다 다른 포트**로 뜬다(thermo 8801 · math 8802 …). 그래서
# `열역학/ch01.html` 같은 상대 주소는 **자기 과목에서만** 맞고 남의 과목은 폴더가 아예 없다.
# **포트의 정본은 `tools/serve_site.vbs` 하나다** — 여기서 사본을 만들지 않고 그것을 읽는다.
#
# ★★ **소비자가 바뀐 자리다 (2026-08-15).** 이 배선은 원래 **사이드바**가 남의 과목으로
#   링크하려고 있었고, 사이드바를 «이 과목만» 으로 좁히면서 그날 함께 걷어냈다.
#   그런데 같은 날 사용자가 *[발화 생략]* 라고 **홈**을 짚었다 —
#   필요가 사라진 것이 아니라 **자리가 옮겨진 것**이었다.
#   ★ 그래서 되살리되 **범위가 완전히 다르다:** 예전엔 **장마다**(300장) 포트 맵이 실렸고
#     지금은 **홈 한 장**의 링크에만 박힌다. 즉 «기능이 죽으면 배선도 죽인다» 는 그대로 옳았고,
#     되살아난 것은 죽은 기능이 아니라 **다른 기능의 필요**다.
# ★ 배포 번들의 홈은 이것을 안 쓴다 — 거기서는 한 사이트에 전 과목이 있어 상대 주소가 맞다.
SERVE_VBS = os.path.join(ROOT, "tools", "serve_site.vbs")
sys.path.insert(0, os.path.join(ROOT, ".claude", "hooks"))
from guard_bash import SUBJECT_BY_BRANCH  # noqa: E402  — 브랜치→과목(포트 맵을 과목으로 옮긴다)

VBS_PORT_RE = re.compile(r'Case\s+"([a-z0-9]+)"\s*\r?\n\s*port\s*=\s*(\d+)')


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def local_ports(vbs_text, subject_by_branch, subject_names):
    """**언제나 빈 맵** — 과목마다 다른 포트가 없어졌다 (2026-09-06 구조 이전).

    옛 뜻: `serve_site.vbs` 의 브랜치→포트 표를 「과목 폴더 이름→포트」로 옮겨, 로컬에서
    다른 과목으로 가는 링크를 `http://localhost:<그 과목 포트>/…` 로 바꿔치기했다.
    그 치환이 필요했던 이유는 **과목마다 워크트리가 따로여서 서로의 파일이 없었기** 때문이다.

    21개 브랜치를 main 하나로 합친 뒤에는 `site/` 안에 전 과목이 함께 있어 **상대경로가
    그대로 맞는다** — 치환할 것이 없다. 빈 맵을 주면 호출부(링크 렌더)가 상대경로를 그대로
    쓰므로 로컬·배포가 같은 경로로 동작한다. 함수를 남겨 둔 것은 호출부와 회귀가 이 이름을
    쓰기 때문이고, 여기서 «이제는 안 바꾼다» 를 한 자리에 못 박아 둔다.
    """
    return {}


def is_placeholder(ch):
    """아직 안 쓴 장인가 — `{"placeholder": true}`. **순수 함수, 테스트가 직접 부른다.**

    표식은 `data/품질 및 신뢰성공학개론/ch08.json` 이 2026 여름에 이미 쓰고 있었는데
    **읽는 자가 하나도 없었다**(2026-09-07 실측: `tools/` 전수 grep 0건). 표식만 있고
    읽는 자가 없으면 그건 사람에게만 보이는 주석이다 — 이 리포가 여러 번 닫은 부류다.
    """
    return isinstance(ch, dict) and ch.get("placeholder") is True


def _is_placeholder(ch_path):
    try:
        with open(ch_path, encoding="utf-8") as fh:
            return is_placeholder(json.load(fh))
    except Exception:                                                   # noqa: BLE001
        return False                       # 못 읽는 것은 자리표가 아니라 결함이다


def lint_baseline(baseline, ch_path, rev):
    """리뷰 기준선(과거 시점 스냅샷)의 lint — **실패해도 빌드를 멈추지 않는다.**

    열린 날 2026-07-27. `--accept-review-rev=<과거 sha>`로 기준선을 옮기려 했더니
    **그 과거 데이터가 오늘 규칙에 걸려** 빌드가 죽었다(유니코드 첨자 24건 — 방금 우리가 고친 바로 그것들).

    구조적 모순이다: 검사를 새로 하나 추가할 때마다 **그보다 오래된 기준선은 영영 못 잡게 된다.**
    그런데 이 플래그의 존재 이유가 정확히 *[발화 생략]* 다 —
    기준선이 낡을수록 필요하고, 낡을수록 못 잡히는 셈이었다. 사용자 지적:
    *[발화 생략]* 가 이 구조 때문이다.

    기준선은 **텍스트 비교용 참조일 뿐 화면에 나가지 않는다**(HTML로 빌드되는 것은 현재 파일이다).
    그러니 과거 데이터의 위반은 고칠 수도 없고 고칠 필요도 없다. 알리되 막지 않는다.
    현재 파일은 아래에서 `lint_chapter`가 그대로 strict하게 본다 — 그 경로는 손대지 않았다.
    """
    try:
        lint_chapter(baseline, ch_path)
    except ValueError as exc:
        print("[review baseline lint 무시]", rev, os.path.relpath(ch_path, ROOT),
              "— 과거 시점 데이터라 오늘 규칙에 걸릴 수 있다(비교용 참조일 뿐 화면에 안 나감):",
              str(exc).rsplit(": ", 1)[-1])


def review_hold(idx, accepting):
    """기준선을 밀려는데 그 과목이 **검수 보류**를 선언했으면 그 선언을 돌려준다 (2026-08-13).

    판정을 `main()` 이 아니라 여기 두는 이유는 `guard_bash.deny_reason` 과 같다 —
    **테스트가 볼 수 있어야** 규칙이 잠긴다. 잠금 `test_review_hold_blocks_baseline_move`.
    """
    return (idx.get("reviewHold") or None) if accepting else None


def review_unseen(idx, chapter_file):
    """사용자가 **아직 안 본 장**인가 — 그렇다면 빌드가 기준선을 HEAD 로 유지한다 (2026-09-18).

    `reviewSeen` = `{"chNN": "<근거: 날짜 · 사용자 지적/[발화 생략]>"}`. 선언 밖 장은 안 본 장이다.
    판정선: 사용자 *[발화 생략]* — 변경점은 본 장에만 뜬다. 보류(`reviewHold`)가 있으면 보류가 이긴다.
    선언이 없는 과목은 `None` — 잠금 `test_review_marks_only_on_seen_chapters` 가 선언을 강제한다.
    """
    seen = idx.get("reviewSeen")
    if not isinstance(seen, dict):
        return None
    if idx.get("reviewHold") or "*" in seen:
        return False
    return os.path.splitext(chapter_file)[0] not in seen


def accept_target(ch_path, as_built, rev, head):
    """이 챕터의 기준선을 **어느 커밋에서** 뜰 것인가 — `(rev, 작업트리인가)` (2026-08-13).

    `--accept-review` 는 **작업 트리**를 그대로 기준선으로 삼는다(내용 = HEAD + 미커밋 변경).
    그래서 창의 끝은 HEAD 이고, 미커밋 변경이 있으면 그 자체가 삼킴이다(`uncommitted`).
    """
    if as_built:
        return (read_build_record(ch_path).get("rev") or ""), False
    if rev:
        return rev, False
    if head:
        return "HEAD", False
    return "HEAD", True


def print_swallow_block(unacked):
    """거부 출력 — **무엇을 삼키는지와 푸는 법**을 화면에 낸다 (2026-08-13).

    출력만 하고 넘어가면 다음 세션이 그 줄을 안 읽는다. 그래서 `main()` 은 이 출력을 낸 뒤
    **아무것도 밀지 않고 exit 1** 한다 — 되돌리기가 비싸기 때문이다(스냅샷은 git 밖이라
    삼킨 것을 되살리려면 과거 sha 를 찾아 다시 수락하는 수밖에 없다).
    """
    print("[기준선 이동 거부] 사용자가 못 본 것이 삼켜진다 — 아무 기준선도 밀지 않았다.")
    by_chapter = {}
    for rel, kind, sha, note in unacked:
        by_chapter.setdefault(rel, []).append((kind, sha, note))
    for rel, rows in sorted(by_chapter.items()):
        record = read_build_record(os.path.join(ROOT, rel))
        built = str(record.get("rev") or "(기록 없음)")
        commits = [row for row in rows if row[0] == "commit"]
        print("  %s — 마지막 빌드 %s%s%s"
              % (rel, built[:7], (" (" + str(record.get("at")) + ")") if record.get("at") else "",
                 (" 이후 이 챕터로 들어온 커밋 %d개" % len(commits)) if commits else ""))
        for kind, sha, note in rows:
            print("      " + (sha[:7] + "  " if sha else "[" + kind + "] ") + note)
        if commits:
            print("      → 이 수정들은 사용자 화면에 **변경점 표시 없이** 반영된다.")
            print("      푸는 법 ⑴ 사용자가 본 화면 시점으로 민다: --accept-review-as-built")
            print("      푸는 법 ⑵ 사용자가 이미 봤으면 명시한다: --accept-review-user-saw="
                  + ",".join(sha for _k, sha, _n in commits))
            history = record.get("history") or []
            if history:
                print("      (그보다 옛 화면이었으면 그 sha 로 민다 — 최근 빌드: "
                      + ", ".join(str(h.get("rev"))[:7] for h in history[:5]) + ")")
        if any(kind == "unbuilt" for kind, _s, _n in rows):
            print("      → 먼저 python tools/build_site.py --all --quiet 로 빌드한 뒤 민다"
                  " — 승인 플래그로는 못 푼다(무엇을 봤는지 관측이 없다).")
        if any(kind in ("dirty", "uncommitted") for kind, _s, _n in rows):
            print("      → python tools/commit.py 로 커밋하고 다시 빌드한 뒤 민다"
                  " — 승인 플래그로는 못 푼다(화면이 어느 커밋과도 같지 않다).")


#: 전 장을 통틀어 «같은 부류» 가 몇 번 나왔는지 — 챕터 순서대로 쌓인다.
#  화면에는 전역 상태가 없어서(챕터 HTML 은 서로 독립) 빌드가 세어 넣는다.
#  `render.build_chapter` 가 읽고(앞 장까지의 수) 쓴다(이 장의 수를 더한다).
REVIEW_NOTE_SEEN = {}


def build_and_record(template, subject, cfg, ch_path, chapter_nav, review_enabled,
                     course_tree, local_ports=None):
    """챕터를 빌드하고 **그 빌드가 어느 커밋 시점인지** 남긴다 (2026-08-13).

    기록을 이 한 곳에서만 하는 이유: 호출부가 둘(수락 대상 / 그 밖)이라 각자 적으면 한쪽이
    빠지고, 빠진 챕터는 *[발화 생략]* 가 되어 그 다음 수락이
    통째로 막힌다. 트리거를 **반드시 하는 일**(빌드)에 건다 — AGENTS 「방지장치의 트리거」.
    """
    out, mirror = build_chapter(template, subject, cfg, ch_path, chapter_nav, review_enabled,
                                course_tree, note_seen=REVIEW_NOTE_SEEN, local_ports=local_ports)
    record_build(ch_path)
    return out, mirror


def _accept_scope(only, sections, formulas):
    """수락 **범위**를 출력에 적는다 (2026-08-07).

    예전 출력은 `only=` 만 찍었다 — `--accept-review-section` 으로 좁혀 수락해도 화면에는
    범위가 **한 글자도 안 나왔다.** 부분 수락은 되돌리기 어려운데(스냅샷은 git 밖이다)
    무엇을 수락했는지 로그에 남지 않으면 나중에 대조할 근거가 없다.
    """
    for label, value in (("only", only), ("section", sections), ("formula", formulas)):
        if value:
            return " " + label + "=" + ",".join(value)
    return ""


def main():
    if run_preflight() != 0:
        return 1
    build_all = "--all" in sys.argv
    accept_review = "--accept-review" in sys.argv
    accept_review_head = "--accept-review-head" in sys.argv
    # --accept-review-rev=<sha>: 기준선을 임의 커밋으로 잡는다 (2026-07-27 신설 —
    # "이번 개편 직전 대비 하이라이트"처럼 HEAD도 현재 파일도 아닌 시점이 필요할 때).
    accept_review_rev = next((a.split("=", 1)[1] for a in sys.argv
                              if a.startswith("--accept-review-rev=")), None)
    # --accept-review-only=theory,derivation,practice: **본 데까지만** 기준선을 수락한다
    # (2026-07-30 신설). 전체 수락은 아직 안 본 뒷부분의 변경 표시까지 지워 버린다 —
    # 자세한 경위는 buildlib/review.accept_review_baseline 독스트링.
    accept_review_only = next((a.split("=", 1)[1] for a in sys.argv
                               if a.startswith("--accept-review-only=")), None)
    accept_review_only = ([s.strip() for s in accept_review_only.split(",") if s.strip()]
                          if accept_review_only else None)
    if accept_review_only:
        accept_review = True
    # --accept-review-section=sec-a,sec-b: 수락 단위를 **이론 절**까지 좁힌다 (2026-08-06).
    # 사용자: *[발화 생략]* — 아직 도달하지 않은
    # 절의 표시는 대조할 기억이 없어 잡음이다. 컬렉션 단위(`--accept-review-only`)로는 못 한다:
    # theory 를 통째로 수락하면 **이미 본 앞 절의 표시까지 지워진다**.
    accept_review_section = next((a.split("=", 1)[1] for a in sys.argv
                                  if a.startswith("--accept-review-section=")), None)
    accept_review_section = ([s.strip() for s in accept_review_section.split(",") if s.strip()]
                             if accept_review_section else None)
    if accept_review_section:
        accept_review = True
    # --accept-review-formula=f-a,f-b: 수락 단위를 **유도 카드**까지 좁힌다 (2026-08-07).
    # 사용자: *[발화 생략]*
    # 유도는 카드를 한 장씩 넘기며 보는데 수락 단위가 컬렉션까지밖에 없어서, 앞 두 장을
    # 봤다고 말해도 **전부 수락(뒷 카드 표시까지 소실)이냐 아무것도 안 하느냐** 둘뿐이었다.
    # 2026-08-06 에 이론에서 닫은 것과 같은 부류다 — 그때 단위를 **이론에만** 내려서 다시 열렸다.
    accept_review_formula = next((a.split("=", 1)[1] for a in sys.argv
                                  if a.startswith("--accept-review-formula=")), None)
    accept_review_formula = ([s.strip() for s in accept_review_formula.split(",") if s.strip()]
                             if accept_review_formula else None)
    if accept_review_formula:
        accept_review = True
    # --accept-review-chapter=ch01: 기준선 수락을 **그 챕터에만** 적용한다 (2026-07-30 신설).
    # 이게 없으면 `--accept-review` 가 전 챕터의 검수 상태를 한 번에 날린다 — 아직 안 본
    # 다른 챕터의 변경 표시까지 사라지고, 스냅샷은 git 밖이라 되돌릴 방법도 마땅치 않다.
    # 빌드 자체는 계속 전 챕터를 돈다(사이트가 갈라지면 안 된다) — 수락 범위만 좁힌다.
    accept_review_chapter = next((a.split("=", 1)[1] for a in sys.argv
                                  if a.startswith("--accept-review-chapter=")), None)
    # --accept-review-subject=<과목 폴더>: 수락을 **그 과목**에만 적용한다 (2026-09-13 신설).
    #   평탄화 뒤 한 트리에 21과목이 있어 `ch07` 은 열 과목에 있다 — 챕터 이름만으로는 한 과목을
    #   못 고르고, 다른 과목의 `reviewHold` 가 이 과목의 수락을 막는다(실측: 공학수학 2 ch07 복구를
    #   기계공작법·수치해석 보류가 차례로 막았다). 없으면 옛날처럼 전 과목의 그 챕터가 대상이다.
    accept_review_subject = next((a.split("=", 1)[1] for a in sys.argv
                                  if a.startswith("--accept-review-subject=")), None)

    def accept_covers(subject, entry_file):
        """이번 수락이 (과목, 챕터 파일)을 덮는가 — 보류 게이트·삼킴 게이트·수락 루프가 같은 자를 쓴다."""
        if accept_review_subject and subject != accept_review_subject:
            return False
        if accept_review_chapter and os.path.splitext(entry_file)[0] != accept_review_chapter:
            return False
        return True
    # ★★ --accept-review-as-built: 기준선을 **사용자가 마지막으로 본 화면**의 커밋으로 잡는다
    #   (2026-08-13 신설). *[발화 생략]* 의 기준은 **시각이 아니라 커밋**이다 — 검수 중에 들어온
    #   수정은 그 사람 화면의 변경점 목록에 애초에 없다. 그 sha 는 빌드가 남긴다
    #   (`.review-snapshot/chNN.built.json` · buildlib/review.py 「빌드 시점 기록」이 정본).
    #   그 사이 커밋이 없으면 HEAD == 빌드 sha 라 `--accept-review-head` 와 결과가 같다.
    accept_review_as_built = "--accept-review-as-built" in sys.argv
    # --accept-review-user-saw=<sha,…>: 삼켜질 커밋을 **사람이 명시로** 승인한다.
    #   플래그 없이 조용히 넘어가는 길은 만들지 않는다 — 경고는 경고 더미에 묻히고, 이 건은
    #   사용자가 **신뢰의 문제**로 말했다(*[발화 생략]*).
    accept_review_user_saw = next((a.split("=", 1)[1] for a in sys.argv
                                   if a.startswith("--accept-review-user-saw=")), None)
    accept_review_user_saw = ([s.strip() for s in accept_review_user_saw.split(",") if s.strip()]
                              if accept_review_user_saw else None)
    review_enabled = os.environ.get("REVIEW_HIGHLIGHTS", "1") != "0"
    template = open(TEMPLATE, encoding="utf-8").read()
    lint_viewer_css_comments(template)
    lint_viewer_setting_registry(template)
    data_root = os.path.join(ROOT, "data")
    # ★ 과목이 없는 워크트리(main = 공통 정본)에서는 **실패가 아니라 「해당 없음」이다**
    #   (신설 2026-08-16). 예전에는 `os.listdir` 이 FileNotFoundError 로 죽어서 exit 1 이 났고,
    #   그러면 배치와 사람 둘 다 **«빌드가 깨졌다»** 로 읽는다 — 실제로는 잴 콘텐츠가 없을 뿐이다.
    #   AGENTS 「알려진 함정」의 *[발화 생략]* 와 같은 자리이고,
    #   `test_checks.py --fail-only` 가 같은 상황에서 이미 `[해당 없음]` 을 찍고 exit 0 이다.
    #   ★ 조용히 넘어가지 않는다 — **한 줄로 찍는다.** 안 찍으면 «안 돈 것»과 «통과한 것»이 같아진다.
    if not os.path.isdir(data_root):
        print("[해당 없음] 이 워크트리에는 data/ 가 없다(공통 정본) — 빌드할 과목 0개")
        print("            콘텐츠 빌드는 각 과목 워크트리에서 돈다.")
        return 0
    built = []
    build_failures = []          # (챕터 상대경로, 마지막 오류 줄) — 끝까지 돌고 한 번에 낸다
    # ★ 기본 빌드가 **건너뛴** 챕터 (신설 2026-08-12). 아래 마지막에 한 줄로 알린다 —
    #   왜 필요한지는 그 자리 주석이 정본이다.
    skipped_todo = []
    home_subjects = []
    subjects_meta = []
    for subject in sorted(os.listdir(data_root)):
        idx_path = os.path.join(data_root, subject, "index.json")
        if not os.path.isfile(idx_path):
            continue
        cfg = SUBJECT_CONFIG.get(subject)
        if cfg is None:
            print("[skip] subject not in SUBJECT_CONFIG:", subject)
            continue
        idx = json.load(open(idx_path, encoding="utf-8"))
        chapter_nav = []
        for entry in idx.get("chapters", []):
            source_path = os.path.join(data_root, subject, entry["file"])
            if os.path.isfile(source_path):
                chapter_nav.append({
                    "number": entry["chapterNumber"],
                    "title": entry["chapterTitle"],
                    "status": entry.get("status", "todo"),
                    "href": "ch" + str(entry["chapterNumber"]).zfill(2) + ".html",
                    "labs": entry.get("labs", []),
                })
        home_subjects.append({
            "name": subject,
            "coverSub": cfg.get("coverSub", ""),
            # 홈이 묶는 축은 **표시 판정**이라 `SUBJECT_CONFIG` 가 정본이다(위 `_TAXONOMY`).
            "semester": cfg.get("semester", ""),
            "category": cfg.get("category", ""),
            "chapters": chapter_nav,
            "labs": [
                dict(lab, chapterNumber=entry["chapterNumber"],
                     chapterTitle=entry["chapterTitle"])
                for entry in idx.get("chapters", [])
                for lab in entry.get("labs", [])
            ],
        })
        subjects_meta.append((subject, cfg, idx, chapter_nav))

    # 사이드바 아코디언용 전체 과목 트리 — 모든 챕터 페이지에 동일하게 주입한다.
    course_tree = []
    for subject, cfg, idx, chapter_nav in subjects_meta:
        chaps = []
        for entry in idx.get("chapters", []):
            source_path = os.path.join(data_root, subject, entry["file"])
            if not os.path.isfile(source_path):
                continue
            num = entry["chapterNumber"]
            fname = "ch" + str(num).zfill(2) + ".html"
            already = os.path.isfile(os.path.join(ROOT, "site", subject, fname))
            chaps.append({
                "number": num,
                "title": entry["chapterTitle"],
                "status": entry.get("status", "todo"),
                "fname": fname,
                "built": build_all or entry.get("status") == "done" or already,
            })
        course_tree.append({"name": subject, "chapters": chaps})

    # ★ 통합 배포에서는 전 과목 트리를 주입받는다 (2026-07-26).
    # 과목 = 브랜치 = worktree라 이 워크트리의 data/ 에는 자기 과목뿐이다. 그래서 위 루프만으로는
    # 사이드바에 과목이 하나만 들어가고, 뷰어가 이미 구현해 둔 '과목별 접기 + 다른 과목으로 이동'이
    # 화면에 나타날 수 없었다(사용자 지적: 요구사항인데 실현이 안 돼 있다).
    # deploy_all.py가 모든 워크트리를 먼저 훑어 만든 트리를 이 환경변수로 넘긴다.
    # 로컬 단일 워크트리 빌드에서는 설정하지 않는다 — 다른 과목 HTML이 없어 링크가 404가 되기 때문.
    merged_tree = os.environ.get("MERGED_COURSE_TREE")
    if merged_tree and os.path.isfile(merged_tree):
        with open(merged_tree, encoding="utf-8") as fh:
            course_tree = json.load(fh)
    else:
        # ★ 로컬 빌드도 전 과목 트리를 쓴다 (2026-07-28, 사용자 지적으로 방침 전환).
        # 예전 주석은 *[발화 생략]* 였다.
        # 그런데 로컬에서 과목은 **워크트리마다 다른 포트**로 이미 떠 있다(serve_site.vbs).
        # 그러니 없는 것이 아니라 **주소가 다른 것**이고, 뷰어가 포트로 보내면 링크가 산다.
        # 실패해도 빌드를 막지 않는다 — 자기 과목만 담긴 트리로 조용히 되돌아간다.
        try:
            import deploy_all                       # 지연 임포트: deploy_all 이 이 모듈을 import 한다
            # trees_to_build — 리포 밖(Codex) 워크트리가 사이드바 제목을 선점하지 않게(2026-09-17).
            local_tree = deploy_all.local_course_tree(
                deploy_all.trees_to_build(deploy_all.worktrees()))
            if local_tree:
                course_tree = local_tree
        except Exception as exc:                    # noqa: BLE001 — 어떤 이유든 빌드는 계속한다
            print("[warn] 전 과목 트리 수집 실패, 자기 과목만 넣는다:", exc)

    # ★★ **홈은 로컬에서도 전 과목을 보여준다** (2026-08-15, 사용자 지적:
    #   *[발화 생략]*). 사이드바는 «이 과목만» 으로 좁혔지만
    #   **홈은 반대다** — 거기가 «나머지를 보러 가는 자리» 이기 때문이다(그래서 좁힐 수 있었다).
    #   위에서 이미 전 과목 트리를 모아 뒀으니 홈도 그것을 쓴다. 없으면 자기 과목만 남는다.
    #   ★ 링크는 **런타임에** 포트로 바뀐다(`build_home` 이 심는 스크립트) — 빌드 시점에 박으면
    #     같은 산출물이 배포에서 못 쓰인다. 사용자 확인: *[발화 생략]*.
    # ★ 「이 워크트리에 챕터가 있나」는 **남의 과목을 붙이기 전에** 센다 — 붙인 뒤에 세면
    #   전 과목 홈 때문에 언제나 참이 되어, 챕터 0개인 과목이 다시 «nothing to build» 로
    #   넘어진다(실측 2026-08-15: 붙이자마자 일곱 갈래가 그대로 빨간불로 돌아갔다).
    own_has_chapters = any(s.get("chapters") for s in home_subjects)
    if len(course_tree) > len(home_subjects):
        known = {s["name"] for s in home_subjects}
        for entry in course_tree:
            if entry["name"] in known:
                continue
            home_subjects.append({
                "name": entry["name"],
                "coverSub": SUBJECT_CONFIG.get(entry["name"], {}).get("coverSub", ""),
                "semester": SUBJECT_CONFIG.get(entry["name"], {}).get("semester", ""),
                "category": SUBJECT_CONFIG.get(entry["name"], {}).get("category", ""),
                "chapters": [dict(c, href=c.get("fname")) for c in entry.get("chapters", [])],
            })
        home_subjects.sort(key=lambda s: (s.get("semester") or "~", s["name"]))

    # 과목 간 딥링크·홈 카드가 함께 쓰는 「과목 폴더 이름 → 로컬 포트」 표. 한 번만 잰다 —
    # 소비자가 늘었다고(홈 → 챕터 본문) 계산까지 소비자 수만큼 반복할 이유는 없다.
    chapter_ports = local_ports(_read_text(SERVE_VBS), SUBJECT_BY_BRANCH,
                                [s["name"] for s in home_subjects])

    # ★★ 검수 보류 — 사용자가 *[발화 생략]* 라고 한 동안은 기준선을 못 민다 (신설 2026-08-13).
    #
    # 실사고: 2026-08-12 검수 배치에서 사용자가 *[발화 생략]* 라고 못 박았는데, 인박스의 [발화 생략] 7번에
    # *[발화 생략]* 이 **대기**로 적혀 있었고 세션을 닫으며 그것을 실행했다.
    # 그 결과 회차 1~12 의 수정 **84항목**이 화면에서 통째로 사라졌다(ch01 24·ch02 33·ch03 3·
    # ch04 5·ch05 17·ch06 2). 사용자가 다음 세션에 *[발화 생략]* 로 발견했다.
    #
    # 구조가 원인이다 — **보류는 채팅에만 있고 계획은 파일에 있었다.** 파일이 이긴다.
    # 그래서 보류를 **파일에 적고 기계가 읽게** 한다. 푸는 방법은 우회 플래그가 아니라
    # `index.json` 에서 `reviewHold` 를 **지우는 것**이다 — 그게 곧 사용자의 *[발화 생략]* 이고,
    # 지운 사실이 커밋 diff 에 남아 *왜 밀었나* 가 기록된다.
    accepting = bool(accept_review or accept_review_head or accept_review_rev
                     or accept_review_as_built)
    if accepting:
        for subject, cfg, idx, chapter_nav in subjects_meta:
            # `--accept-review-chapter=chNN` 이면 그 장이 없는 과목은 이번 수락과 무관하다 —
            # 그 과목의 보류로 다른 과목의 수락을 막으면 「과목 = 폴더」(2026-09-06 평탄화)에서
            # 어느 과목도 못 민다(실측 2026-09-13: 기계공작법 보류가 공학수학 2 ch07 복구를 막았다).
            if not any(accept_covers(subject, e["file"]) for e in idx.get("chapters", [])):
                continue
            hold = review_hold(idx, accepting)
            if hold:
                print("[기준선 보류]", subject, "— 기준선을 밀지 않았다.")
                print("  선언:", json.dumps(hold, ensure_ascii=False))
                print("  푸는 법: 사용자가 «다 봤어» 라고 하면 data/%s/index.json 의"
                      " reviewHold 를 지우고 다시 돌린다." % subject)
                return 1

    # ★★ 삼킴 게이트 — **사용자가 못 본 커밋**을 기준선이 조용히 먹지 못하게 막는다 (2026-08-13).
    #
    #   실사고: 사용자가 *[발화 생략]* 라고 한 **시각**의 HEAD 를 잡았는데, 그 10분 전에
    #   ch05 커밋 둘(4870d24·7408c6d)이 들어와 있었다. 둘 다 사용자가 요청해 고친 것인데
    #   기준선이 그 뒤로 잡혀 **변경점 표시가 아예 안 붙었다.**
    #   사용자: *[발화 생략]*
    #
    #   ★ 원인은 부주의가 아니라 **관측의 부재**다 — 기준선을 밀 때 무엇이 삼켜지는지 아무도
    #     세지 않았다. 그래서 ⑴ 빌드가 자기 시점을 남기고(`build_and_record`) ⑵ 그 시점과
    #     밀려는 시점 사이의 커밋을 **세어 출력하고** ⑶ 사람이 명시로 승인하지 않으면 **거부**한다.
    #   ★ 판정은 `unacknowledged_swallows` **한 곳**이다 — 여기 조건을 다시 적지 않는다.
    #   ★ 전수 판정을 **먼저** 돌리고 하나라도 걸리면 아무 챕터도 안 민다 — 부분 적용은
    #     되돌리기가 더 비싸다(스냅샷은 git 밖이다).
    swallow_by_chapter = {}
    if accepting:
        findings = []
        for subject, cfg, idx, chapter_nav in subjects_meta:
            for entry in idx.get("chapters", []):
                ch_path = os.path.join(data_root, subject, entry["file"])
                if not os.path.isfile(ch_path):
                    continue
                if not accept_covers(subject, entry["file"]):
                    continue
                target, working_tree = accept_target(ch_path, accept_review_as_built,
                                                     accept_review_rev, accept_review_head)
                rel = os.path.relpath(ch_path, ROOT).replace(os.sep, "/")
                rows = baseline_move_findings(ch_path, target, working_tree=working_tree)
                swallow_by_chapter[rel] = rows
                findings.extend((rel,) + row for row in rows)
        unacked = unacknowledged_swallows(findings, accept_review_user_saw)
        if unacked:
            print_swallow_block(unacked)
            return 1

    for subject, cfg, idx, chapter_nav in subjects_meta:
        for entry in idx.get("chapters", []):
            ch_path = os.path.join(data_root, subject, entry["file"])
            if not os.path.isfile(ch_path):
                continue
            rel = os.path.relpath(ch_path, ROOT).replace(os.sep, "/")
            # ★ 기준선 복구 — `reviewHold` 가 기준선 sha 를 선언했는데 스냅샷 파일이 없으면 그 커밋에서
            #   되살린다(2026-09-13 신설). `.review-snapshot/` 은 git 밖이라 폴더 이동(2026-09-06
            #   평탄화)으로 통째로 사라졌고, 없으면 변경점 0건으로 **조용히** 렌더된다. 보류가 적어 둔
            #   sha 가 곧 사용자가 마지막으로 인정한 기준선이므로 그것을 쓴다 — 밀기가 아니라 복원이다.
            hold_rev = (idx.get("reviewHold") or {}).get("baseline")
            if hold_rev and not has_review_baseline(ch_path):
                base = chapter_at_revision(ch_path, hold_rev)
                if base is None:
                    print("[기준선 복구 건너뜀]", rel, "—", hold_rev, "에 이 장이 없다")
                else:
                    accept_review_baseline(ch_path, resolve_review_prerequisites(base, ch_path),
                                           only=None, baseline_rev=hold_rev,
                                           viewer_rev=viewer_rev(template))
                    print("[기준선 복구]", rel, "←", hold_rev,
                          "(reviewHold 가 선언한 기준선인데 스냅샷이 없었다)")
            # ★ 안 본 장은 기준선을 HEAD 로 유지한다(`review_unseen` 독스트링). 이번 호출이 이 장을
            #   명시로 수락하는 중이면 그 수락이 맡는다.
            if (review_enabled and review_unseen(idx, entry["file"])
                    and not (accepting and accept_covers(subject, entry["file"]))
                    and unseen_baseline_stale(ch_path, viewer_rev(template))):
                head_base = chapter_at_revision(ch_path, "HEAD")
                if head_base is not None:
                    # lint 가 기준선을 정규화한다 — 빼면 삽화가 전부 바뀐 것으로 잡힌다(2026-09-18 실측)
                    head_base = resolve_review_prerequisites(head_base, ch_path)
                    lint_baseline(head_base, ch_path, "HEAD")
                    accept_review_baseline(ch_path, head_base, only=None,
                                           baseline_rev=AUTO_UNSEEN_TAG + (git_head() or "?"),
                                           viewer_rev=viewer_rev(template))
                    print("  [안 본 장 — 기준선 HEAD]", rel)
            if accepting and not accept_covers(subject, entry["file"]):
                # 이 챕터는 수락 대상이 아니다 — 기준선을 그대로 두고 빌드만 한다.
                if not build_all and entry.get("status") != "done":
                    continue
                out, mirror = build_and_record(template, subject, cfg, ch_path, chapter_nav,
                                               review_enabled, course_tree,
                                               local_ports=chapter_ports)
                built.append(out)
                _say_ok(os.path.relpath(out, ROOT), ("(+mirror)" if mirror else ""))
                continue
            # ★ 기준선을 뜰 커밋. `--accept-review-as-built` 면 **빌드가 남긴 시점**(= 사용자가
            #   본 화면)이고, 아니면 `--accept-review-rev=` 가 지정한 sha 다. 위 삼킴 게이트가
            #   이미 통과시킨 값이라 여기서 다시 판정하지 않는다.
            accepted_here = False
            this_rev = accept_review_rev
            if accept_review_as_built:
                this_rev = read_build_record(ch_path).get("rev")
            if this_rev:
                baseline = chapter_at_revision(ch_path, this_rev)
                if baseline is None:
                    print("[review baseline skipped]", this_rev, "has no",
                          os.path.relpath(ch_path, ROOT))
                else:
                    baseline = resolve_review_prerequisites(baseline, ch_path)
                    lint_baseline(baseline, ch_path, this_rev)
                    snapshot = accept_review_baseline(ch_path, baseline,
                                                     only=accept_review_only,
                                                     sections=accept_review_section,
                                                     formulas=accept_review_formula,
                                                     baseline_rev=this_rev,
                                                     viewer_rev=viewer_rev(template))
                    accepted_here = True
                    print("[review baseline", this_rev
                          + (" as-built" if accept_review_as_built else "") + "]",
                          os.path.relpath(snapshot, ROOT))
            elif accept_review_head:
                baseline = chapter_at_revision(ch_path, "HEAD")
                if baseline is None:
                    print("[review baseline skipped] HEAD has no", os.path.relpath(ch_path, ROOT))
                else:
                    baseline = resolve_review_prerequisites(baseline, ch_path)
                    lint_baseline(baseline, ch_path, "HEAD")
                    # ★ `only` 를 **여기에도** 넘긴다 (열린 날 2026-08-02, 실사고).
                    #   `--accept-review-head --accept-review-only=theory,derivation` 을 주면
                    #   `only` 가 조용히 무시돼 **아직 안 본 문풀·연습문제의 기준선까지** 통째로
                    #   수락됐다(실측: ch02 하이라이트 31/16 → 0/0). 기준선은 git 밖이라
                    #   되돌릴 길이 백업뿐이었다 — 실제로 백업에서 복원해야 했다.
                    #   플래그 조합이 **조용히 한쪽을 버리는 것**이 결함의 형태다.
                    snapshot = accept_review_baseline(ch_path, baseline,
                                                     only=accept_review_only,
                                                     sections=accept_review_section,
                                                     formulas=accept_review_formula,
                                                     viewer_rev=viewer_rev(template))
                    accepted_here = True
                    print("[review baseline HEAD" + _accept_scope(accept_review_only,
                                                                  accept_review_section,
                                                                  accept_review_formula) + "]",
                          os.path.relpath(snapshot, ROOT))
            elif accept_review:
                baseline = json.load(open(ch_path, encoding="utf-8"))
                baseline = resolve_review_prerequisites(baseline, ch_path)
                lint_chapter(baseline, ch_path)
                snapshot = accept_review_baseline(ch_path, baseline, only=accept_review_only,
                                                     sections=accept_review_section,
                                                     formulas=accept_review_formula,
                                                     viewer_rev=viewer_rev(template))
                accepted_here = True
                print("[review baseline" + _accept_scope(accept_review_only,
                                                         accept_review_section,
                                                         accept_review_formula) + "]",
                      os.path.relpath(snapshot, ROOT))
            # ★ 수락이 **무엇을 하는지**를 화면에 낸다 (2026-08-13). 예전 출력은 경로 한 줄뿐이라
            #   삼킨 커밋도, 앞으로 보일 변경도 화면에 안 나왔다 — 그 눈멂이 이 사고의 자리다.
            if accepted_here:
                eaten = [row for row in (swallow_by_chapter.get(rel) or []) if row[0] == "commit"]
                tail = (" — " + ", ".join(sha for _k, sha, _n in eaten)
                        + " (사용자가 봤다고 명시함)") if eaten else ""
                print("  [삼키는 커밋] %d개%s" % (len(eaten), tail))
            # ★ **자리표 파일은 「아직 안 쓴 장」이지 결함이 아니다** (2026-09-07).
            #   `{"placeholder": true, …}` 는 세션이 «여기에 장이 온다» 고 적어 둔 표식인데
            #   **아무 도구도 그 표식을 읽지 않아서** `--all` 빌드가 `KeyError: 'theory'` 로
            #   걸린 장으로 셌다. 그건 미완성이지 고칠 결함이 아니다 — 「대상이 아닌 것은
            #   실패가 아니다」(AGENTS 알려진 함정). 내용을 지어내 채우는 것은 빨강이다.
            if _is_placeholder(ch_path):
                skipped_todo.append(os.path.relpath(ch_path, ROOT))
                print("  [자리표] %s — 아직 안 쓴 장이다(placeholder). 건너뛴다."
                      % os.path.relpath(ch_path, ROOT))
                continue
            if not build_all and entry.get("status") != "done":
                skipped_todo.append(os.path.relpath(ch_path, ROOT))
                if accepted_here:
                    print("  [앞으로 보이는 변경] 셀 수 없다 — 이 챕터는 빌드를 건너뛰었다"
                          " (--all 로 다시 돌릴 것).")
                continue
            # ★★ **한 장이 걸려도 끝까지 돈다** (2026-09-06, 구조 이전).
            #   과목이 브랜치로 갈려 있던 동안에는 빌드가 그 과목 것만 돌아, 첫 실패에서
            #   멈춰도 잃는 것이 자기 과목뿐이었다. 한 트리로 합친 뒤에는 **한 과목의 밀린
            #   결함이 전 과목의 빌드를 막는다** — 실측(2026-09-06): 합친 직후 8과목 15장이
            #   걸렸고, 계측공학 한 장 때문에 나머지 20과목이 한 장도 안 나왔다.
            #   그래서 실패를 모아 두고 계속 돈다. **게이트는 그대로다** — 아래에서 하나라도
            #   있으면 exit 1 이고, 목록을 한 번에 낸다(고치고 다시 돌리기를 21번 하지 않는다).
            try:
                out, mirror = build_and_record(template, subject, cfg, ch_path, chapter_nav,
                                               review_enabled, course_tree,
                                               local_ports=chapter_ports)
            except Exception as exc:                                    # noqa: BLE001
                rel_bad = os.path.relpath(ch_path, ROOT)
                build_failures.append((rel_bad, str(exc).strip().splitlines()[-1]))
                print("[FAIL]", rel_bad, "— 걸렸다(계속 진행한다)")
                continue
            built.append(out)
            _say_ok(os.path.relpath(out, ROOT), ("(+mirror)" if mirror else ""))
            if accepted_here:
                # ★ 세는 쪽은 **빌드가 내놓은 것을 읽기만 한다**(marks_from_built_html) —
                #   여기서 다시 계산하면 화면과 갈라진다(review.marks_by_collection 주석).
                _built_ch, marks = marks_from_built_html(out)
                total = sum(len(ids) for ids in marks.values())
                print("  [앞으로 보이는 변경] %d항목%s"
                      % (total, "" if total else " — 밀었는데 볼 게 없다"))
    for _s, cfg, _i, _n in subjects_meta:
        if cfg.get("steamTables"):
            tables_out = build_tables_page(_s)
            _say_ok(os.path.relpath(tables_out, ROOT))
        for lab_out in copy_lab_pages(_s):
            _say_ok(os.path.relpath(lab_out, ROOT))
    # 포트 맵은 위에서 한 번 잰 chapter_ports 를 그대로 쓴다(배포 번들 홈은 `deploy_all` 이
    # 따로 만들고 안 넘긴다).
    home_out = build_home(home_subjects, chapter_ports)
    _say_ok(os.path.relpath(home_out, ROOT))
    if not built:
        # ★★ **챕터가 아직 없는 과목은 실패가 아니다** (고침 2026-08-15, `verify_all` 첫 실행이
        #   잡았다). 2-2 일곱 과목은 뼈대만 개설된 상태라 챕터가 0개인데, 그 빌드가 exit 1 을
        #   내고 있었다 — 전 갈래를 한 번에 재기 전까지 **아무도 그 빨간불을 본 적이 없다.**
        #   AGENTS 「대상이 아닌 과목은 실패가 아니다」가 바로 이 형태다: 대상이 없으면
        #   `[해당 없음]` 을 찍고 exit 0 이다(조용히 넘어가지 않되, 실패로 세지도 않는다).
        #   ★ **챕터가 있는데 하나도 안 빌드된 것**과는 다르다 — 그건 위의 필터가 걸러서
        #     이 자리에 오지 않는다(`--all` 없이 todo 만 남은 경우는 그 위에서 이미 알린다).
        if not own_has_chapters:
            print("[해당 없음] 이 과목에는 아직 챕터가 없다 — 빌드할 것이 0개다.")
            return 0
        print("nothing to build")
        return 1
    # ★★ 「all checks passed」 가 **안 본 챕터**를 감추지 않게 한다 (신설 2026-08-12).
    #   열린 날의 사고: `status: todo` 인 ch06 을 고친 뒤 기본 빌드를 돌리자
    #   `built 6 chapter(s), all checks passed` 가 나왔다. 그런데 `--all` 로는 3 error 로
    #   죽는다 — 기본 빌드가 그 챕터를 **아예 안 돌기 때문**이다. 회귀 2886케이스도 못 봤다
    #   (데이터 결함이라 테스트 대상이 아니다). 즉 **작업 중 확인 경로가 통째로 비어 있었다.**
    #   `close_report` 는 `--all` 을 쓰므로 세션을 닫을 때는 잡히지만, 그건 몇 시간 뒤다.
    #   ★ 트리거를 **반드시 하는 일**(빌드)에 건다 — *[발화 생략]*
    #     같은 규칙은 사람의 성실성에 기대는 것이고, 그 형태가 실패한 것이 이 사고다
    #     (AGENTS 「방지장치의 트리거는 내가 반드시 하는 일에 건다」).
    if skipped_todo:
        print("[주의] status 가 done 이 아니라 **건너뛴** 챕터 %d개 — %s"
              % (len(skipped_todo), ", ".join(skipped_todo)))
        print("       그 파일을 고쳤다면 `python tools/build_site.py --all` 로 확인할 것 —"
              " 아래 '통과' 는 이 챕터를 보지 않은 결과다.")
    # ★★ 실어 둔 웹폰트는 **부분집합**이라 «오늘 내용»에 묶여 있다 (신설 2026-08-13).
    #   새 낱말이 들어오면 그 글자만 두부가 되는데, **화면을 열어 보기 전에는 안 보인다** —
    #   빌드도 회귀도 통과한다. *[발화 생략]* 를 규칙으로 적어 두는
    #   형태는 사람의 성실성에 기대는 것이고, 이 리포가 여러 번 실패한 꼴이다.
    #   그래서 트리거를 **반드시 하는 일**(빌드)에 건다(AGENTS 「방지장치의 트리거」).
    #   ★ 웹폰트를 안 싣는 과목은 `site/fonts/corpus.json` 이 없어 조용히 지나간다 —
    #     선언이 곧 opt-in 이고, 「대상이 아닌 과목은 실패가 아니다」.
    try:
        from font_subset import missing_from_shipped_fonts          # noqa: E402
        gaps = missing_from_shipped_fonts()
    except Exception as exc:                                        # noqa: BLE001
        gaps = []
        print("[주의] 실어 둔 글꼴의 말뭉치를 대조하지 못했다:", exc)
    if gaps:
        print("[주의] 실어 둔 웹폰트에 **없는 글자** %d개 — %s"
              % (len(gaps), "".join(gaps[:40]) + ("…" if len(gaps) > 40 else "")))
        print("       그 글자는 독자 화면에서 폴백 글꼴로 그려진다."
              " `python tools/font_subset.py build …` 로 부분집합을 다시 만들 것"
              " (되만드는 법은 site/fonts/README.md).")
    if build_failures:
        print("\n**걸린 장 %d개 — 나머지 %d장은 만들었다.**" % (len(build_failures), len(built)))
        for rel_bad, why in build_failures:
            print("  · %-46s %s" % (rel_bad, why[:120]))
        print("\n한 장씩 고치려면: python tools/lint_chapter.py <그 경로>")
        return 1
    print("built", len(built), "chapter(s), all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
