# -*- coding: utf-8 -*-
"""세션 종료(/clear) 전 close 점검 — "진짜 닫혔는가"를 명령으로 답한다.

    python tools/close_report.py

**왜 이 도구가 있는가 (2026-07-22 사용자 지적):**
사용자가 "clear 해도 되냐"고 물었을 때 Claude가 *이전 실행 기억*으로 표를 만들어
"통과"라고 답했다. 그 시점에 실제로 돌린 명령은 git status 하나뿐이었다.
사람이 매번 5개 명령을 기억해 돌리는 절차는 결국 빠뜨린다 — 그래서 도구로 만든다.

점검 항목(전부 실제 실행 결과):
  1) 빌드 통과 여부 + 챕터별 경고 수
  2) 회귀 테스트 통과 여부 + 케이스 수
  3) PENDING_FIG_FIXES 잔량 (남아 있으면 그게 미완 명단)
  4) strict 승격이 안 끝난 챕터 (경고에 머문 검사 = 아직 막지 못함)
  4-b) **미선언 opt-in 승격 키** — 「선언 안 함」과 「해당 없음」을 가른다(아래 상수 블록이 정본)
  5) 커밋 안 된 변경

읽기 전용이 아니다 — 빌드가 site/** 를 쓴다.
"""
import ast
import os
import re
import subprocess
import sys

from verify_workorder import browser_block_record_issues, section

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STRICT_SETS = [
    ("글 밀도", "checks_content.py", "DENSITY_STRICT_CHAPTERS"),
    ("본문 표기", "checks_content.py", "PROSE_STYLE_STRICT_CHAPTERS"),
    ("halo 여백", "checks_content.py", "HALO_GAP_STRICT_CHAPTERS"),
    ("화살표 간격", "checks_content.py", "ARROW_CLEARANCE_STRICT_CHAPTERS"),
    ("삽화 lint", "checks_svg.py", "FIGURE_LINT_STRICT_CHAPTERS"),
]
GIT_STATUS_CMD = ["git", "-c", "core.quotepath=false", "status", "--short", "-uall"]

rows = []          # (항목, 상태, 근거)
blockers = []
hard_failures = []


def run(*cmd):
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


NOT_APPLICABLE = []      # «과목이 없어서 안 잰 것» — 세어서 끝에 찍는다
_NO_SUBJECT = None


class _NotApplicable(Exception):
    """이미 «해당없음» 으로 센 줄을 감싼 `try` 밖으로 빼내는 신호.

    ★ 일반 `Exception` 으로 빠져나가면 그 자리의 `except` 가 **«확인불가»** 로 다시 찍는다 —
      그러면 한 줄이 두 번 나오고, 둘 중 하나는 거짓말이다.
    """


def no_subject():
    """이 워크트리에 **과목 데이터가 없나** — 공통 정본 `main` 이 그렇다.

    ★★ **열린 날 2026-08-15.** 공통의 집이 컨테이너 루트로 옮겨 오면서 이 자를 `main` 에서
      돌리게 됐는데, 그날 표의 **미완 4줄 중 3줄이 전부 «data/ 가 없어서»** 였다 —
      빌드 실패 · 수치 검산 확인불가 · opt-in 39키 미선언. 결함이 아니라 **대상이 아닌 것**이다.
      그리고 가짜 미완이 셋이면 **진짜 하나가 거기 묻힌다.**
    ★ 그렇다고 **조용한 초록을 주면 안 된다.** 실제로 그때 `strict` 다섯 줄은 챕터가 0개라
      `전 챕터 error` 라고 찍고 있었다 — **공허한 참**이라 «안 잰 것»과 «통과한 것»이 화면에서
      같아 보였다. 그래서 상태를 **«해당없음»** 으로 따로 두고 끝에 **세어서** 밝힌다
      (`test_checks.needs_subject()` 와 같은 처방이고 이유도 같다).
    ★ 판정을 못 하면 **재는 쪽으로 넘어진다** — 반대로 넘어지면 과목이 멀쩡한 워크트리에서
      게이트가 통째로 조용해진다(그건 이 자를 없애는 것과 같다).
    """
    global _NO_SUBJECT
    if _NO_SUBJECT is None:
        try:
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import audit_content                                               # noqa: E402
            _NO_SUBJECT = not audit_content.CHAPTERS
        except ModuleNotFoundError:
            # ★ 공용 폴더 국소 분기(2026-09-11) — **미러 동기화가 이걸 두 번 지웠다**(전공정리
            #   원본엔 `tools/audit_content.py` 가 실재해 이 가지가 한 번도 안 걸려서다).
            #   파일 자체가 없는 것은 "판정 못 함"이 아니라 "대상이 아님"이다. 없으면
            #   `on_disk_chapters()` 가 같은 이유로 또 죽는다 — 되돌아오면 다시 붙인다.
            _NO_SUBJECT = True
        except Exception:                                  # noqa: BLE001 — 보고를 막지 않는다
            _NO_SUBJECT = False
    return _NO_SUBJECT


def skip_without_subject(label, why):
    """과목이 있어야 성립하는 줄이면 «해당없음» 으로 **세고** True 를 돌려준다."""
    if not no_subject():
        return False
    NOT_APPLICABLE.append(label)
    rows.append((label, "해당없음", why))
    return True


def on_disk_chapters():
    """이 워크트리에 **실재하는** 챕터 파일 이름 — 목록을 여기 박지 않는다.

    ★ 열린 날 2026-08-07 (기계재료). 여기엔 `CHAPTERS = ("ch01.json","ch02.json","ch03.json")`
    이 **박혀 있었다.** 공통 도구가 과목별 사실(챕터 목록)을 아는 것이라
    AGENTS 「공통 도구에 과목별 사실을 박지 않는다」 위반이고, 증상은 두 방향이다:

      ⑴ **덜 본다.** ch04 이후를 한 번도 안 보고 `전 챕터 error` 라고 찍는다.
         기계재료 ch04 는 마침 공통 목록에 들어 있어 **우연히 맞은** 판정이었다 —
         맞았다는 것과 확인했다는 것은 다르다(규칙 11).
      ⑵ **아무것도 안 본다.** ch01~ch03 이 아예 없는 과목(동역학 ch00·ch12~ch18)에서는
         그 세 이름이 공통 목록에 있다는 이유만으로 통과한다. 폴백이 있는 도구가
         *[발화 생략]* 를 *[발화 생략]* 으로 찍는 그 부류다.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import audit_content                                                       # noqa: E402
    return tuple(stem + ".json" for stem in audit_content.CHAPTERS)


def strict_leftovers(chapters, names, list_name):
    """`names` 로 승격되지 않은 챕터 — 판정은 **빌드가 쓰는 자**에 위임한다.

    승격 레지스트리는 두 벌이다(공통 `*_STRICT_CHAPTERS` + 과목 `index.json` 의
    `strictChapters`). 공통 목록만 보고 판정하면 **과목이 자기 선언으로 올린 챕터를
    '경고에 머물렀다' 고 오보한다** — 2026-08-02 이후 신설된 규격은 공통 목록을 두지 않는 것이
    정책이라(남의 과목 빌드를 멈추지 않으려고) 그 오보가 기본값이 된다.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import audit_content                                                       # noqa: E402
    from buildlib.checks_content import is_strict_chapter                      # noqa: E402
    key = list_name[: -len("_STRICT_CHAPTERS")].lower()
    return [c[:4] for c in chapters
            if not is_strict_chapter(os.path.join(audit_content.DATA, c), names, key)]


def read_set(module, name):
    """공용 폴더 국소 분기 — 없으면 `None`(호출부가 이미 `pending is None` 등으로 받는다).
    미러 동기화가 두 번 지웠다(전공정리 원본엔 이 파일이 실재한다)."""
    path = os.path.join(ROOT, "tools", "buildlib", module)
    if not os.path.isfile(path):
        return None
    body = open(path, encoding="utf-8").read()
    m = re.search(re.escape(name) + r"\s*=\s*(set\(\)|\{[^}]*\})", body)
    if not m:
        return None
    raw = m.group(1)
    return set() if raw == "set()" else set(re.findall(r'"([^"]+)"', raw))


# ─────────────────────────────────────────────────────────────────────────────
# ★ 미선언 opt-in 승격 키 — 「선언 안 함」과 「해당 없음」이 화면에서 똑같이 보이던 자리
#   (열린 날 2026-08-13. 고체역학 세션이 실측해 넘긴 제보가 정본이다):
#
#   > *[발화 생략]*
#
# **무엇이 새어나갔나.** 이 리포는 검사를 과목별로 승격한다(`data/<과목>/index.json` 의
# `strictChapters`). 설계 자체는 옳다 — 전 과목 error 로 박으면 남의 빌드가 멈춘다. 문제는
# **미선언이 아무 흔적도 남기지 않는 것**이다. 규칙 11 이 못 박은 그 부류다:
# *범위를 확인하지 않은 0건은 「없다」가 아니라 「거기까지는 없다」이다.*
# 이 리포는 같은 부류를 한 번 닫았는데(`pendingChapters` — 「보류와 망각을 가르는」 장치)
# **승격 키 자체가 없는 경우는 그 장치 밖**이었다. 열역학 `index.json` 의
# `_strictChapters_2026-08-07` 주석이 *[발화 생략]* 고
# 스스로 적고 있다 — 알고도 못 세던 자리라는 뜻이다.
#
# ★ **키 목록을 여기 박지 않는다.** `is_strict_chapter(...)` 호출부에서 **AST 로 뽑는다.**
#   손으로 적으면 검사가 늘 때마다 갈라지고, 갈라진 쪽은 조용하다 — `on_disk_chapters` 가
#   챕터 목록에 대해 이미 닫은 것과 같은 부류다. 정규식이 아니라 AST 인 이유: 호출이
#   여러 줄에 걸치고(`checks_content.py:5900`·`6540`) 세 번째 인자가 리터럴일 때만 키다.
#
# ★★ **모양을 가른다 — 미선언의 대가가 세 가지로 다르다.**
#     · `게이트` … `if is_strict_chapter(...): errors.extend(fn(ch))`
#                  → 미선언이면 **검사 함수가 아예 안 돈다.** 경고조차 없다.
#                    실례가 위 제보의 `theory_figures`(C37)다.
#     · `분기`  … `(errors if is_strict_chapter(...) else warnings).extend(fn(ch))`
#                  → 함수는 **돈다.** 위반이 있으면 경고로 뜨고, 그 경고는 이 도구의
#                    「경고 잔량」이 이미 blocker 로 세운다. 즉 0 은 **잰 0** 이다.
#     · `전달`  … 판정을 변수에 담아 아래 함수로 넘긴다 — 이 자는 거기까지 못 본다(미검증).
#
# ★ **막는 것은 게이트형뿐이다.** 분기형까지 막으면 이미 보이는 것을 두 번 세는 것이고,
#   경보 피로는 검사기를 죽인다(AGENTS 「감사 ↔ 빌드 검사 대응」이 *[발화 생략]* 고 내린 판정과 같은 자다). 미선언 전부는 **나열만** 한다 —
#   고체역학이 요청한 「목록 한 줄」이 그것이다.
#
# ★ **사유를 적는 자리는 그 과목의 `index.json`** 이다: `"strictWaivers": {"키": "사유"}`.
#   · `docs/` 는 공통이라 `sync_common` 이 전 과목에 옮긴다 — 한 과목의 「해당 없음」이
#     남의 과목까지 조용히 면제한다(`card-overlap-verdicts.json` 키에 챕터를 넣은 이유와 같다).
#   · `strictChapters`·`pendingChapters` 가 이미 그 파일에 있다. **같은 판정을 두 파일에
#     나눠 두면 갈라진다.**
#   · **사유 없는 줄은 예외로 안 친다** — `audit_orphan_checks.allowed()` 와 같은 규율.
#   · `pendingChapters` 에 이름이 올라 있으면 그것도 선언이다(보류). 망각과 가른다.
#
# 잠금: `test_checks.py::test_optin_strict_keys_are_visible`.
STRICT_WAIVER_FIELD = "strictWaivers"
_SHAPE_RANK = {"게이트": 0, "전달": 1, "분기": 2}       # 안 보이는 쪽이 이긴다


def _strict_calls(node):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and (getattr(n.func, "attr", None) or getattr(n.func, "id", None))
            == "is_strict_chapter"]


def strict_keys_in_source(text):
    """소스 한 벌에서 `{키: {shape, names}}` 를 뽑는다 — **파일 I/O 없는 순수 함수.**

    판정을 파일 읽기와 갈라 두는 이유는 `checks_content.strict_list_names_in` 과 같다:
    실데이터가 전부 통과하는 상태에서는 회귀 단언이 **공허하게 참**이 되므로, 새 키를 담은
    가짜 소스를 직접 먹여 봐야 *목록을 손으로 적지 않았다*는 것이 증명된다.

    `names` 는 공통 승격 목록의 **식별자 이름**(예: `FIGURE_LINT_STRICT_CHAPTERS`)이고,
    빈 튜플·`set()` 리터럴이면 `None` 이다 — 그것이 곧 **순수 opt-in** 이라는 뜻이다.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    gated = {id(c) for n in ast.walk(tree) if isinstance(n, ast.If)
             for c in _strict_calls(n.test)}
    branch = {id(c) for n in ast.walk(tree) if isinstance(n, ast.IfExp)
              for c in _strict_calls(n.test)}
    out = {}
    for call in _strict_calls(tree):
        if len(call.args) < 3:
            continue
        node = call.args[2]
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue                    # 변수로 넘기는 자리(이 도구 자신)는 키가 아니다
        shape = ("게이트" if id(call) in gated
                 else "분기" if id(call) in branch else "전달")
        names = call.args[1].id if isinstance(call.args[1], ast.Name) else None
        cur = out.setdefault(node.value, {"shape": shape, "names": names})
        if _SHAPE_RANK[shape] < _SHAPE_RANK[cur["shape"]]:
            cur["shape"] = shape        # 한 키가 여러 자리에 있으면 가장 안 보이는 모양으로
        cur["names"] = cur["names"] or names
    return out


def opt_in_strict_keys():
    """`tools/buildlib/**` 전부에서 키를 모은다 — **파일 목록도 박지 않는다.**

    `buildlib` 로 한정하는 이유: 검사가 사는 곳이 거기다. `test_checks.py` 는 가짜 키를 담은
    픽스처를 갖고 있고 이 파일 자신은 키를 **변수로** 넘기므로, 넓게 훑으면 있지도 않은
    규격이 미선언으로 뜬다(그 오보가 쌓이면 이 자리는 장식이 된다).
    """
    import glob
    merged = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "tools", "buildlib", "*.py"))):
        with open(path, encoding="utf-8") as fh:
            found = strict_keys_in_source(fh.read())
        for key, info in found.items():
            cur = merged.setdefault(key, dict(info))
            if _SHAPE_RANK[info["shape"]] < _SHAPE_RANK[cur["shape"]]:
                cur["shape"] = info["shape"]
            cur["names"] = cur["names"] or info["names"]
    return merged


def _resolve_common_names(ident):
    """공통 승격 목록을 이름으로 해석한다. 못 찾으면 **빈 집합**(폴백을 두지 않는다)."""
    if not ident:
        return frozenset()
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from buildlib import checks_content, checks_svg                            # noqa: E402
    for mod in (checks_content, checks_svg):
        if hasattr(mod, ident):
            return frozenset(getattr(mod, ident) or ())
    return frozenset()


def classify_coverage(n_strict, total):
    """세 갈래 — 순수 함수(테스트가 직접 부른다). 챕터가 0이면 잰 것이 없으므로 미선언이다."""
    if total and n_strict >= total:
        return "선언됨"
    return "부분" if n_strict else "미선언"


def strict_waiver_reasons(index_data):
    """`{키: 사유}`. **사유가 빈 줄은 예외로 치지 않는다** (`audit_orphan_checks.allowed` 규율)."""
    out = {}
    for key, why in ((index_data or {}).get(STRICT_WAIVER_FIELD) or {}).items():
        key, why = str(key).strip(), str(why if why is not None else "").strip()
        if key and why:
            out[key] = why
    return out


def silent_undeclared(rows):
    """close 를 막을 것만 고른다 — **게이트형 · strict 0 · 보류 없음 · 사유 없음.**"""
    return [r for r in rows if r["state"] == "미선언" and r["shape"] == "게이트"
            and not r["pending"] and not r["reason"]]


def strict_key_rows(chapters):
    """키마다 한 줄. 판정은 **빌드가 쓰는 자**(`is_strict_chapter`)에 위임한다.

    `strict_leftovers` 와 같은 이유다 — 공통 목록만 보면 과목이 자기 선언으로 올린 챕터를
    '미선언' 이라고 오보한다.
    """
    import json as _json
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import audit_content                                                       # noqa: E402
    from buildlib.checks_content import (is_strict_chapter,                    # noqa: E402
                                         subject_pending_chapters)
    try:
        with open(os.path.join(audit_content.DATA, "index.json"), encoding="utf-8") as fh:
            index_data = _json.load(fh)
    except (OSError, ValueError):
        index_data = {}
    waivers = strict_waiver_reasons(index_data)
    probe = os.path.join(audit_content.DATA, chapters[0] if chapters else "index.json")
    out = []
    for key, info in sorted(opt_in_strict_keys().items()):
        names = _resolve_common_names(info["names"])
        strict = [c for c in chapters
                  if is_strict_chapter(os.path.join(audit_content.DATA, c), names, key)]
        out.append({"key": key, "shape": info["shape"],
                    "state": classify_coverage(len(strict), len(chapters)),
                    "strict": len(strict), "total": len(chapters),
                    "pending": sorted(subject_pending_chapters(probe, key)),
                    "reason": waivers.get(key, "")})
    return out


def card_overlap_backlog_rows():
    """과목마다 `(과목, 학기, 선언 챕터 수, 전체 챕터 수, 미판정 쌍 수)` — 순회 범위를 함께 낸다.

    ★ **순회 범위는 `data/<과목>/chNN.json` 전부**다(`audit_conventions.chapters`). 과목을
      코드에 적지 않는다 — 「공통 도구에 과목별 사실을 박지 않는다」.
    ★ 「미판정」은 **문턱을 넘었는데 사유가 안 적힌 쌍**이다. 판정이 옳은지는 이 자가 못 본다.
    """
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import audit_conventions as ac                                          # noqa: E402
    from buildlib.checks_content import (CARD_OVERLAP_GATE_MIN,             # noqa: E402
                                         subject_strict_chapters)
    rows_by_subject, semesters, seen = ac.card_overlap_dist()
    out = []
    for subject in sorted(rows_by_subject):
        chapters = seen.get(subject) or set()
        subject_dir = os.path.join(ROOT, "data", subject)
        declared = subject_strict_chapters(os.path.join(subject_dir, "ch00.json"),
                                           "card_overlap")
        left = sum(1 for (_ch, _o, _l, _r, score, judged) in rows_by_subject[subject]
                   if score >= CARD_OVERLAP_GATE_MIN and not judged)
        out.append((subject, semesters.get(subject, "?"), len(declared), len(chapters), left))
    return out, CARD_OVERLAP_GATE_MIN


def card_overlap_backlog():
    """화면에 찍을 줄들. 판정은 `card_overlap_backlog_rows` 가 하고 여기는 꼴만 만든다."""
    rows, gate = card_overlap_backlog_rows()
    total = sum(r[4] for r in rows)
    lines = [f"[L] 본문·잘 놓쳐요·떠올리기 겹침 — 미판정 {total}건 "
             f"(문턱 {gate:.2f} · 순회 과목 {len(rows)}개)",
             "   ※ 이 게이트는 과목이 `strictChapters.card_overlap` 에 선언해야 돈다 — "
             "선언 0 인 과목은 빌드가 아무 말도 안 한다."]
    for subject, semester, n_declared, n_chapters, left in rows:
        if not left and not n_declared:
            continue                    # 잔량도 없고 선언도 없다 — 화면에 낼 것이 없다
        mark = "OK " if not left else "-> "
        lines.append(f"   {mark}{subject[:22]:<22} {semester:<4} "
                     f"선언 {n_declared:>2}/{n_chapters:<2}챕터 · 미판정 {left}건")
    lines.append("   -> 판정은 data/<과목>/card-overlap-verdicts.json 에 "
                 "「중복 아님 + 사유」 또는 「고쳤다」로 적는다 "
                 "(후보는 `python tools/audit_conventions.py --class=L`)")
    return lines


def backup_age():
    """마지막 백업이 며칠 전인지 — (상태, 근거). 순수 조회다(백업을 돌리지는 않는다).

    ★ **막지 않는 항목이다.** 백업 여부는 *이 세션의 결과물이 옳은가*와 무관하고,
      목적지(git 설정 `backup.dest`)는 기계별 사실이라 안 정한 기계도 있다. 막으면 그 기계에서
      close 가 영영 안 난다. 대신 **경과 일수를 적어** 세션 닫기 직전에 사람이 정하게 한다.
    """
    import datetime
    # ★ 목적지 해석은 **backup_bundle 한 곳**에서만 한다 (2026-08-02).
    #   처음엔 여기서 `backup-dest.txt` 를 직접 읽었는데, 그 파일이 워크트리 안에 있어
    #   **정한 과목에서만 보이고 나머지 과목에서는 계속 '미설정'** 으로 떴다
    #   (사용자: *[발화 생략]*). 해석기를 두 벌 두면 이렇게 갈라진다.
    import backup_bundle                                                    # noqa: E402
    dest = backup_bundle.resolve_dest()
    if not dest:
        return ("안내", "목적지 미설정 — `python tools/backup_bundle.py --set-dest \"<폴더>\"`")
    if not os.path.isdir(dest):
        return ("안내", "목적지 폴더가 없다: " + (dest or "(빈 값)"))
    # 접두어가 맞는 것만 센다 — 목적지에 사용자의 다른 파일이 있어도 오판하지 않는다.
    stamps = sorted(f for f in os.listdir(dest)
                    if re.fullmatch(r"repo-backup-\d{8}-\d{6}\.zip", f))
    if not stamps:
        return ("안내", "백업 없음 — `python tools/backup_bundle.py`")
    last = datetime.datetime.strptime(stamps[-1][len("repo-backup-"):-len(".zip")],
                                      "%Y%m%d-%H%M%S")
    days = (datetime.datetime.now() - last).days
    when = last.strftime("%m-%d %H:%M")
    note = f"{when} · {len(stamps)}세대 보관"
    if days >= 1:
        return ("안내", f"{days}일 전 ({note}) — 돌릴 것: `python tools/backup_bundle.py`")
    return ("close", f"오늘 {when} · {len(stamps)}세대 보관")


def exit_code(hard_failures, blockers):
    """종료코드 — **미완이 하나라도 걸리면 1**. 순수 함수(회귀가 직접 부른다).

    ★★ **고친 날 2026-08-26.** 여기는 `main()` 안에 `return 1 if hard_failures else 0` 으로
      박혀 있었고, `hard_failures` 에 들어가는 것은 「브라우저 차단 분류」 **하나뿐**이었다.
      `blockers.append` 는 16곳인데 **어느 것도 종료코드에 안 닿아서** 빌드 실패 · 회귀 실패 ·
      바닥 방어 ✘ · 맨손 범위 주장 · 근거 없는 확정 · 미커밋이 **전부 걸려도 exit 0** 이었다.
      코드 주석 셋과 원장이 *[발화 생략]* 라고 적는데 **그 문장이 기계적으로 거짓**이었다.
    ★ **함수로 뽑은 이유**: `main()` 은 빌드와 회귀를 실제로 돌려서 회귀가 못 부른다.
      판정만 갈라 두면 «비지 않은 `blockers` 가 exit 를 움직이는가» 를 직접 잰다 —
      **잠금이 없어 새 blocker 를 더해도 아무 회귀가 안 깨지던** 자리가 이것이다.
    ★ **벽이 되면 안 되는 것은 애초에 `blockers` 에 안 담긴다** — 진행 중계(2-a5) ·
      지침 크기 래칫(2-a4e) · 게이트 실체(2-a4b) **셋**은 `rows` 에 「참고」로만 들어간다
      (2026-08-26 소스로 재확인: 세 자리 다 `rows.append(..., "참고", ...)` 이고
      `blockers.append` 가 없다 — 옛 판본은 「셋」이라 적고 둘만 이름을 댔다).
      그 판정은 건드리지 않는다(벽이 서면 다음 회차가 마감을 통째로 우회한다).
    """
    return 1 if (hard_failures or blockers) else 0


def browser_block_audit_texts(items):
    """Return classification failures for (path, workorder_text) pairs."""
    failures = []
    for path, text in items:
        progress = section(text, "진행 기록")
        for issue in browser_block_record_issues(progress):
            failures.append(path + ": " + issue)
    return failures


CLAIM_MARK = "상태: 종결"


def claims_complete(text):
    """저자가 이 워크오더를 「끝났다」고 적었는가. 순수 함수 — 테스트 대상.

    `> 상태: 종결` 은 AGENTS.md 「워크오더 수용 게이트」 절이 명시한 대로 **게이트에 힘이
    없는 사람용 표시**다(2026-08-08 판정 — 이 마크로 완료 기준 실행을 건너뛰던 길을 그날
    되돌렸다). 그 판정을 뒤집는 것이 아니다 — `verify_workorder.py` 는 여전히 이 마크를
    보지 않고 완료 기준을 실제로 돌린다. 여기서 쓰는 목적은 다르다: **아직 진행 중인
    워크오더가 완료 기준 미달로 걸리는 것은 결함이 아니라 정상**(항목별 판정을 아직 안
    적었을 뿐)이므로, 저자가 스스로 "끝났다"고 적은 것만 실패를 close 블로커로 올린다.
    """
    return CLAIM_MARK in text


def main():
    print("=" * 74)
    print("close 점검 — 각 줄은 방금 실행한 결과다 (기억이 아니라)")
    print("=" * 74)

    # 1) 빌드 — **`--all` 로 돈다** (2026-08-01 dynamics 실측).
    #
    # `--all` 없이 돌면 index.json 의 status 가 `done` 인 챕터만 빌드한다. 그래서 **제작 중인
    # 과목**(모든 챕터가 todo)에서는 `nothing to build` 로 exit 1 이 나고, close 점검이
    # '빌드 실패' 라고 보고한다 — 실패가 아니라 **아직 done 이 없을 뿐**인데 매 세션 미완으로 뜬다.
    # 게다가 그 상태에서는 챕터 lint 가 **한 번도 안 돈다**. close 점검이 확인해야 할 것은
    # '배포 대상이 있는가' 가 아니라 '지금 있는 데이터가 규격을 지키는가' 이므로 --all 이 맞다.
    # 새로 연 과목(materials·solids)도 같은 조건이라 그쪽에서도 같은 오보가 났을 것이다.
    total_warn, waivers = 0, []            # 빌드를 건너뛰어도 아래 요약이 이 둘을 읽는다
    if not skip_without_subject("빌드", "data/ 에 챕터가 0개다 — 빌드할 것이 없다"):
        code, out = run("tools/build_site.py", "--all")
        total_warn = out.count("[warn")
        waivers = [l.strip()[len("[면제]"):].strip()
                   for l in out.splitlines() if l.strip().startswith("[면제]")]
        if code == 0:
            rows.append(("빌드", "close", f"exit 0 · 삽화 lint 명시 면제 {len(waivers)}건"))
        else:
            rows.append(("빌드", "실패", out.strip().splitlines()[-1][:70]))
            blockers.append("빌드 실패")

    # 1-b) ★ 경고 잔량 — 예전에 이 자리에서 "경고 N건"을 세면서 상태를 close로 찍었다.
    # 그 한 줄이 ch01 삽화 경고 28건을 무기한 유예시킨 구조적 원인이었다(2026-07-28 사용자 지적).
    # 이제 경고 상태 자체가 없다(error 아니면 명시 면제) — 그래도 남아 있다면 이 게이트를
    # 우회한 경로가 생긴 것이므로 blocker로 세운다.
    if total_warn:
        rows.append(("경고 잔량", "미완", f"{total_warn}건 — 경고 상태는 폐지됐다(면제로 선언하거나 고칠 것)"))
        blockers.append(f"경고 {total_warn}건")
    else:
        rows.append(("경고 잔량", "close", "0건 — 상태는 error 아니면 명시 면제뿐"))

    # 1-c) ★ **수락해 놓고 안 민 기준선** (열린 날 2026-08-07, 재발 지적).
    #
    # 사용자: *[발화 생략]*
    #
    # AGENTS 는 *[발화 생략]* 고
    # 적어 두었지만 **지켰는지 확인하는 기계가 없었다.** 그래서 세션이 끝날 때 아무도 안 물었고,
    # 남은 마크를 다음 세션이 *[발화 생략]* 으로 문서에 적어 굳혔다. close 는 바로 그 자리다.
    try:
        if skip_without_subject("기준선 밀기", "잴 챕터가 0개다 — «남은 하이라이트 0건» 은 공허한 참이다"):
            raise _NotApplicable
        import glob
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from buildlib.review import (marks_from_built_html,               # noqa: E402
                                     stale_acceptances)
        stale = []
        for html_path in sorted(glob.glob(os.path.join(ROOT, "site", "*", "ch*.html"))):
            subject = os.path.basename(os.path.dirname(html_path))
            if subject == "template":
                continue
            ch_path = os.path.join(ROOT, "data", subject,
                                   os.path.splitext(os.path.basename(html_path))[0] + ".json")
            chapter, marks = marks_from_built_html(html_path)
            if chapter is None:
                continue
            for name, left, at in stale_acceptances(ch_path, chapter, marks):
                stale.append(f"{subject} {os.path.basename(ch_path)} {name}"
                             f"({at} 수락, {len(left)}건)")
        if stale:
            rows.append(("기준선 밀기", "미완", "; ".join(stale)[:120]))
            blockers.append("수락한 범위에 하이라이트가 남았다 — `--accept-review-head` 로 다시 밀 것: "
                            + "; ".join(stale))
        else:
            rows.append(("기준선 밀기", "close", "수락 범위에 남은 하이라이트 0건"))
    except _NotApplicable:                 # 위에서 이미 «해당없음» 으로 세었다
        pass
    except Exception as exc:               # 산출물이 없어도 close 보고는 계속돼야 한다
        rows.append(("기준선 밀기", "확인불가", str(exc)[:70]))

    # 2) 회귀 테스트
    code, out = run("tools/test_checks.py")
    cases = out.count("[ok]") + out.count("[FAIL]")
    if code == 0:
        rows.append(("회귀 테스트", "close", f"exit 0 · {cases}케이스 전부 통과"))
    else:
        rows.append(("회귀 테스트", "실패", f"{out.count('[FAIL]')}건 실패"))
        blockers.append("회귀 테스트 실패 — 검사가 과거 결함을 더는 못 잡는다")

    # 2-a) ★ 아무도 안 부르는 검사·도구 (열린 날 2026-08-07, XSanity 에서 역이식).
    #
    # 검사가 결함을 잡는지는 test_checks 가 잠그는데, **그 검사가 호출되기는 하는지**는
    # 아무도 안 봤다. buildlib 에 함수를 써 놓고 배선을 빠뜨리면 빌드도 회귀도 초록이다.
    # 도구도 같다 — 등록 안 된 도구는 다음 세션에게 없는 것과 같아서 같은 것을 또 만든다.
    code, out = run("tools/audit_orphan_checks.py", "--fail-only")
    if code == 0:
        rows.append(("도구·검사 등록", "close", "호출자 없는 검사·도구 0건"))
    else:
        tail = [l for l in out.splitlines() if l.startswith("[FAIL]")]
        rows.append(("도구·검사 등록", "미완", "; ".join(tail)[:110] or out.strip()[:110]))

    # 2-a2) ★ 검사가 **조용히 줄었는지** (열린 날 2026-08-12).
    #
    # **무엇이 새어나갔나:** 「검사 완화·우회는 빨강」은 문장이었고, 회귀 테스트 239개 중
    # 하나를 지워도 빌드·회귀·close 어디도 빨개지지 않았다. 바깥 자료가 짚은 그대로다 —
    # *[발화 생략]*. 막는 게 아니라 **보이게** 하는 자리다.
    code, out = run("tools/audit_check_erosion.py")
    if code == 0:
        rows.append(("검사 침식", "close", out.strip().splitlines()[-1][:110] if out.strip() else "줄어든 것 없음"))
    else:
        tail = [l for l in out.splitlines() if l.strip() and not l.startswith("  ->")]
        rows.append(("검사 침식", "미완", "; ".join(tail[-2:])[:110]))

    # 2-a4) ★ 수치에 **근거**가 붙어 있는지 — 래칫 (공용 `규칙/방지장치-설계.md` 15항, 2026-08-15).
    #
    # **틀린 숫자와 맞는 숫자는 겉모습이 같다.** 문장은 근거가 없으면 비어 보이는데 숫자는
    # 근거가 없어도 «정해진 것» 처럼 보여서 아무도 «그 8초는 어디서 나왔나» 를 안 묻는다.
    # ★ 소급 면제된 것은 **빚이라 안 막는다** — 전부 FAIL 로 내면 경보 피로가 되어 자가 죽는다.
    #   여기가 막는 것은 **새로 생긴 것**뿐이다.
    # ★★ 이 자리가 있어야 규율 17 이 말하는 «재는 자를 만들고 거기서 멈추는» 함정을 피한다.
    code, out = run("tools/audit_magic_numbers.py")
    head = out.strip().splitlines()[0][:110] if out.strip() else ""
    if code == 0:
        rows.append(("수치 근거", "close", head))
    else:
        hits = [l.strip() for l in out.splitlines() if "[근거 없음]" in l]
        rows.append(("수치 근거", "미완", "; ".join(hits[:2])[:110] or head))

    # 2-a4b) 주석·독스트링의 「찾았는데 안 고쳤다」 자백 — 래칫(층 0 「고치기」 · 공용 폴더 이식 2026-09-11).
    #   씨앗은 빚이라 안 막고 새로 생긴 것만 막는다.
    code, out = run("tools/check_open_admissions.py")
    head = out.strip().splitlines()[0][:110] if out.strip() else ""
    if code == 0:
        rows.append(("코드 자백", "close", head))
    else:
        hits = [l.strip() for l in out.splitlines() if l.startswith("   ") and ":" in l]
        rows.append(("코드 자백", "미완", "; ".join(hits[:2])[:110] or head))

    # 2-a4a) ★ **"done"인데 문풀·연습문제가 비어 있는가** (열린 날 2026-09-02, medesign).
    #
    # **무엇이 새어나갔나:** 빌드·회귀·개인정보 스캔이 전부 초록이라는 것만 보고 "남은 거
    # 없다"고 보고했다. 사용자: *[발화 생략]* — 근거는 댔지만 **엉뚱한 것의
    # 근거**였다(품질 게이트 통과 ≠ SUBJECT.md에 적힌 범위를 다 채움). `status: "done"`은
    # 저자가 스스로 매기는 값이라, 이론만 채우고 done을 찍는 것을 막을 장치가 없었다.
    code, out = run("tools/audit_chapter_completeness.py", "--fail-only")
    if code == 0:
        rows.append(("문풀·연습문제", "close", "status=done 챕터 중 미선언 빈 컬렉션 0건"))
    else:
        tail = [l for l in out.splitlines() if l.startswith("[FAIL]")]
        rows.append(("문풀·연습문제", "미완", f"{len(tail)}건 — " + (tail[0][:90] if tail else "")))
        blockers.append(f"문풀·연습문제 미선언 공백 {len(tail)}건 — index.json contentWaivers로 "
                         "사유를 밝히거나 채울 것")

    # 2-a4a1) 「0건」이 「없다」인가 「못 봤다」인가 — 조용한 0건 래칫(2026-09-09).
    #   사용자: *[발화 생략]*. 과목 이름 오타 하나로 감사가 통째로 죽은 채
    #   「합계 0건」을 찍는 자리를 센다. 늘면 막고, 줄면 `--accept` 로 기준선을 낮춘다.
    code, out = run("tools/audit_sweep_reach.py", "--quiet")
    if code == 0:
        rows.append(("감사의 순회 범위", "close", "조용한 0건이 기준선 이하"))
    else:
        tail = [l for l in (out or "").splitlines() if l.startswith("   · ")]
        rows.append(("감사의 순회 범위", "미완", f"조용한 0건 {len(tail)}개"))
        blockers.append("감사가 「없는 과목」을 조용히 통과시킨다 — "
                        "`python tools/audit_sweep_reach.py`")

    # 2-a4a2) 이론 절 삽화 판정 — **래칫**. 사용자 판정 2026-09-09 [발화 생략].
    #
    # 승격 순간 실측이 **893 절**(이론이 있는 장 213 개 중 193 개)이라, 그 자리에서 전부를
    # blocker 로 걸면 세션이 한 번도 안 닫힌다 — 이 파일 자신의 설계 원칙(「전부 막으면 경보
    # 피로로 검사기가 죽는다」)과 부딪힌다. 그래서 **승격은 전 과목 동시로 하되 문턱은 래칫**이다:
    # 되돌아가는 것은 그 자리에서 막히고, 갚는 속도는 루프가 정한다.
    # 기준선 파일 `docs/이론삽화-절판정-기준선.txt` 를 못 읽으면 **엄한 쪽**으로 넘어진다.
    code, out = run("tools/audit_theory_figure_reasons.py", "--fail-only")
    _m = re.search(r"미판정 절 (\d+)개", out or "")
    _now = int(_m.group(1)) if _m else None
    _base = None
    try:
        with open(os.path.join(ROOT, "docs", "이론삽화-절판정-기준선.txt"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    _base = int(line)
                    break
    except (OSError, ValueError):
        _base = None
    if _now is None or _base is None:
        rows.append(("이론 삽화 판정", "미완", "기준선이나 실측을 못 읽었다 — 엄한 쪽으로 본다"))
        blockers.append("이론 절 삽화 판정 눈금을 못 읽었다 — "
                        "`python tools/audit_theory_figure_reasons.py`")
    elif _now > _base:
        rows.append(("이론 삽화 판정", "미완", f"미판정 절 {_now} > 기준선 {_base} — 늘었다"))
        blockers.append(f"이론 절 삽화 판정이 늘었다 {_base}→{_now} — 새로 쓴 절에 삽화나 사유를 "
                        "붙일 것(`python tools/audit_theory_figure_reasons.py --fail-only`)")
    else:
        rows.append(("이론 삽화 판정", "close",
                     f"미판정 절 {_now} ≤ 기준선 {_base}"
                     + (" — 줄었으니 기준선을 낮출 것" if _now < _base else "")))

    # 2-a4b) ★★ **게이트가 진짜 게이트인가** — 자 · 문 · 부르는 자 (공용 폴더에서 이식 2026-08-26).
    #
    # **무엇이 새어나갔나:** `audit_gates`·`check_floor`·`audit_scope_claims`·`audit_guide_size`·
    # `audit_stamps` 다섯이 `tools/` 에 있고 AGENTS 도구 등록부에도 올라 있는데 **부르는 코드가
    # 하나도 없었다**(실측 2026-08-26 `audit_gates` 출력: 다섯 줄 전부 «부르는 자 0곳»).
    # 목록에서는 다섯 다 「있다」로 보인다 — 그래서 눈이 아니라 자가 본다.
    #
    # ★ **자리가 여기인 이유:** 아래 「진행 중계」 블록과 `# 2-b)` 사이는
    #   `test_narration_ceiling_is_wired`(⑺-b)가 «`blockers.append` 가 없어야 한다» 고 훑는
    #   창이다. 게이트를 그 사이에 끼우면 그 회귀가 깨진다 — **테스트를 고칠 일이 아니라
    #   코드를 그 창 밖에 두는 것이 맞다**(⑺-b 가 잠그는 판정은 여전히 옳다).
    #
    # ★ **이 줄은 「참고」다 — 막지 않는다.**
    # ★★ **그 「사람 판정」은 2026-08-26 에 닫혔다.** 배선 직후 반쪽 게이트가 5 → 1 로 줄고
    #   남은 하나가 `audit_guide_size` 였는데, 그 자는 설계상 래칫이라 언제나 exit 0 이다.
    #   길이 둘이었고(⑴ 선언에서 래칫을 빼기 ⑵ `audit_gates` 에 「래칫」 칸 만들기)
    #   **⑵ 로 판정했다** — ⓐ 래칫이 셋이라 빼는 방식이면 뺄 때마다 또 빼야 하고 그 자들이
    #   배선됐는지 아무도 안 보게 된다 ⓑ 래칫에도 문은 있다, **사람이다**(실행 규율 20).
    #   → 실측 후 반쪽 0개 · `audit_gates` exit 0.
    # ★ **그래도 여기서 막지는 않는다.** 「참고」를 「미완」으로 올리는 것은 별개 판정이라
    #   (규칙 19 — 요청한 만큼만) 큐에 번호로 열어 뒀다: `docs/2026-08-25-문항-채우기-큐.md`.
    #   섣불리 막으면 마감이 통째로 서고, 그러면 다음 회차가 close 를 통째로 우회한다.
    code, out = run("tools/audit_gates.py", "--quiet", "--run-selftests")
    if code == 0:
        rows.append(("게이트 실체", "close", "자·문·부르는 자 셋을 다 갖췄다"))
    else:
        # ★ **불릿을 통째로 세지 않는다** (2026-08-26, 이식 직후 잡았다). 이 자의 출력에는
        #   «·» 로 시작하는 묶음이 둘이다 — FAIL 목록과 «아직 자가 없는 것»(그쪽은 스스로
        #   «막지 않는다» 고 적은 할 일 목록이다). 통째로 세면 자가 «반쪽 1개» 라 찍는 자리에서
        #   요약만 «반쪽 3개» 가 된다 — 같은 배치에서 `verify_all` 을 고친 그 부류
        #   (요약이 본문과 다른 수를 말한다)를 이식하며 되풀이할 뻔했다.
        # ★ 표식을 「FAIL 줄 다음의 연속된 불릿」으로 잡는다. 표가 먼저 나오나 나중에 나오나
        #   (stdout·stderr 를 이어 붙이는 순서에 달렸다) 같은 답이 나온다.
        lines = out.splitlines()
        half, taking = [], False
        for l in lines:
            s = l.strip()
            if s.startswith("FAIL"):
                taking = True
                continue
            if taking:
                if s.startswith("·"):
                    half.append(s[1:].strip())
                elif s:
                    break
        n = len(half)
        # ★ 꼬리말이 낡지 않게 한다 (2026-08-26). 예전에는 *[발화 생략]* 이라
        #   적었는데 그 자리는 「래칫」 칸으로 닫혔다 — 남는 빨강은 이제 **진짜 배선 결함**이다.
        #   틀린 사유를 달아 두면 다음 사람이 그 줄을 «원래 그런 것» 으로 읽고 넘긴다.
        rows.append(("게이트 실체", "참고",
                     ("반쪽 %d개: " % n) + ("; ".join(half[:2]))[:70]
                     + " — 막지 않는다(올릴지는 큐 ⑺)"))

    # 2-a4c) ★ 바닥 방어가 **배선**됐나 — 일곱 항목(`@import`·훅 등록·게이트 호출부·기록·
    #   커밋의 「왜」·공용 연결·자기 사본의 신선도). 손으로 돌리는 게이트는 바쁜 날 안 돌고,
    #   안 돈 날이 곧 사고 난 날이다. 실측 2026-08-26 배선 직전: `✘ 0건`(초록) — 그래서 막는다.
    code, out = run("tools/check_floor.py", ".")
    if code == 0:
        rows.append(("바닥 방어", "close", "✘ 0건"))
    else:
        bad = [l.strip() for l in out.splitlines() if l.strip().startswith("✘")]
        blockers.append("바닥 방어 ✘ — `python tools/check_floor.py .`")
        rows.append(("바닥 방어", "미완", ("; ".join(bad[:2]) or "✘ 있음")[:110]))

    # 2-a4d) ★ 「전수」라 쓰고 부분만 했나 (규칙 21 ⑵ · 공용 「규칙/증거의-정직.md」).
    #   실측 2026-08-26 배선 직전: 맨손 주장 0건(초록) — 그래서 막는다.
    code, out = run("tools/audit_scope_claims.py", "--quiet")
    if code == 0:
        rows.append(("범위 주장", "close", "맨손 주장 0건"))
    else:
        blockers.append("맨손 범위 주장 — `python tools/audit_scope_claims.py`")
        rows.append(("범위 주장", "미완",
                     next((l.strip() for l in out.splitlines() if "맨손" in l), "")[:110]))

    # 2-a4e) ★ 실리는 지침 래칫 — **막지 않는다.** 자란 것이 정당하면 `--accept` 로 기준선을
    #   옮기는 것이 정본 절차라(실행 규율 20) 여기서 exit 코드를 게이트로 쓰면 안 된다.
    code, out = run("tools/audit_guide_size.py", ".")
    rows.append(("지침 크기", "참고",
                 next((l.strip() for l in out.splitlines() if "합계" in l), "")[:110]))

    # 2-a4f) ★ 근거 없는 「확정」 도장 — 관측 레코드를 못 가리키는 칸(규칙 21 ⑶).
    #   대상 선언이 없는 갈래에서는 **해당 없음으로 조용히 통과**한다(exit 0).
    #   실측 2026-08-26 배선 직전: 근거 없는 확정 0칸(초록) — 그래서 막는다.
    code, out = run("tools/audit_stamps.py", "--quiet")
    if code == 0:
        # ★ **exit 0 의 뜻을 여기서 지어내지 않는다** (2026-08-26). 옛 판은 무조건
        #   「근거 없는 확정 0칸」이라 찍었는데, 그 0 이 «봤는데 없다» 인지 «볼 것이 없다» 인지
        #   **이 자리는 모른다.** 그 자가 스스로 낸 판정 줄을 그대로 옮긴다.
        said = next((l.strip() for l in out.splitlines() if "[도장 감사]" in l), "")
        rows.append(("확정 근거", "close",
                     said.replace("[도장 감사]", "").strip()[:110] or "근거 없는 확정 0칸"))
    else:
        blockers.append("근거 없는 확정 — `python tools/audit_stamps.py`")
        rows.append(("확정 근거", "미완",
                     next((l.strip() for l in out.splitlines() if "FAIL" in l), "")[:110]))

    # 2-a5) ★★ 진행 중계 — **여기서는 세기만 한다. 막는 자리는 커밋이다** (개정 2026-08-15).
    #
    # 이 리포의 항목이 전부 **리포 산출물**이라 「상호작용」 축은 사람의 성실성에 걸려 있었고,
    # `audit_session_conduct`·`audit_session_cost` 는 세기만 한다(설계상 옳다). 그런데
    # **세는 자만 있으면 그 숫자가 «값을 했다» 는 성과로 읽힌다** — 원 실사고가 그랬다.
    # 그래서 처음 판본은 이 자리를 **「막는 자」로 선언**했다.
    #
    # ★★ **그런데 여기서는 막을 수 없다 — 사용자 판정 2026-08-15.**
    #   이 수는 **세션 전체 누적**이라(`check_narration.latest_session`) close 를 돌리는
    #   시점엔 이미 확정이다. 다른 close 항목은 전부 «고치고 다시 돌리면 초록» 인데
    #   **이것만 그 세션 안에서 못 지운다** — 초록으로 가는 길이 «세션을 새로 여는 것» 뿐이다.
    #   못 지우는 빨간불은 게이트가 아니라 **벽**이고, 벽이 서면 사람은 그 아래 멀쩡한
    #   항목들까지 함께 무시한다(이 리포가 반복해 배운 «경보 피로는 검사기를 죽인다»).
    #
    # ☞ **트리거를 「아직 고칠 수 있는 시점」으로 옮겼다 — `commit.py` 다.**
    #   거기서 `check_narration --quiet` 가 넘겼을 때만 한 줄 낸다. 그 시점엔 남은 턴에서
    #   실제로 줄일 수 있다(AGENTS 「방지장치의 트리거는 내가 반드시 하는 일에 건다」).
    # ★ **안 막는다는 사실을 여기 적어 두는 것이 실행 규율 17 의 요구다** —
    #   *[발화 생략]*
    #   조용히 안 막는 것과 **안 막는다고 밝히는 것**은 다르다.
    # ★ 상한은 실측에서 왔고(발화 1회당 1줄) 표본이 작은 세션은 스스로 판정을 미룬다.
    code, out = run("tools/check_narration.py")
    lines_out = [l.strip() for l in out.splitlines() if l.strip()]
    if code == 0:
        rows.append(("진행 중계", "close", lines_out[0][:110] if lines_out else ""))
    else:
        fail = [l for l in lines_out if l.startswith("FAIL")]
        # ★ 상태를 **`참고`** 로 적는다 — `미완` 은 「고치면 닫힌다」는 뜻인데 이 항목은
        #   그 세션 안에서 고칠 수가 없다(위 ★★). 같은 글자를 쓰면 읽는 사람이
        #   *[발화 생략]* 를 반복해 묻게 되고, 그게 경보 피로의 시작이다.
        rows.append(("진행 중계", "참고",
                     ((fail[0] if fail else lines_out[0] if lines_out else "")
                      + " — 막지 않는다(커밋에서 알린다)")[:110]))

    # 2-b) ★ 수치 검산 — 그 과목의 답 검산 도구를 **실제로 돌린다** (열린 날 2026-08-07).
    #
    # **무엇이 새어나갔나:** `verify_*_answer.py` 는 만들어만 두고 **아무도 자동으로 안 돌렸다.**
    # 빌드도 회귀도 close 점검도 이 도구를 부르지 않았으므로, 데이터의 수가 틀려도
    # 어디에서도 빨개지지 않는다 — 사람이 그 명령을 기억해 치는 동안에만 유효한 규칙이었다.
    # 절대 규칙 4 가 "스크립트로 독립 검산" 이라고 못박은 것을 **실행에서 놓치고 있던** 자리다.
    #
    # ★ 어느 파일이 이 과목 것인지는 **`index.json` 이 선언**한다(`answerVerifier`).
    #   파일 이름으로 추측하지 않는다 — 공학수학의 것이 `verify_ode_answer.py` 라 이름에
    #   과목이 안 들어 있다. 폴백도 두지 않는다: 폴백이 있으면 **선언 안 한 과목이 선언한
    #   것처럼 조용히 지나간다**(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
    #
    # ★★ **미선언은 blocker 로 세우지 않는다.** 지금 다섯 과목에 검산 도구가 다 있는데
    #   선언한 곳은 아직 없다 — blocker 로 만들면 **남의 과목 close 가 그 자리에서 전부 멈춘다**
    #   (`len(svgs) == 2` 로 thermo 를 깨뜨린 전례와 같은 부류). 표에는 매 세션 뜨므로 묻히지
    #   않고, 각 과목이 자기 세션에서 한 줄 선언하면 그때부터 실행이 강제된다.
    verifier, verifier_err = None, None
    na_verify = skip_without_subject("수치 검산", "index.json 이 없다 — 검산할 데이터가 없다")
    try:
        if na_verify:
            raise _NotApplicable
        import json as _json
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import audit_content                                                   # noqa: E402
        with open(os.path.join(audit_content.DATA, "index.json"), encoding="utf-8") as fh:
            verifier = (_json.load(fh) or {}).get("answerVerifier")
    except _NotApplicable:                 # 위에서 이미 «해당없음» 으로 세었다
        pass
    except Exception as exc:
        verifier_err = str(exc)[:70]
    if na_verify:
        pass
    elif verifier_err:
        rows.append(("수치 검산", "확인불가", verifier_err))
    elif not verifier:
        # ★★ **「없다」와 「검산할 것이 있는데 없다」를 가른다** (열린 날 2026-08-25, 사용자 판정 ⓒ).
        #   위 ★★ 는 「미선언을 blocker 로 안 세운다」를 정했는데, 그 근거는 *[발화 생략]* 였다 — **문항이 0개인 과목**을 전제한 말이다.
        #   2026-08-25 에 전제가 깨졌다: 2-2 두 과목에 문항 40개가 들어왔는데 **검산 도구 자체가
        #   없다.** 그 수치는 초안 회차에 서브에이전트가 손으로 검산한 것뿐이고 아무도 다시 안 본다.
        #   ★ 그런데 「미선언」 한 줄은 문항 0개일 때와 40개일 때가 **글자가 같다** — 빚이 자라도
        #     화면이 안 변한다. 그래서 **수를 찍는다.** 자라는 빚은 자라는 것이 보여야 한다.
        #   ★ blocker 로는 안 세운다(위 판정 유지) — 지금 고칠 수 없는 빨간불은 경보 피로가 되고,
        #     경보 피로는 검사기를 죽인다. 대신 「미완」이라 close 표에서 눈에 띈다.
        n_items = None
        try:
            import glob as _glob
            n_items = 0
            for _p in sorted(_glob.glob(os.path.join(audit_content.DATA, "ch*.json"))):
                with open(_p, encoding="utf-8") as fh:
                    _ch = _json.load(fh) or {}
                n_items += len(_ch.get("problems") or []) + len(_ch.get("practice") or [])
        except Exception:                                                  # noqa: BLE001
            n_items = None
        if n_items:
            rows.append(("수치 검산", "미완",
                         f"문항 {n_items}개가 검산 자 없이 있다 — 그 수는 초안 회차에 한 번 "
                         "손으로 맞춰 본 것이고 아무도 다시 안 본다(절대 규칙 4)"))
        else:
            rows.append(("수치 검산", "미선언",
                         "index.json 에 answerVerifier 를 적으면 이 자리에서 실제로 돌린다"))
    elif not os.path.isfile(os.path.join(ROOT, "tools", verifier)):
        rows.append(("수치 검산", "확인불가", f"선언된 {verifier} 가 tools/ 에 없다"))
        blockers.append("수치 검산 도구 없음")
    else:
        code, out = run("tools/" + verifier)
        if code == 0:
            rows.append(("수치 검산", "close",
                         f"{verifier} exit 0 · {out.count('[ok]')}건 전부 통과"))
        else:
            rows.append(("수치 검산", "실패", f"{verifier} — {out.count('[FAIL]')}건 실패"))
            blockers.append("수치 검산 실패 — 데이터에 적힌 수가 틀렸다")

    # 2-b) ★ **발행 표면의 개인정보** — 배포하는 폴더만 훑는다 (열린 날 2026-08-14).
    #
    #   왜 여기 거나: `scan_private` 은 만들어져 있었지만 **아무도 안 불렀다.** 그래서
    #   ⑴ 발행 홈에 학교 이름이 박힌 것 ⑵ 템플릿 개발 주석이 통째로 실린 것이
    #   둘 다 **사람이 발행본을 직접 열어 보고서야** 나왔다(원장 2026-08-14 두 행).
    #   *[발화 생략]*(공용 방지장치-설계 9항).
    #
    #   ★ **`site/` 만 본다.** 저장소 공유 표면은 별도 `scan_private.py --tracked`가 맡는다.
    #     리포 전체를 훑으면 원장·워크오더의 실사고 기록이 통째로 걸려
    #     경보 피로가 되고, 경보 피로는 검사기를 죽인다. 막을 것은 **되돌릴 수 없는 것**,
    #     즉 밖으로 나가는 표면 하나다(공개-전-점검 §0 「방향의 비대칭」).
    #   ★ 예외는 `scan_private` 이 스스로 찾는 대장(`개인정보-예외.txt`)에 **사유와 함께**
    #     적는다 — 여기에 면제 목록을 만들지 않는다(두 곳에 적으면 갈라진다).
    site_dir = os.path.join(ROOT, "site")
    if not os.path.isdir(site_dir):
        rows.append(("발행 개인정보", "확인불가", "site/ 가 없다 — 빌드 뒤에 다시 볼 것"))
    else:
        code, out = run("tools/scan_private.py", "site")
        read_n = re.search(r"실제로 읽은 파일 (\d+)개", out)
        hit = re.search(r"^(\d+)건 / 파일 (\d+)개", out, re.M)
        if code == 0:
            rows.append(("발행 개인정보", "close",
                         f"site/ {read_n.group(1) if read_n else '?'}개 판독 · 0건"))
        else:
            rows.append(("발행 개인정보", "미완",
                         f"{hit.group(1) if hit else '?'}건 — `python tools/scan_private.py site`"))
            blockers.append("발행 표면에 개인정보 후보 — 빼거나 예외 대장에 사유와 함께 적을 것")

    # 3) 좌표 수정 대기 명단
    pending = read_set("checks_svg.py", "PENDING_FIG_FIXES")
    if pending is None:
        rows.append(("PENDING 명단", "확인불가", "패턴 불일치 — 수동 확인"))
    elif pending:
        rows.append(("PENDING 명단", "미완", f"{len(pending)}건 — " + ", ".join(sorted(pending))))
        blockers.append(f"PENDING_FIG_FIXES {len(pending)}건")
    else:
        rows.append(("PENDING 명단", "close", "비어 있음"))

    # 4) strict 승격 잔여 — **실재하는 챕터**를 **빌드와 같은 판정으로** 잰다
    #    (하드코딩·공통목록만 보기의 경위는 on_disk_chapters·strict_leftovers 독스트링).
    # ★ 공용 폴더 국소 분기 — 가르는 자(`skip_without_subject`)를 먼저 물어야 한다. 미러
    #   동기화가 두 번 순서를 되돌렸다(전공정리 원본은 `on_disk_chapters()` 가 안 죽어서
    #   순서가 안 보인다).
    strict_na = skip_without_subject(
        "strict 승격", "챕터가 0개다 — 여기서 «전 챕터 error» 는 공허한 참이다")
    chapters = () if strict_na else on_disk_chapters()
    for label, module, name in STRICT_SETS:
        if strict_na:
            break
        s = read_set(module, name)
        if s is None:
            continue
        left = strict_leftovers(chapters, s, name)
        if left:
            rows.append((f"{label} strict", "미완", "경고에 머문 챕터: " + ", ".join(left)))
        else:
            rows.append((f"{label} strict", "close", "전 챕터 error"))

    # 4-b) ★ **미선언 opt-in 승격 키** — 위 상수 블록이 정본.
    #      바로 위 4)는 **공통 목록이 있는 5종**만 본다. 그 목록조차 없는 규격
    #      (2026-08-02 이후 정책)은 여기서만 드러난다.
    optin_rows = []
    try:
        if skip_without_subject("opt-in 승격",
                                "선언할 index.json 이 없다 — 39키는 각 과목 워크트리의 몫이다"):
            raise _NotApplicable
        optin_rows = strict_key_rows(chapters)
        seen = {"선언됨": 0, "부분": 0, "미선언": 0}
        for r in optin_rows:
            seen[r["state"]] += 1
        silent = silent_undeclared(optin_rows)
        why = (f"{len(optin_rows)}키 · 선언 {seen['선언됨']} · 부분 {seen['부분']} · "
               f"미선언 {seen['미선언']}")
        if silent:
            names = ", ".join(r["key"] for r in silent)
            rows.append(("opt-in 승격", "미완", why + " — 사유 없는 침묵: " + names))
            blockers.append(
                f"opt-in 승격 미선언(침묵) {len(silent)}종 [{names}] — 미선언이면 그 검사가 "
                f"아예 안 돈다. 승격하거나 data/<과목>/index.json 의 {STRICT_WAIVER_FIELD} 에 "
                "사유를 적을 것")
        else:
            rows.append(("opt-in 승격", "close", why + " — 사유 없는 침묵 0건"))
    except _NotApplicable:                 # 위에서 이미 «해당없음» 으로 세었다
        pass
    except Exception as exc:               # 선언이 없는 브랜치에서도 close 보고는 계속돼야 한다
        rows.append(("opt-in 승격", "확인불가", str(exc)[:70]))

    # 5) 미커밋
    # core.quotepath=false가 없으면 한글 경로가 "\354\227..."로 이스케이프되어
    # .workorder.md 판정이 0건이 된다(2026-07-24, 새 6번 게이트 첫 실행에서 발견).
    r = subprocess.run(GIT_STATUS_CMD, cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    dirty = [l for l in (r.stdout or "").splitlines() if l.strip()]
    if dirty:
        rows.append(("미커밋 변경", "미완", f"{len(dirty)}개 파일"))
        blockers.append(f"미커밋 {len(dirty)}개")
    else:
        rows.append(("미커밋 변경", "close", "워킹트리 깨끗"))

    # 6) 변경 워크오더의 브라우저 차단 기록
    # verify_workorder를 따로 실행하는 것을 잊어도 close_report가 같은 부류를 다시 막는다.
    changed_workorders = []
    for line in dirty:
        path = line[3:].strip().strip('"').replace("\\", "/")
        if not path.endswith(".workorder.md"):
            continue
        full = os.path.join(ROOT, path)
        try:
            changed_workorders.append((path, open(full, encoding="utf-8").read()))
        except OSError:
            continue
    browser_failures = browser_block_audit_texts(changed_workorders)
    if browser_failures:
        rows.append(("브라우저 차단 분류", "실패", f"{len(browser_failures)}건 — 대체 검증/전용 잔여 미분리"))
        blockers.append(f"브라우저 차단 분류 {len(browser_failures)}건")
        hard_failures.extend(browser_failures)
    else:
        rows.append(("브라우저 차단 분류", "close",
                     f"변경 워크오더 {len(changed_workorders)}개 자동 감사"))

    # 6-b) ★ 워크오더 완료 기준 게이트를 **실제로 부른다** (신설 2026-08-31).
    #      `audit_gates.py`가 이 게이트의 선언된 부르는 자(`AGENTS.md`)가 문서일 뿐 실행되는
    #      코드가 아니라고 잡았다 — 즉 「완료를 주장하기 전 스스로 돌린다」는 사람의 성실성에만
    #      기대고 있었다. 여기서 실제로 돌리되, **진행 중인 워크오더가 걸리는 것은 정상**이라
    #      (항목별 판정을 아직 안 적은 것뿐) 저자가 `claims_complete()`로 "끝났다"고 적은 것만
    #      실패를 블로커로 올린다. `--no-build`는 위 1)이 이미 빌드를 돌렸기 때문이다.
    wo_gate_failures = []
    wo_gate_ran = 0
    for path, text in changed_workorders:
        wo_gate_ran += 1
        code, out = run("tools/verify_workorder.py", path, "--no-build")
        if code != 0 and claims_complete(text):
            last = out.strip().splitlines()[-1][:70] if out.strip() else "(출력 없음)"
            wo_gate_failures.append(f"{path}: exit {code} — {last}")
    if wo_gate_failures:
        rows.append(("워크오더 완료 기준", "실패",
                     f"'{CLAIM_MARK}' 표시된 것 중 {len(wo_gate_failures)}건 미달"))
        blockers.append(f"워크오더 완료 기준 미달 {len(wo_gate_failures)}건")
        hard_failures.extend(wo_gate_failures)
    else:
        rows.append(("워크오더 완료 기준", "close",
                     f"변경 워크오더 {wo_gate_ran}개 실행 · '{CLAIM_MARK}' 표시된 미달 0건"))

    # 7) 마지막 백업 — **close 를 막지는 않는다.**
    #    백업은 '이 세션의 결과물이 옳은가'와 무관하고, 목적지를 아직 안 정한 기계도 있다
    #    (git 설정 `backup.dest` 는 커밋되지 않는 기계별 값). 막으면 그 기계에서 close 가 영영 안 난다.
    #    대신 **며칠 지났는지를 눈에 띄게** 적어 세션 닫기 직전에 결정을 받게 한다
    #    (사용자: *[발화 생략]*).
    rows.append(("마지막 백업", *backup_age()))

    width = max(len(r[0]) for r in rows) + 2
    print()
    for name, state, why in rows:
        mark = ("OK  " if state == "close"
                else "--  " if state == "해당없음" else "->  ")
        print(f"  {mark}{name:<{width}}{state:<7}{why}")

    # ★ **안 잰 것을 세어서 밝힌다.** 조용히 빼면 «통과»와 화면에서 구별되지 않는다(규칙 11).
    #   `test_checks.needs_subject()` 가 같은 이유로 같은 줄을 찍는다 — 판정이 둘로 갈리지
    #   않게 **문구까지 같은 자리**를 쓴다.
    if NOT_APPLICABLE:
        print()
        print(f"[해당 없음] 이 워크트리에는 과목이 없다(공통 정본) — **{len(NOT_APPLICABLE)}줄은 "
              f"안 쟀다**: " + " · ".join(NOT_APPLICABLE))
        print("            여기 close 의 뜻은 «공통 계약이 성립한다» 이지 «콘텐츠가 옳다» 가 아니다.")

    # ★ 미선언 opt-in 키 **목록** — 고체역학이 요청한 「한 줄」이 이것이다.
    #   수치는 위 표가 이미 말했으므로 여기서는 **미선언만** 이름으로 낸다(출력을 길게 하지 않는다).
    undeclared = [r for r in optin_rows if r["state"] == "미선언"]
    if undeclared:
        print()
        print(f"미선언 opt-in 승격 키 {len(undeclared)}종 "
              "— 「선언 안 함」과 「해당 없음」은 화면에서 같아 보인다:")
        for r in undeclared:
            if r["reason"]:
                tag, note = "[사유]", r["reason"][:58]
            elif r["pending"]:
                tag, note = "[보류]", f"pendingChapters 에 {len(r['pending'])}챕터 선언"
            elif r["shape"] == "게이트":
                tag, note = "[★침묵]", "미선언이면 검사 함수가 아예 안 돈다 — 경고도 안 난다"
            else:
                tag, note = "[경고]", "함수는 돈다 — 위반이 있으면 경고로 뜬다(경고 잔량이 막는다)"
            print(f"   {tag:<7} {r['key']:<22} {note}")
        print(f"   -> 이 과목에 해당 없는 규격이면 data/<과목>/index.json 의 "
              f"\"{STRICT_WAIVER_FIELD}\": {{\"키\": \"사유\"}} 로 적을 것 "
              "(사유 없는 줄은 예외로 안 친다)")

    # ★ [L] 본문·잘 놓쳐요·떠올리기 겹침 — **과목별 미판정 잔량** (신설 2026-09-07).
    #   왜 여기 있나: 이 게이트는 **과목이 선언해야 도는 opt-in** 이라(그 판정선의 정본은
    #   `checks_content.card_overlap_declared` 독스트링), 안 켠 과목은 빌드가 아무 말도 안 한다.
    #   그 침묵이 이 부류를 여기까지 끌고 온 원인이다 — 자는 이미 후보를 내고 있었는데
    #   아무것도 막지 않아 아무도 판정하지 않았다(실행 규율 17 「세기만 하는 자」).
    #   → 켜지 않았어도 **잔량은 매번 화면에 나온다.** 여기서 막지는 않는다: 켠 챕터의
    #     잔량은 빌드가 이미 error 로 막고, 안 켠 것까지 막으면 경보 피로가 검사기를 죽인다.
    try:
        print()
        for line in card_overlap_backlog():
            print(line)
    except Exception as exc:                       # 잔량을 못 세도 close 보고는 계속돼야 한다
        print(f"\n[L] 겹침 잔량: 셀 수 없음 ({exc})")

    # ★ 승격 잔량 — '기계 방지'가 말로만 남은 것들 (열린 날 2026-08-06, 사용자 지적).
    #   *[발화 생략]* — 그날
    #   C31 이 정확히 그렇게 샜다. 잔량을 **매번 세어 보여야** '언젠가'가 숫자가 된다.
    #   막는 것은 `test_ledger_closed_rows_name_a_real_machine`(승격일 이후 행), 여기서는 잔량만 센다.
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        from buildlib.ledger import (LEDGER, ledger_source_note,       # noqa: E402
                                     pending_ledger_rows, pending_candidates)
        with open(LEDGER, encoding="utf-8") as fh:
            ledger_text = fh.read()
        old = pending_ledger_rows(ledger_text)
        inbox = pending_candidates()
        total = len(old) + sum(inbox.values())
        print()
        print(f"승격 잔량(기계 방지가 말로만 남은 것): 총 {total}건 "
              f"— 원장 옛 행 {len(old)} · 인박스/워크오더 {sum(inbox.values())}")
        # ★★ **어느 원장을 쟀는지 함께 찍는다** (2026-08-26). 이 자리는 오래 «0건» 이었는데
        #   그 0 은 **얼어붙은 사본**(`docs/feedback-ledger.md`, 머리에 «정본 아님» 이 박혀
        #   있다)의 0 이었다. 조용히 사본으로 떨어지면 «없다» 와 «못 봤다» 가 화면에서
        #   똑같아 보인다(규칙 11) — 그 둘을 가르는 것이 이 한 줄이다.
        # ★★ **분모까지 찍는다** (2026-08-26, 같은 날 두 번째). 경로를 정본으로 돌리자 이번엔
        #   **형식의 절반**(2026-08-22 이후 산문 절 20개)을 못 읽고 있던 것이 드러났다. 부류 이름은
        #   «자가 자기 입력을 못 잡았는데, 그 사실이 결과에 안 나온다» 이고, 처방은 하나다 —
        #   **자는 자기 분모를 같이 낸다.** 기대보다 작으면 그건 판정이 아니라 미완이다.
        print("   " + ledger_source_note(ledger_text))
        for path, hits in sorted(inbox.items()):
            print(f"   - {path}: {hits}건")
        if total:
            blockers.append(f"승격 잔량 {total}건 — 원장의 '기계 방지'가 말로만 남은 항목")
    except Exception as exc:                       # 원장이 없어도 close 보고는 계속돼야 한다
        print(f"\n승격 잔량: 셀 수 없음 ({exc})")

    print()
    if blockers:
        print("★ 미완이 있다. clear 여부는 사용자가 판단할 것:")
        for b in blockers:
            print("   - " + b)
    else:
        print("★ 전부 close — 다음 세션이 이어받을 수 있다.")
    # 면제는 유한하고 눈에 보여야 한다 — 매번 전부 출력한다. 목록이 길어지는 것이
    # 곧 '면제로 덮고 있다'는 신호이므로, 줄이는 것은 다음 배치의 일이다.
    if waivers:
        print()
        print(f"삽화 lint 명시 면제 {len(waivers)}건 (사유가 여전히 유효한지 볼 것):")
        for w in waivers:
            print("   - " + w)

    print()
    print("주의: 이 도구가 못 보는 것 — 뷰어 JS·CSS 동작(버튼·스크롤·줄바꿈)에는")
    print("      회귀 검증이 없다. 그 부류는 사람이 화면에서 확인해야 한다.")
    if hard_failures:
        print()
        for failure in hard_failures:
            print("  [FAIL] " + failure)
    # ★★★ 판정은 `exit_code()` 가 갖는다 — 경위와 근거는 그 독스트링이 정본이다.
    #   잠금 `test_checks.py::test_close_report_exit_code_follows_the_blockers`.
    return exit_code(hard_failures, blockers)


if __name__ == "__main__":
    sys.exit(main())
