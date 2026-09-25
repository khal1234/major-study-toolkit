# -*- coding: utf-8 -*-
"""Review-baseline storage and change metadata injection."""
import difflib
import json
import os
import re
import subprocess

# 삽화 좌표 1 이 화면에서 몇 px 인지 환산할 때 쓴다. **자를 두 벌 두지 않는다** —
# 글자 규격·치수 규격이 이미 이 값으로 '화면 실효 px' 를 정의하고 있다(checks_svg 가 정본).
from .checks_svg import FIGURE_RENDER_WIDTH, svg_with_only

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _review_snapshot_path(ch_path):
    return os.path.join(os.path.dirname(ch_path), ".review-snapshot", os.path.basename(ch_path))

def has_review_baseline(ch_path):
    """기준선 스냅샷 파일이 있는가. `.review-snapshot/` 은 git 밖이라 **폴더를 옮기면 통째로
    사라진다** — 2026-09-06 평탄화 때 21과목 전부 잃었고, 스냅샷이 없으면 변경점이 0건으로
    조용히 렌더돼 사용자가 «변경점 표시 계속 안 뜨네» 를 여러 번 겪었다(2026-09-13 실측).
    빌드는 이 값이 거짓이고 `reviewHold.baseline` 이 있으면 그 커밋에서 스냅샷을 되살린다."""
    return os.path.isfile(_review_snapshot_path(ch_path))


def _review_baseline(ch_path):
    snapshot_path = _review_snapshot_path(ch_path)
    if not os.path.isfile(snapshot_path):
        return None
    try:
        return json.load(open(snapshot_path, encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValueError(snapshot_path + ": invalid review snapshot JSON")

# 기준선을 수락할 수 있는 단위. `--accept-review-only=` 가 받는 이름들이다.
REVIEW_COLLECTIONS = ("theory", "derivation", "practice", "problems", "textbookProblems")


def acceptance_scope(only, sections, formulas):
    """이번 수락이 **덮어쓰는 컬렉션**. 순수 함수 — 수락 기록과 삼킴 판정이 같은 자를 쓴다.

    절(`sections`)·카드(`formulas`) 단위 수락은 그 컬렉션 하나만 건드린다. 셋은 함께 못 쓰므로
    (`accept_review_baseline` 이 거부한다) 분기가 겹칠 일이 없다.
    """
    if sections:
        return ("theory",)
    if formulas:
        return ("derivation",)
    return tuple(only or REVIEW_COLLECTIONS)


def accept_review_baseline(ch_path, chapter=None, only=None, sections=None, formulas=None,
                           baseline_rev=None, viewer_rev=None):
    """기준선 스냅샷을 쓴다. `only`(컬렉션)·`sections`(이론 절)·`formulas`(유도 카드)로 **부분 수락**한다.

    왜 부분 수락이 필요한가 (신설 2026-07-30, 사용자 요청):
      *[발화 생략]*
    검수는 앞에서부터 순서대로 본다. 앞부분을 다 본 상태에서 전체를 수락하면 **아직 안 본
    뒷부분의 변경 표시까지 사라진다** — 검수자가 못 본 것을 '본 것'으로 만들어 버린다.
    반대로 수락을 미루면 이미 본 앞부분이 계속 칠해져 있어 새 수정이 묻힌다.
    그래서 **본 데까지만** 수락한다. 일회성 스크립트로 하면 매 검수마다 다시 짜게 되므로
    도구에 남긴다(AGENTS 실행 규율 2).
    """
    snapshot_path = _review_snapshot_path(ch_path)
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    if chapter is None:
        chapter = json.load(open(ch_path, encoding="utf-8"))
    # ★★ 부분 수락 단위를 **섞지 않는다** (2026-08-06 · `formulas` 추가 2026-08-07).
    #   플래그 조합이 조용히 한쪽을 버리는 것이 2026-08-02 실사고의 형태였다 —
    #   여기서는 아예 거부해 그 침묵을 만들지 않는다.
    #   ★ 두 단위가 동시에 필요하면(이론 전체 + 유도 앞 2장) **두 번 돌린다.**
    #     각 호출이 기존 스냅샷 위에 병합하므로 합성이 정확하다.
    picked = [n for n, v in (("--accept-review-only", only),
                             ("--accept-review-section", sections),
                             ("--accept-review-formula", formulas)) if v]
    if len(picked) > 1:
        raise ValueError(" 와 ".join(picked) + " 는 함께 못 쓴다"
                         " (수락 단위를 하나로 정할 것 — 둘 다 필요하면 나눠서 두 번 돌린다)")
    if formulas:
        # ★ **유도 카드 단위 수락** (신설 2026-08-07, 사용자 요청).
        #   *[발화 생략]*
        #   유도는 카드를 한 장씩 넘기며 본다. 그런데 수락 단위가 **컬렉션(`only=derivation`)
        #   까지밖에 없어서**, 앞 두 장을 봤다고 말해도 옮길 방법이 *전부냐 아무것도 아니냐*
        #   둘뿐이었다 — 전부 수락하면 **아직 안 본 뒷 카드의 표시까지 사라진다.**
        #   이것은 2026-08-06 에 이론에서 닫은 것과 **같은 부류**다(그때는 절 단위를 만들었다).
        #   같은 부류가 다른 컬렉션에서 다시 열린 이유는, 그때 단위를 *이론에만* 내렸기 때문이다.
        previous = _review_baseline(ch_path)
        current = {f.get("id"): f for f in
                   ((chapter.get("derivation") or {}).get("formulas") or [])}
        unknown = [fid for fid in formulas if fid not in current]
        if unknown:
            raise ValueError("그런 유도 카드가 없다: " + ", ".join(unknown))
        if previous is None:
            print("[review baseline] 기존 스냅샷이 없어 카드 수락을 전체 수락으로 처리한다:",
                  os.path.relpath(ch_path, ROOT))
        else:
            merged = json.loads(json.dumps(previous, ensure_ascii=False))
            base = (merged.setdefault("derivation", {})).setdefault("formulas", [])
            have = {f.get("id") for f in base}
            for i, f in enumerate(base):
                if f.get("id") in formulas:
                    base[i] = current[f["id"]]
            # 기준선에 없던 카드(이번에 새로 만든 것)도 수락 대상이면 넣는다 —
            # 안 넣으면 '통째로 새것'으로 남아 계속 칠해진다(절 단위와 같은 처리).
            for fid in formulas:
                if fid not in have:
                    base.append(current[fid])
            chapter = merged
    if sections:
        # ★ **절 단위 수락** (신설 2026-08-06, 사용자 요청).
        #   *[발화 생략]*
        #   검수자가 **아직 도달하지 않은 절**의 변경 표시는 정보가 아니라 잡음이다 —
        #   그 절은 어차피 처음 읽는 글이라 '무엇이 달라졌는지'를 대조할 기억이 없다.
        #   컬렉션 단위(`only`)로는 이걸 못 한다: theory 를 통째로 수락하면 **이미 본 앞 절의
        #   표시까지 함께 지워진다.** 그래서 수락 단위를 절까지 내린다.
        previous = _review_baseline(ch_path)
        current = {s.get("id"): s for s in
                   ((chapter.get("theory") or {}).get("sections") or [])}
        unknown = [sid for sid in sections if sid not in current]
        if unknown:
            raise ValueError("그런 절이 없다: " + ", ".join(unknown))
        if previous is None:
            print("[review baseline] 기존 스냅샷이 없어 절 수락을 전체 수락으로 처리한다:",
                  os.path.relpath(ch_path, ROOT))
        else:
            merged = json.loads(json.dumps(previous, ensure_ascii=False))
            base = (merged.setdefault("theory", {})).setdefault("sections", [])
            have = {s.get("id") for s in base}
            for i, s in enumerate(base):
                if s.get("id") in sections:
                    base[i] = current[s["id"]]
            # 기준선에 아예 없던 절(이번에 새로 만든 절)도 수락 대상이면 넣어 준다 —
            # 안 넣으면 '통째로 새것'으로 남아 계속 칠해진다.
            for sid in sections:
                if sid not in have:
                    base.append(current[sid])
            chapter = merged
    if only:
        unknown = [name for name in only if name not in REVIEW_COLLECTIONS]
        if unknown:
            raise ValueError("알 수 없는 컬렉션: " + ", ".join(unknown)
                             + " (가능: " + ", ".join(REVIEW_COLLECTIONS) + ")")
        previous = _review_baseline(ch_path)
        if previous is None:
            # 기준선이 없으면 부분 수락은 의미가 없다 — 전체가 '새것'이라 비교 대상이 없다.
            print("[review baseline] 기존 스냅샷이 없어 부분 수락을 전체 수락으로 처리한다:",
                  os.path.relpath(ch_path, ROOT))
        else:
            merged = json.loads(json.dumps(previous, ensure_ascii=False))
            for name in only:
                if name in chapter:
                    merged[name] = chapter[name]
                else:
                    merged.pop(name, None)
            chapter = merged
    with open(snapshot_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(chapter, f, ensure_ascii=False, indent=2)
        f.write("\n")
    _record_acceptance(ch_path, only, sections, formulas, baseline_rev, viewer_rev)
    return snapshot_path


# ─────────────────────────────────────────────────────────────────────────────
# ★ 수락 이력 — "밀었다"를 기계가 읽을 수 있는 형태로 남긴다 (신설 2026-08-07, **재발**)
#
# 사용자: *[발화 생략]*
#
# ★★ 왜 또 났나 — 원인은 게으름이 아니라 **관측의 부재**다.
#   ⑴ 전 세션이 이론을 수락한 **뒤에** 같은 세션에서 또 고쳤고, 배치를 닫을 때 다시 밀지 않았다.
#      (AGENTS 「초기화는 배치를 닫는 마지막 단계에서 한다」가 정확히 이 자리인데, **지켰는지
#      확인하는 기계가 없었다** — 사람의 성실성에 기대고 있었다.)
#   ⑵ 그리고 그 상태를 `.claude/SUBJECT.md` 에 *[발화 생략]* 이라고 적어,
#      다음 세션이 **문서를 근거로** 그대로 두게 만들었다.
#   ⑶ `build_review` 의 출력이 **합계뿐**이라(`본문변경 22`) 그 22 안에 이론 10절이 들어 있다는
#      것이 화면에 안 보였다. 합계는 컬렉션을 감춘다.
#   → 같은 부류가 AGENTS 에 이미 *[발화 생략]* 로 적혀 있다. 네 번째다.
#
# 그래서 **수락 범위를 스냅샷 옆에 기록**한다. 이게 있어야 close 때 *[발화 생략]* 을 기계가 지목할 수 있다(`stale_acceptances`).
# 기록은 git 밖이다 — 스냅샷과 생사를 같이해야 하기 때문이다(따로 놀면 둘이 어긋난다).
def _acceptance_path(ch_path):
    return os.path.splitext(_review_snapshot_path(ch_path))[0] + ".accepted.json"


def read_acceptance(ch_path):
    """수락 이력. 없으면 `{}` — 한 번도 수락한 적 없는 챕터다."""
    path = _acceptance_path(ch_path)
    if not os.path.isfile(path):
        return {}
    try:
        return json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _head_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, encoding="utf-8").stdout.strip() or None
    except OSError:
        return None


VIEWER_CHANGE_LOG = os.path.join(ROOT, "docs", "viewer-change-log.txt")


def viewer_changes_for(ch_path, current_rev, log_path=VIEWER_CHANGE_LOG):
    r"""이 챕터를 수락한 뒤 **화면(뷰어)이 바뀌었나** — 배너에 실을 줄들. 순수 함수에 가깝다.

    ★★ **열린 날 2026-08-23, 사용자 지적:** *[발화 생략]* — 맞다. 변경점 판정의 입력이 **`chNN.json` 스냅샷 하나**라
      뷰어·템플릿·CSS 는 그 입력에 아예 없었다. 그날 하루에만 뷰어를 다섯 번 고쳤고
      (복귀 칩 · 닷 3회 · 슬라이드) **전부 검수자에게 안 보였다.**
      부류는 «화면을 바꾸는 변경 중 데이터가 아닌 것은 검수에서 통째로 사라진다» 이다.

    ★ **기계가 판정하는 것은 «바뀌었나» 하나다** — 뷰어 판본(`viewerRev` = 템플릿 sha256)이
      수락 당시와 다른가. 사람이 안 적어도 이건 늘 참이다.
    ★ **«무엇이» 는 사람이 적는다**(`docs/viewer-change-log.txt`: `날짜 | 무엇 | 어디서 보이나`).
      기계는 CSS diff 에서 «수식의 점이 얇아졌다» 를 못 만든다 — 지어내면 그게 곧
      «다른 카드의 사유를 복사한 것» 과 같은 것이 된다.
    ★ **한 번도 수락한 적 없는 챕터에는 안 띄운다** — 도달하지 않은 자리에는 변경점을
      띄우지 않는다는 규칙 그대로다. 옛 수락 기록에 `viewerRev` 가 없으면 **판정 불가라 안 띄운다**
      (안 띄우는 쪽이 «봤다» 를 지어내지 않는다).
    """
    record = read_acceptance(ch_path)
    stamps = [v for v in record.values() if isinstance(v, dict)]
    if not stamps or not current_rev:
        return []
    revs = {s.get("viewerRev") for s in stamps if s.get("viewerRev")}
    if not revs or revs == {current_rev}:
        return []                       # 수락한 판본 그대로거나, 옛 기록이라 판정할 수 없다
    since = min(s.get("at") or "" for s in stamps)
    out = []
    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "|" not in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2 or parts[0] < since:
                    continue
                out.append({"at": parts[0], "what": parts[1],
                            "where": parts[2] if len(parts) > 2 else ""})
    return out


def _record_acceptance(ch_path, only, sections, formulas, baseline_rev=None, viewer_rev=None):
    import datetime
    record = read_acceptance(ch_path)
    # ★ `rev` 는 **수락한 시각의 HEAD** 이고 `baselineRev` 는 **기준선 내용을 뜬 커밋**이다
    #   (2026-08-13 신설). 둘은 `--accept-review-rev=<과거 sha>` 에서 갈린다 — 시각만 적어
    #   두면 *[발화 생략]* 를 나중에 물을 수 없다. 오늘 사고의 진단이
    #   정확히 그것이라(시각 ≠ 화면) 기록도 둘로 가른다.
    stamp = {"at": datetime.date.today().isoformat(), "rev": _head_sha()}
    if baseline_rev:
        stamp["baselineRev"] = baseline_rev
    # ★ **어느 판본의 화면을 본 것으로 처리했나** (2026-08-23). 데이터 sha 만으로는
    #   «그 뒤 뷰어가 바뀌었나» 를 물을 수 없다 — 위 `viewer_changes_for` 주석이 정본이다.
    if viewer_rev:
        stamp["viewerRev"] = viewer_rev
    narrowed = sections or formulas          # 절·카드 단위 수락은 id 를 누적한다
    for name in acceptance_scope(only, sections, formulas):
        if narrowed:
            scope = record.get(name, {}).get("ids") or []
            record[name] = dict(stamp, ids=sorted(set(scope) | set(narrowed)))
        else:
            record[name] = dict(stamp, ids="all")
    with open(_acceptance_path(ch_path), "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def _touched_since(ch_path, rev):
    """수락 이후 그 챕터를 건드린 커밋이 있는가. 판정 불가면 `True`(안전한 쪽)."""
    if not rev:
        return True
    rel = os.path.relpath(ch_path, ROOT).replace(os.sep, "/")
    try:
        out = subprocess.run(["git", "log", "--oneline", rev + "..HEAD", "--", rel],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8")
    except OSError:
        return True
    return bool(out.stdout.strip()) or out.returncode != 0


AUTO_UNSEEN_TAG = "auto-unseen@"


def unseen_baseline_stale(ch_path, current_viewer_rev):
    """안 본 장의 기준선을 HEAD 로 다시 떠야 하나. 판정 불가면 `True`(다시 뜬다 — 안 본 장이라 잃을 것이 없다).

    재는 것: 수락 기록이 없거나, 뷰어 판본이 다르거나, 수락 뒤 그 장을 건드린 커밋이 있으면 참.
    못 보는 것: 미커밋 편집 — HEAD 를 뜨므로 커밋 → 빌드 뒤에야 표시가 사라진다.
    """
    stamps = [v for v in read_acceptance(ch_path).values() if isinstance(v, dict)]
    if not stamps or not has_review_baseline(ch_path):
        return True
    # 이 경로가 뜬 기준선만 믿는다 — 손 수락·옛 경로는 lint 정규화를 안 거쳐 가짜 표시가 남을 수 있다
    if any(not str(s.get("baselineRev") or "").startswith(AUTO_UNSEEN_TAG) for s in stamps):
        return True
    if any(s.get("viewerRev") != current_viewer_rev for s in stamps):
        return True
    return any(_touched_since(ch_path, s.get("rev")) for s in stamps)


# ─────────────────────────────────────────────────────────────────────────────
# ★★ 빌드 시점 기록 — **사용자가 본 화면은 어느 커밋인가** (신설 2026-08-13)
#
# 실사고: 사용자가 *[발화 생략]* 라고 한 **시각**의 HEAD(`36fc657`)를 ch05 기준선으로
# 잡았다. 그런데 그 직전 10분 사이에 ch05 커밋이 둘 들어와 있었다 — `4870d24`(관 안 화살표)·
# `7408c6d`(원기둥 실루엣선). 둘 다 **사용자가 요청해서 고친 것**인데 기준선이 그 뒤로
# 잡히는 바람에 **변경점 표시가 아예 안 붙었다.**
#   사용자: *[발화 생략]*
#
# ★★ 처방의 기준선은 **시각이 아니라 커밋**이다 (사용자 지적):
#   *[발화 생략]*
#   맞는 말이다 — 검수 중에 들어온 수정은 **그 사람 화면의 변경점 목록에 애초에 없다.**
#   시각은 화면과 어긋날 수 있지만 **빌드 sha 는 안 어긋난다**(화면 = 빌드 산출물).
#   그래서 빌드가 자기 시점을 남기고, 수락은 **그 sha** 를 기준으로 삼는다.
#
# 자리를 스냅샷 옆에 두는 이유는 `accepted.json` 과 같다 — 기준선과 **생사를 같이해야**
# 둘이 어긋나지 않는다(`.review-snapshot/` 은 `.gitignore` 라 커밋에 안 실린다).
#
# ★ 남는 구멍은 밝혀 둔다: 사용자가 **더 옛날 빌드 화면을 열어 둔 채** 읽고 있었으면 그것까지는
#   관측할 수 없다. 그래서 `history` 에 최근 빌드 sha 를 남겨, 거부 출력이 *[발화 생략]* 를
#   사람이 고를 수 있게 보여 준다(`--accept-review-rev=<그 sha>`).
BUILD_RECORD_KEEP = 10


def _rel(ch_path):
    return os.path.relpath(ch_path, ROOT).replace(os.sep, "/")


def _git(args):
    """git 한 번. 실패하면 `None` — 호출부가 **판정 불가**로 다루게 한다(조용한 0 이 아니다)."""
    try:
        out = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8")
    except OSError:
        return None
    return out.stdout if out.returncode == 0 else None


def _build_record_path(ch_path):
    return os.path.splitext(_review_snapshot_path(ch_path))[0] + ".built.json"


def read_build_record(ch_path):
    """그 챕터를 **마지막으로 빌드한 시점**. 없으면 `{}` — 화면의 관측이 없다는 뜻이다."""
    path = _build_record_path(ch_path)
    if not os.path.isfile(path):
        return {}
    try:
        return json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def chapter_is_dirty(ch_path):
    """그 챕터 데이터에 **미커밋 변경**이 있는가. 판정 불가면 `None`(빈 것과 구별한다)."""
    out = _git(["status", "--porcelain", "--", _rel(ch_path)])
    return None if out is None else bool(out.strip())


def record_build(ch_path, rev=None, dirty=None):
    """빌드가 자기 시점을 남긴다 — **화면이 어느 커밋에서 나왔는가**의 유일한 관측.

    `dirty` 가 참이면 그때 화면은 **어느 커밋과도 같지 않다**(미커밋 변경이 섞였다) —
    그 사실을 함께 적어야 나중에 *[발화 생략]* 는 거짓 결론을 막는다.
    """
    rev = _head_sha() if rev is None else rev
    dirty = chapter_is_dirty(ch_path) if dirty is None else dirty
    import datetime
    previous = read_build_record(ch_path)
    history = previous.get("history") or []
    if previous.get("rev") and previous.get("rev") != rev:
        history = ([{k: previous.get(k) for k in ("rev", "at", "dirty")}]
                   + history)[:BUILD_RECORD_KEEP]
    record = {"rev": rev, "at": datetime.datetime.now().isoformat(timespec="seconds"),
              "dirty": bool(dirty), "history": history}
    path = _build_record_path(ch_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return record


def commits_touching(ch_path, old_rev, new_rev, log=None):
    """`old_rev..new_rev` 사이에 **그 챕터를 건드린** 커밋 `[(sha, 제목), …]`.

    `log(rel, old, new)` 를 넘기면 git 대신 그것을 쓴다 — 테스트가 실제 리포를 안 건드리는 자리다.
    판정 불가(git 실패·모르는 sha)면 `None` 이다. **빈 목록과 구별한다** — 이 리포에서
    *[발화 생략]* 을 *[발화 생략]* 로 읽는 것이 반복된 실패다(AGENTS 규칙 11).
    """
    if log is not None:
        return log(_rel(ch_path), old_rev, new_rev)
    if not old_rev or not new_rev:
        return None
    out = _git(["log", "--format=%h\t%s", old_rev + ".." + new_rev, "--", _rel(ch_path)])
    if out is None:
        return None
    rows = []
    for line in out.splitlines():
        sha, _sep, subject = line.partition("\t")
        if sha.strip():
            rows.append((sha.strip(), subject.strip()[:90]))
    return rows


# 삼킴 판정의 종류. **`commit` 만 sha 로 승인된다** — 나머지는 처방이 다르다(빌드·커밋).
SWALLOW_KINDS = ("unbuilt", "dirty", "uncommitted", "unknown", "commit")


def baseline_move_findings(ch_path, target_rev, working_tree=False, record=None,
                           log=None, dirty_now=None, baseline_exists=None):
    """기준선을 `target_rev` 로 밀기 **전에** 묻는다 — 사용자가 못 본 것이 삼켜지는가.

    반환 `[(kind, sha, note), …]`. **빈 목록이면 밀어도 된다.**
    `record`·`log`·`dirty_now` 를 넘기면 git·파일을 전혀 안 탄다(테스트가 그렇게 부른다).

      | kind | 무엇 | sha 승인 |
      |---|---|---|
      | `unbuilt`     | 빌드 기록이 없다 = 어느 화면을 봤는지 관측이 없다 | 아니오 — 먼저 빌드 |
      | `dirty`       | 미커밋 변경이 섞인 채로 빌드된 화면이다 | 아니오 — 커밋하고 다시 빌드 |
      | `uncommitted` | 작업 트리를 기준선으로 삼는데 그 트리가 더럽다 | 아니오 — 커밋하고 민다 |
      | `unknown`     | git 이 답을 못 했다 | 아니오 |
      | `commit`      | 마지막 빌드 **이후** 이 챕터로 들어온 커밋 | **예** |

    ★ 왜 「마지막 빌드」가 기준인가 — 사용자가 본 것은 그 빌드 산출물이고, 그 뒤에 들어온
      수정은 **그 화면의 변경점 목록에 없다.** 그것을 기준선에 넣으면 *본 적 없는 것을 본 것으로*
      만드는 것이다. 위 「빌드 시점 기록」 주석이 정본이다.
    """
    # ★ **한 번도 수락한 적 없는 챕터는 삼킬 것이 없다.** 기준선이 아직 없으면 화면에 변경
    #   표시 자체가 없고(=사용자가 잃을 마크가 없고), AGENTS 도 *[발화 생략]* 며 미검수 챕터를 HEAD 로 밀라고 한다. 여기서 막으면 그 정상
    #   동작이 통째로 잠긴다.
    exists = (_review_baseline(ch_path) is not None) if baseline_exists is None else baseline_exists
    if not exists:
        return []
    record = read_build_record(ch_path) if record is None else record
    built = (record or {}).get("rev")
    if not built:
        return [("unbuilt", "", "빌드 기록이 없다 — 사용자가 어느 화면을 봤는지 관측이 없다")]
    out = []
    if (record or {}).get("dirty"):
        out.append(("dirty", built,
                    "미커밋 변경이 섞인 채로 빌드된 화면이다 — " + built[:7]
                    + " 커밋과도 같지 않아 무엇을 봤는지 대조할 수 없다"))
    if working_tree:
        dirty = chapter_is_dirty(ch_path) if dirty_now is None else dirty_now
        if dirty is None:
            out.append(("unknown", "", "지금 작업 트리가 더러운지 git 이 답을 못 했다"))
        elif dirty:
            out.append(("uncommitted", "",
                        "지금 작업 트리에 미커밋 변경이 있다 — 커밋한 뒤에 밀어야 화면과 맞는다"))
    commits = commits_touching(ch_path, built, target_rev, log=log)
    if commits is None:
        out.append(("unknown", "", "git 이 " + str(built) + ".." + str(target_rev) + " 를 못 읽었다"))
    else:
        out.extend(("commit", sha, subject) for sha, subject in commits)
    return out


def unacknowledged_swallows(findings, acknowledged=None):
    """승인되지 않은 채 삼켜질 것만 남긴다. **판정은 이 함수 하나다.**

    `findings` 는 `[(rel, kind, sha, note), …]`(챕터 경로를 앞에 붙인 것),
    `acknowledged` 는 `--accept-review-user-saw` 가 받은 sha 목록이다.
    빈 목록이면 통과 — `main()` 에 같은 조건을 다시 적지 않는다(두 곳에 적으면 갈라진다).

    ★ 커밋만 sha 로 승인된다. `unbuilt`·`dirty`·`uncommitted` 는 **플래그로 못 푼다** —
      처방이 *[발화 생략]* 라서, 그 자리에 우회로를 내면 규칙이 곧 꺼진다
      (`reviewHold` 에 `--force` 를 안 만든 것과 같은 이유).
    """
    seen = [s.strip().lower() for s in (acknowledged or []) if s and s.strip()]
    left = []
    for rel, kind, sha, note in findings:
        low = (sha or "").lower()
        if kind == "commit" and low and any(low.startswith(s) or s.startswith(low) for s in seen):
            continue
        left.append((rel, kind, sha, note))
    return left


def _collection_items(chapter, name):
    if name == "theory":
        return (chapter.get("theory") or {}).get("sections") or []
    if name == "derivation":
        return (chapter.get("derivation") or {}).get("formulas") or []
    if name == "textbookProblems":
        # ★ `textbookProblems` 는 배열이 아니라 {source, note, items} 객체다(2026-09-13
        #   실사고 — 다른 컬렉션처럼 `chapter.get(name) or []` 로 받으면 dict 자체가 "항목 목록"
        #   행세를 해 답 변경이 추가/수정/삭제 0건으로 조용히 사라졌다).
        return (chapter.get("textbookProblems") or {}).get("items") or []
    return chapter.get(name) or []


def marks_by_collection(marked_chapter):
    """변경 표시를 **컬렉션별 id 목록**으로 준다. 순수 함수 — 테스트가 직접 부른다.

    합계만 보면 *[발화 생략]* 안에 이론 10절이 들어 있는지 알 수 없다 — 그 눈멂이 이 부류의
    재발 경로였다(위 주석 ⑶).

    ★★ 인자는 **이미 표시가 붙은 챕터**다 — 여기서 다시 계산하지 않는다.
      한 번 그렇게 짰다가 빌드와 **1건 어긋났다**(ch12 `sec-polar-cylindrical`: HTML 10 vs 11).
      빌드는 `resolve_review_prerequisites` → `lint_chapter` → `add_review_changes` 순으로
      돌고 앞 두 단계가 데이터를 만지는데, 그 순서를 여기서 **베껴 쓰면 언젠가 또 갈라진다.**
      → 세는 쪽은 **빌드가 내놓은 것을 읽기만 한다**(`marks_from_built_html`). 판정이 하나면
      갈라질 자리가 없다 — 이 리포가 여러 번 닫아 온 부류의 정석 처방이다.
    """
    return {name: [item.get("id") for item in _collection_items(marked_chapter, name)
                   if item.get("_changed")]
            for name in REVIEW_COLLECTIONS}


def marks_from_built_html(html_path):
    """빌드가 산출물에 심어 둔 `var CH = …` 를 그대로 읽는다 — 화면의 정본.

    반환 `(marked_chapter, marks_by_collection)`. 산출물이 없거나 마커가 깨졌으면 `(None, {})`.
    """
    try:
        html = open(html_path, encoding="utf-8").read()
    except OSError:
        return None, {}
    # ★ **한 줄**로 심긴다(`json.dumps` 에 indent 가 없다) — 그 줄만 떼어 읽는다.
    #   처음엔 `render.py` 의 재주입 마커(`;\n\nfunction esc`)를 그대로 베꼈는데, 산출물에는
    #   그 사이에 `var SUBJECT_NAV = …` 등 네 줄이 더 들어가 **한 번도 안 맞았다.**
    #   그런데 실패가 `(None, {})` 이라 **보고가 조용히 비었다** — 침묵하는 실패가 이 리포에서
    #   가장 비싼 형태다(빈 출력이 '0건'과 구별되지 않는다). 그래서 회귀로 잠근다.
    prefix = "var CH = "
    line = next((ln for ln in html.replace("\r\n", "\n").split("\n")
                 if ln.startswith(prefix)), None)
    if line is None:
        return None, {}
    try:
        chapter = json.loads(line[len(prefix):].strip().rstrip(";"))
    except json.JSONDecodeError:
        return None, {}
    return chapter, marks_by_collection(chapter)


def visible_collections(chapter):
    """화면에 탭이 뜨는 컬렉션. 비어 있거나 `hiddenTabs` 로 감춘 것은 뺀다.

    판정 기준은 뷰어와 같다 — 화면에서 안 보이는 것을 *[발화 생략]* 으로 올리면
    안 본다고 한 것을 보라는 뜻이 된다(AGENTS 「확인하실 자리」).
    """
    hidden = set(chapter.get("hiddenTabs") or [])
    return tuple(name for name in REVIEW_COLLECTIONS
                 if name not in hidden and _collection_items(chapter, name))


def stale_acceptances(ch_path, chapter, marks, touched=None):
    """**수락했다고 해 놓고 정작 안 민** 자리. 순수 판정 — 테스트가 직접 부른다.

    반환: `[(컬렉션, 남은 id 목록, 수락 날짜), …]`. 빈 리스트면 밀 것이 없다.

    ★★ **수락 뒤에 새로 고친 것과 구별해야 한다** (2026-08-07, 첫 구현의 결함).
      처음엔 *[발화 생략]* 로 짰는데, 그러면 **지적을 받아 고친 배치마다
      울린다.** 그 표시는 잘못이 아니라 *[발화 생략]* 라는 보고이고,
      사용자가 그것을 보고 다시 "봤어" 할 때 미는 것이 정상 흐름이다.
      울리지 않아야 할 때 우는 자는 **꺼진다** — 이 리포가 경고 잔량으로 이미 겪은 부류다.
      → **수락 시점의 커밋(`rev`) 이후 그 챕터를 건드린 커밋이 있는가**로 가른다.
        있으면 새 작업이라 정상, 없는데 표시가 남았으면 **수락이 안 먹은 것**이다.
      `touched` 를 넘기면 git 을 안 타고 그 값을 쓴다(테스트용).
    """
    record = read_acceptance(ch_path)
    if not record:
        return []
    visible = set(visible_collections(chapter))
    out = []
    for name, info in sorted(record.items()):
        if name not in visible:
            continue                      # 숨긴 탭은 화면에 없으니 검수 대상이 아니다
        moved_on = (_touched_since(ch_path, info.get("rev")) if touched is None else touched)
        if moved_on:
            continue                      # 수락 뒤에 또 고쳤다 — 그 표시는 정상이다
        ids = info.get("ids")
        left = ([i for i in marks.get(name) or []]
                if ids == "all" else
                [i for i in marks.get(name) or [] if i in set(ids or ())])
        if left:
            out.append((name, left, info.get("at")))
    return out


def chapter_at_revision(ch_path, revision):
    rel_path = os.path.relpath(ch_path, ROOT).replace(os.sep, "/")
    result = subprocess.run(
        ["git", "show", revision + ":" + rel_path],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise ValueError(revision + ":" + rel_path + ": invalid chapter JSON")

def _items_by_id(items):
    return {str(item["id"]): item for item in items if item.get("id") is not None}


# ── 변경 규모 3단계 (신설 2026-07-29, 인박스 I항목) ────────────────────────────
#
# 사용자: *[발화 생략]*
#
# 지금까지 변경 표시는 **이진**이었다 — 바뀌었나/아닌가. 그래서 좌표 0.1px 조정과
# 문장 전면 교체가 화면에서 같은 색으로 보였고, 검수자는 어디에 힘을 줄지 알 수 없었다.
# 승인된 3단계(2026-07-28): `신규·전면 / 내용 일부 / 표기·크기·위치만`.
#
# ★★★ **정본은 한 줄이다: 독자가 화면에서 알아볼 수 있는 변화만 변경으로 센다.**
#   아래 판정선들(삽화 좌표 10px · 저자 전용 필드)은 전부 이 한 줄의 얼굴이다.
#   판정이 애매하면 규칙을 늘리기 전에 이 줄로 되돌아온다.
#
# ★★ **2026-08-13 개정 — 셋째 단계(`cosmetic`)를 없앤다.** 사용자 판정:
#   *[발화 생략]*
#
# ★ 진단: '표기만' 은 **판정을 미루는 이름**이었다. 화면에서는 접어 두고 토글을 한 단계 더
#   거치게 했는데, 검수자에게 필요한 답은 *볼 것인가 아닌가* 하나다. 게다가 그 구조는 실제로
#   무너져 있었다 — 실측(ch01, 2026-08-13): 요약은 **수정 25** 인데 접기를 풀어도 화면 마크는
#   **4**. 버튼이 *[발화 생략]* 이라고 말하면서 아무것도 보여주지 않았다.
# → 판정을 **이진**으로 되돌린다. 볼 것이면 센다(major/minor), 아니면 **아예 안 만든다**(`None`).
#   요약·목록·화면 셋이 **그 하나의 판정만** 읽는다 — 두 곳이 따로 판정하면 갈라진다
#   (2026-08-07 *[발화 생략]* 가 같은 부류였다).
CHANGE_LEVELS = ("major", "minor")
_MAJOR_SIMILARITY = 0.5      # 이보다 덜 닮았으면 사실상 다시 쓴 것

# ★ 삽화에서 **좌표만** 움직였을 때, 안 보고 넘어가도 되는 최대 이동량(화면 실효 px).
#   근거 두 줄이 이 값을 양쪽에서 조인다(사용자 판정 2026-08-13):
#     ⑴ 아래쪽 — 사용자 기존 원칙 *[발화 생략]*.
#        도구가 한꺼번에 미는 미세 정렬(치수보조선 4/10px 규격 맞추기 등)이 하이라이트를
#        통째로 덮는 일이 없어야 하므로 그보다 여유를 둔다.
#     ⑵ 위쪽 — 그보다 크게 움직였으면 **형상이 달라진 것**이라 놓치면 안 된다. 그래서 상한이다.
#   자는 이 리포가 글자·치수 규격에서 쓰는 것과 **같은 자**다: SVG 좌표 x 612 / viewBox 폭.
#   값을 바꾸려면 위 두 근거부터 다시 볼 것 — 숫자만 고치면 다음 세션이 근거 없이 되돌린다.
_COORD_NOISE_PX = 10.0

# ★★ **독자 화면에 안 나오는 필드만 바뀐 것은 「변경」이 아니다** (신설 2026-08-13, 사용자 지적).
#
#   *[발화 생략]* — 실측하니 그 절의 독자 화면은 한 글자도
#   안 바뀌었고, 달라진 것은 `changeNote` 하나였다(끝난 배치의 사유를 `clear_change_notes` 로
#   걷어낸 자국).
#   ★ 이걸 안 빼면 **사유를 지운 것 자체가 다음 배치의 변경점으로 뜬다** — 그 잡음은 스스로를
#     재생산하므로 영원히 끝나지 않는다.
#
#   ★ 방향은 **명단에 적은 것만 뺀다(블랙리스트)**. 화이트리스트로 짜면 새로 생긴 *내용* 필드가
#     조용히 안 보이게 되는데, 그것이 이 판정에서 가장 비싼 실패다 — 모르는 필드는 **세는 쪽**이
#     기본값이어야 한다.
#   ★ 명단은 **뷰어를 실제로 훑어** 잡았다(2026-08-13, 추측 아님):
#       `changeNote` — `reviewNote()` 가 **검수 툴팁**으로만 쓴다. 독자 렌더러에 없다.
#       `sourceRef`  — 뷰어가 *[발화 생략]* 고 명시하고 데이터에만 남긴다.
#       `rationale`  — 삽화가 왜 필요한가를 적는 저자 메모. 뷰어에 등장하지 않는다.
#     `kind` 는 **넣지 않는다** — 삽화에서는 딱지로 렌더된다(`kindLabel[d.kind]`).
#       `objectives` — 문항·자가점검의 학습목표 태그. 뷰어는 진도 판정에만 읽고 글자로 안 그린다.
#       `basis`      — 학습목표의 근거(교재 절·분모 번호). 뷰어에 등장하지 않는다(2026-09-19 — 태그만 단
#                      전전 ch01 에서 사유 없는 하이라이트 다섯이 떴다).
AUTHOR_ONLY_FIELDS = ("changeNote", "sourceRef", "rationale", "objectives", "basis")


def reader_facing(value):
    """저자 전용 필드를 걷어낸 사본. dict 가 아니면 그대로 돌려준다."""
    if not isinstance(value, dict):
        return value
    return {k: v for k, v in value.items()
            if k not in AUTHOR_ONLY_FIELDS and not str(k).startswith("_")}


def _svg_texts_only(value):
    """SVG 문자열에서 **글자 내용만** 뽑는다 — 좌표·굵기·색은 버린다.

    삽화의 '표기·크기·위치만 바뀐 것'을 가려내는 핵심이다. 사용자가 명시적으로 든 예가
    *[발화 생략]* 인데, SVG 원문끼리 비교하면 font-size 하나만 바뀌어도
    문자열 차이가 커서 '내용 변경'으로 잡힌다. 글자만 남기면 그 구분이 성립한다.
    """
    return "".join(re.findall(r"<text[^>]*>(.*?)</text>", value or "", re.S))


def _svg_glyphs(value):
    """`_svg_texts_only` 에서 **안쪽 태그까지 벗긴** 순수 글자 (신설 2026-08-13).

    첨자는 `<tspan dy=…>` 로 조판되는데, 그 `dy` 는 **좌표**이지 글자가 아니다. 안 벗기면
    1px 첨자 조정이 '글자가 바뀐 것' 으로 잡혀 아래 좌표 판정에 **아예 닿지 못한다.**
    """
    return re.sub(r"<[^>]*>", "", _svg_texts_only(value))


# 좌표를 담는 속성. 여기 **없는** 속성값(색·굵기·글꼴·클래스)은 모양 서명으로 간다 —
# 그쪽이 다르면 화면에서 알아볼 수 있으므로 무조건 변경으로 센다(안전한 쪽이 기본값).
_COORD_ATTRS = frozenset((
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
    "width", "height", "d", "points", "transform", "gradientTransform",
    "viewBox", "dx", "dy", "offset", "fx", "fy",
    "refX", "refY", "markerWidth", "markerHeight", "startOffset",
))
_SVG_TOKEN_RE = re.compile(
    r"<\s*(/?)([A-Za-z][-\w:.]*)"                          # 여는·닫는 태그
    r"|([A-Za-z_:][-\w:.]*)\s*=\s*(\"[^\"]*\"|'[^']*')")   # 속성="값"
_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_VIEWBOX_RE = re.compile(r"viewBox\s*=\s*[\"']\s*[-+\d.eE]+\s+[-+\d.eE]+\s+([\d.]+)")


def svg_shape_and_coords(value):
    """SVG를 **모양 서명**과 **좌표 수열**로 가른다. 순수 함수 — 테스트가 직접 부른다.

    서명에는 태그 순서와 *좌표가 아닌* 속성값(색·굵기·글꼴)이 들어가고, 좌표 속성은 **이름만**
    들어간다(값은 수열로 따로 잰다). 그래서 *색이 바뀌었나* 와 *얼마나 움직였나* 를 섞지 않고
    각각 물을 수 있다 — 이 둘을 한 자로 재려던 것이 옛 `cosmetic` 판정의 결함이었다.
    """
    shape, coords = [], []
    for m in _SVG_TOKEN_RE.finditer(value or ""):
        if m.group(2) is not None:
            shape.append("<" + m.group(1) + m.group(2))
            continue
        name, raw = m.group(3), m.group(4)[1:-1]
        if name in _COORD_ATTRS:
            shape.append(name)
            coords.extend(float(tok) for tok in _NUM_RE.findall(raw))
        else:
            shape.append(name + "=" + raw)
    return shape, coords


def _svg_screen_scale(value):
    """SVG 좌표 1 이 화면에서 몇 px 인가. viewBox 를 못 읽으면 1(좌표를 그대로 px 로 본다)."""
    m = _VIEWBOX_RE.search(value or "")
    try:
        width = float(m.group(1)) if m else 0.0
    except ValueError:
        width = 0.0
    return (FIGURE_RENDER_WIDTH / width) if width > 0 else 1.0


def _similarity(old, new):
    return difflib.SequenceMatcher(None, old or "", new or "").ratio()


def classify_svg_change(old_svg, new_svg):
    """삽화 변경의 판정. `None` 이면 **변경이 아니다** — 요약·목록·화면 어디에도 안 나온다.

    판정선은 사용자가 정했다 (2026-08-13):

      | 삽화 변경                        | 판정 |
      |---------------------------------|------|
      | **글자 내용**이 다르다            | 센다 (닮은 정도로 major/minor) |
      | 글자는 같은데 **크기·색**이 다르다 | 센다 (minor) — 화면에서 알아볼 수 있다 |
      | 좌표만 다른데 최대 이동 <= 10px   | **안 센다** |
      | 좌표만 다른데 최대 이동 > 10px    | 센다 (minor) — 형상이 달라진 것이다 |
    """
    old_texts, new_texts = _svg_glyphs(old_svg), _svg_glyphs(new_svg)
    if old_texts != new_texts:
        # ★ 비율도 **글자끼리** 잰다. SVG 원문끼리 재면 라벨 한 단어를 갈아치워도
        #   전체 문자열의 98%가 같아 묻힌다(회귀 케이스가 이걸 잡았다).
        return "major" if _similarity(old_texts, new_texts) < _MAJOR_SIMILARITY else "minor"
    old_shape, old_coords = svg_shape_and_coords(old_svg)
    new_shape, new_coords = svg_shape_and_coords(new_svg)
    if old_shape != new_shape:
        return "minor"          # 색·굵기·글꼴이 바뀌었거나 도형이 늘고 줄었다
    if len(old_coords) != len(new_coords):
        return "minor"          # 좌표 개수가 다르면 형상이 달라진 것이다
    shift = max((abs(a - b) for a, b in zip(old_coords, new_coords)), default=0.0)
    return "minor" if shift * _svg_screen_scale(new_svg) > _COORD_NOISE_PX else None


def _classify_change(old_value, new_value, is_svg=False):
    """두 값의 변경 규모. `None` 이면 **변경으로 세지 않는다.** 순수 함수 — 테스트 대상.

    ★ 비-SVG 값은 **글자가 다르면 무조건 센다**(개정 2026-08-13). 옛 구현은 문자열 유사도
      0.98 을 넘으면 `cosmetic` 으로 접었는데, 유사도는 *얼마나 많이* 바뀌었는지를 재지
      *무엇이* 바뀌었는지를 재지 않는다. 한 문단에서 글자 몇 개만 바뀌면 유사도는 언제나
      0.98 을 넘으므로 **표기 통일 작업은 구조적으로 전부 감춰졌다**(속도 기호를 필기체로
      옮긴 배치가 그렇게 통째로 사라졌다).
      *어느 필드를 볼 것인가* 는 유사도가 아니라 호출부의 필드 명단과 `AUTHOR_ONLY_FIELDS` 가
      정한다 — 자가 재는 것과 판정해야 하는 것이 다르면 그 자는 언제나 엉뚱한 곳을 가린다.
    """
    if old_value is None:
        return "major"
    if is_svg:
        return classify_svg_change(old_value, new_value)
    old_text = json.dumps(reader_facing(old_value), ensure_ascii=False, sort_keys=True)
    new_text = ("" if new_value is None
                else json.dumps(reader_facing(new_value), ensure_ascii=False, sort_keys=True))
    return "major" if _similarity(old_text, new_text) < _MAJOR_SIMILARITY else "minor"


def _worst(levels):
    """가장 무거운 단계를 고른다 — 한 항목 안에 여러 변경이 섞이면 큰 쪽으로 표시한다."""
    for level in CHANGE_LEVELS:
        if level in levels:
            return level
    return None


# ── 배열 필드의 **원소 단위** 표시 (신설 2026-07-29) ──────────────────────────
#
# 사용자 지적: *[발화 생략]*
#
# 새어나간 구조: 아래 `_compare_review_items` 는 **필드 단위**로만 비교한다
# (`item.get(field) != old_item.get(field)`). `comprehensionChecks` 는 배열 하나가 한 필드라
# 체크 한 개만 고쳐도 필드 전체가 '변경'이 되고, 템플릿이 그 배열을 통째로 감싸므로
# 손대지 않은 항목까지 하이라이트된다. 검수자가 **안 바뀐 것을 다시 읽게 만드는** 결함이다.
#
# ★ 여기 넣은 필드는 템플릿이 **원소마다** reviewClass 를 붙여야 한다. 안 그러면 부모의
#   표시만 사라지고 원소 표시는 없어서 **변경이 통째로 안 보이게 된다** — 너무 넓은 것보다
#   나쁘다. 그래서 명단을 좁게 두고, 회귀 테스트가 명단과 템플릿의 일치를 강제한다
#   (test_review_marks_only_changed_elements).
GRANULAR_FIELDS = ("comprehensionChecks", "pitfalls")

# ★ 이 명단이 「독자가 화면에서 알아볼 수 있는 변화만 센다」의 첫 관문이다 —
#   `changeNote`·`sourceRef` 같은 저자 전용 필드는 **여기 들어오면 안 된다**
#   (들어오면 사유를 지운 것 자체가 다음 배치의 변경점이 된다. `AUTHOR_ONLY_FIELDS` 주석).
#
# ★★ **모듈 상수로 둔다 — 함수 안에 두면 테스트가 못 본다.** 2026-08-14 에 밖으로 뺐다.
#   이 리포가 `deny_reason()`·`follow_up_issues()` 를 순수 함수로 빼 둔 것과 같은 이유다.
#
# ★★ `derivation` 의 `comprehensionChecks` 는 **뒤늦게 넣은 것이고, 재발이다** (2026-08-14).
#   실측: ch05 유도 카드 `ke-pe-negligibility` 안의 체크에 `followUp` 을 더했는데 빌드가
#   *[발화 생략]* 로 신고했다. 같은 배치의 **이론 절 둘은
#   정상으로 잡혔다** — 컬렉션마다 명단이 갈려서 생긴 구멍이다.
#   2026-07-21 에 같은 모양을 이미 한 번 닫았다: *[발화 생략]*. 그때는 **검사**였고 이번은 **변경점 판정**이라
#   자리만 달랐을 뿐, 「같은 필드가 두 컬렉션에 사는데 한쪽만 본다」는 똑같다.
#   진도 모드가 이론·유도라 **유도 변경이 안 보이면 검수 자체가 불가능**했다.
#
# ★ 그래서 명단을 손으로 맞추는 데서 끝내지 않는다 — **데이터에 체크가 있는 컬렉션은 전부
#   여기 있어야 한다**를 회귀가 강제한다(`test_review_fields_cover_every_check_owner`).
#   손으로 맞추는 명단은 새 컬렉션이 생기는 날 다시 갈린다.
REVIEW_FIELDS = {
    "theory": ["content", "comprehensionChecks", "pitfalls"],
    "derivation": ["latex", "derivationSteps", "notes", "variables",
                   "comprehensionChecks"],
    "practice": ["prompt", "solutionTemplate", "blanks", "expectedOutput"],
    "problems": ["prompt", "answer", "solutionOutline"],
    "textbookProblems": ["why", "answer", "outline"],
}

# ── 긴 글의 **단락 단위** 표시 (신설 2026-08-05) ────────────────────────────────
#
# 사용자 지적: *[발화 생략]*
#
# ★★ **위 배열 건과 같은 부류인데 한 층 아래다.** 2026-07-29 에 배열 필드(`pitfalls` 등)를
#   원소 단위로 좁혔지만 **긴 문자열 필드는 그대로 두었다.** `content` 는 값 하나라
#   `item.get(field) != old_item.get(field)` 가 참이 되는 순간 **절 본문 전체**가 칠해진다 —
#   한 줄만 넣어도 스무 단락을 다시 읽게 만든다. 그때 고친 것은 *배열*이지 *덩어리*가 아니었다.
#
# 뷰어는 이 문자열을 `\n{2,}` 로 잘라 단락으로 렌더한다(`renderTheoryBody`·`fmtText`).
# 그러니 **같은 규칙으로 잘라** 달라진 단락의 인덱스만 넘기면 된다.
# 판정은 배열 때와 같은 이유로 **내용 대조**다 — 인덱스로 맞추면 앞에 한 단락만 끼워 넣어도
# 뒤가 전부 변경으로 잡힌다(그게 지금 고치려는 증상 그 자체다).
#
# ★ 여기 넣은 필드는 템플릿이 **단락마다** 표시를 붙여야 한다. 안 그러면 부모 표시만 사라져
#   변경이 통째로 안 보이게 된다 — 너무 넓은 것보다 나쁘다. 회귀가 그 일치를 강제한다
#   (`test_review_marks_only_changed_paragraphs`).
PARAGRAPH_FIELDS = ("content",)
_PARA_SPLIT = re.compile(r"\n{2,}")


def paragraphs_of(text):
    """뷰어와 **같은 규칙**으로 단락을 나눈다 — `fmtText`·`renderTheoryBody` 의 `\\n{2,}`.

    자를 둘로 두면 인덱스가 밀려 엉뚱한 단락이 칠해진다.
    """
    return _PARA_SPLIT.split(str(text)) if isinstance(text, str) else []


def changed_paragraph_indexes(new_text, old_text):
    """달라진 단락의 인덱스 목록 (전부 그대로면 빈 목록). 순수 함수 — 테스트가 부른다.

    `None` 을 돌려주면 '단락으로 못 나눈다'는 뜻이라 부모를 통째로 칠하는 옛 동작으로 돌아간다.
    """
    if not isinstance(new_text, str) or not isinstance(old_text, str):
        return None
    new_paras = paragraphs_of(new_text)
    if len(new_paras) < 2:
        return None                   # 단락이 하나뿐이면 좁힐 것이 없다
    old_seen = set(paragraphs_of(old_text))
    return [i for i, para in enumerate(new_paras) if para not in old_seen]


def _mark_changed_elements(new_list, old_list):
    """배열에서 **실제로 달라진 원소만** `_changed` 로 표시한다. 순수 함수 — 테스트 대상.

    판정 기준은 '옛 배열에 같은 내용이 있었는가'다. 원소에 id 가 없는 경우가 있어
    (pitfalls 가 그렇다) id 대조를 쓸 수 없고, 인덱스 대조는 항목 하나를 끼워 넣으면
    뒤쪽 전부가 변경으로 잡힌다. 내용 대조는 순서가 바뀌어도 오탐이 없다.
    """
    if not isinstance(new_list, list):
        return False
    if not any(isinstance(el, dict) for el in new_list):
        return False  # 문자열 배열은 원소에 속성을 붙일 수 없다 — 부모 표시를 그대로 둔다

    # ★ 대조는 **독자에게 보이는 것끼리** 한다 (2026-08-13). `changeNote` 같은 저자 전용
    #   필드까지 넣고 비교하면, 지난 배치의 사유를 지운 자국이 이번 배치의 변경으로 뜬다.
    def content_key(el):
        return json.dumps(reader_facing(el), ensure_ascii=False, sort_keys=True)

    old_items = [el for el in (old_list or []) if isinstance(el, dict)]
    old_keys = {content_key(el) for el in old_items}
    old_by_id = _items_by_id(old_items)

    for el in new_list:
        if not isinstance(el, dict):
            continue
        if content_key(el) in old_keys:
            continue  # 내용이 그대로다 — 손댄 적이 없다
        old_el = old_by_id.get(str(el.get("id"))) if el.get("id") is not None else None
        el["_changed"] = ["item"]
        el["_changeLevel"] = _classify_change(old_el, el)
    return True


def classify_diagram_change(old, new):
    """삽화 하나의 변경 규모. `None` 이면 변경이 아니다. 순수 함수 — 테스트가 부른다.

    ★ **svg 밖(캡션 종류·revealMode 등)의 변경을 좌표 자에 태우지 않는다.** 좌표 판정만 쓰면
      svg 를 안 건드린 변경이 '움직인 것이 없다'로 사라진다 — **안 보이게 하는 쪽으로 틀리는
      것**이 이 판정에서 가장 비싼 실수다. 저자 전용 필드는 `reader_facing` 이 먼저 걷어낸다.
    """
    if old is None:
        return "major"
    levels = []
    if reader_facing(old) != reader_facing(new):
        # svg 는 아래에서 따로 잰다 — 여기서는 나머지 필드만 본다.
        rest_old = dict(reader_facing(old));  rest_old.pop("svg", None)
        rest_new = dict(reader_facing(new));  rest_new.pop("svg", None)
        if rest_old != rest_new:
            levels.append(_classify_change(rest_old, rest_new))
    if old.get("svg") != new.get("svg"):
        levels.append(_classify_change(old.get("svg"), new.get("svg"), is_svg=True))
    level = _worst([level for level in levels if level])
    if level is None and reader_facing(old) != reader_facing(new) \
            and author_asked_to_show(old, new):
        return "minor"
    return level


def author_asked_to_show(old, new):
    """저자가 **이번 배치에** 사유를 적었으면 좌표 문턱을 건너뛴다 (신설 2026-08-23).

    사용자: *[발화 생략]*.
    실측 — 기계재료 `fig-course-map` 의 화살표 셋을 6 좌표(화면 실효 **5.2px**) 옮겨
    사용자가 지적한 결함을 고쳤는데, `_COORD_NOISE_PX` 10 아래라 요약·목록·화면 어디에도
    안 나왔다. **고쳐 달라고 한 사람이 고쳐졌는지 확인할 방법이 없었다.**

    ★ **문턱을 낮추지 않는다.** 10px 는 *도구가 한꺼번에 미는 미세 정렬*(치수보조선 4/10px
      규격 맞추기 등)을 지우려고 있고 그 근거는 그대로다. 여기서 가르는 것은 **크기가 아니라
      출처**다 — 지적을 받아 고친 6px 와 자가 알아서 민 6px 는 같은 수라도 다른 사건이다.
      좌표만 보는 기계는 둘을 못 가르므로 **저자의 선언**을 입력으로 받는다
      (`class='dim'`·`kind` 선언과 같은 형태 — 기계가 이름으로 추측하면 삽화마다 갈린다).
    ★ 선언은 `changeNote` 하나로 족하다. 이미 *[발화 생략]* 를 적는
      자리이고, 빌드가 «하이라이트에 사유가 없다» 로 그 짝을 이미 강제한다.
    ★ **이번에 새로 적힌 것만** 본다 — 지난 배치의 사유가 남아 있으면 그 뒤의 모든 미세
      이동이 영원히 마크를 단다(`clear_change_notes` 가 배치마다 비우는 이유와 같다).
    ★ 사유만 바뀌고 독자에게 보이는 것이 그대로면 **여전히 변경이 아니다** — 호출부가
      `reader_facing` 차이를 먼저 확인하므로 `AUTHOR_ONLY_FIELDS` 조항은 살아 있다.
    """
    note = str((new or {}).get("changeNote") or "").strip()
    return bool(note) and note != str((old or {}).get("changeNote") or "").strip()


def _mark_changed_diagrams(current, previous, changes, levels=None):
    previous_by_id = _items_by_id(previous or [])
    current_by_id = _items_by_id(current or [])
    for diagram_id, diagram in current_by_id.items():
        old = previous_by_id.get(diagram_id)
        if old == diagram:
            continue
        level = classify_diagram_change(old, diagram)
        if level is None:
            # ★ **볼 것이 아니면 아무 데도 안 남긴다** — 표시도, 요약의 수도.
            #   한쪽에만 남기면 *요약은 25인데 화면은 4* 가 된다(2026-08-13 실사고).
            continue
        diagram["_reviewChanged"] = True
        diagram["_reviewChangeLevel"] = level
        if levels is not None:
            levels.append(level)
        changes.append("diagrams:" + diagram_id)
    if any(diagram_id not in current_by_id for diagram_id in previous_by_id):
        changes.append("diagrams:deleted")
        if levels is not None:
            levels.append("major")

_FIG_ID_RE = re.compile(r"""<g\b[^>]*\bid\s*=\s*['"]([^'"]+)['"]""")


def _changed_group_ids(old_svg, new_svg):
    """기준선 대비 **바뀐 그룹 id 목록**. 순수 함수 — 테스트가 직접 부른다.

    판정은 «그 그룹만 남긴 그림이 다른가» 하나다(`svg_with_only`). 새로 생긴 그룹도 여기서
    함께 잡힌다 — 옛 그림에는 그 자리가 아예 없으니 다르다.
    ★ 기준선이 없으면(첫 삽화) **빈 목록**이다 — 전부 새것으로 칠하면 아무것도 안 짚은 것과
      같다(그때는 삽화 딱지 하나로 충분하다).
    """
    if not old_svg.strip():
        return []
    out = []
    for gid in dict.fromkeys(_FIG_ID_RE.findall(new_svg)):
        if svg_with_only(old_svg, {gid}) != svg_with_only(new_svg, {gid}):
            out.append(gid)
    return out


def _mark_changed_figure(item, old_item, changes, levels):
    r"""카드의 **슬라이드 삽화**(`figure`)도 `diagrams` 와 같은 표시를 받는다 (신설 2026-08-19).

    ★★ **열린 날 2026-08-19.** 사용자: *[발화 생략]* — 맞는 말이고, 이 자료에는 **그 장치가 이미 있다**(변경점 표시).
    빠져 있던 것은 **슬라이드 삽화만** 그 장치 밖에 있었다는 것이다:
    `REVIEW_FIELDS["derivation"]` 에도 없고 `_mark_changed_diagrams` 는 `diagrams` 만 본다.
    → SVG 만 고치면 **아무 표시도 안 뜨고 요약에도 안 세어졌다**(조용한 변경).

    ★ 판정은 `classify_diagram_change` 하나를 그대로 쓴다 — 삽화가 바뀌었는지 재는 자가 둘이면
      같은 그림이 자리에 따라 다르게 표시된다(이 파일이 여러 번 겪은 부류).
    """
    fig = item.get("figure")
    if not isinstance(fig, dict):
        return
    old = (old_item or {}).get("figure")
    if old == fig:
        return
    level = classify_diagram_change(old if isinstance(old, dict) else None, fig)
    if level is None:
        return                            # 볼 것이 아니면 아무 데도 안 남긴다(위 주석의 규율)
    fig["_reviewChanged"] = True
    fig["_reviewChangeLevel"] = level
    # ★★ **어느 조각이 바뀌었는지까지 준다** (2026-08-19, 사용자 3회차: *[발화 생략]*).
    #   딱지는 «이 삽화가 바뀌었다» 까지만 말한다 — 그림은 픽셀이라 **어디가** 바뀌었는지는
    #   그림 안에서 짚어야 하고, 그러려면 그룹 단위 대조가 필요하다.
    #   ★ 대조는 `svg_with_only` 를 그대로 쓴다 — «그 그룹만 남긴 그림» 이 다르면 그 그룹이
    #     바뀐 것이다. 자를 새로 만들면 그리는 쪽(뷰어의 `show`)과 재는 쪽이 갈린다.
    fig["_reviewChangedGroups"] = _changed_group_ids(
        str((old or {}).get("svg") or ""), str(fig.get("svg") or ""))
    changes.append("figure")
    levels.append(level)


def _compare_review_items(current, previous, fields, summary):
    previous_by_id = _items_by_id(previous or [])
    current_by_id = _items_by_id(current or [])
    for item_id, item in current_by_id.items():
        old_item = previous_by_id.get(item_id)
        if old_item is None:
            item["_changed"] = ["new"]
            item["_changeLevel"] = "major"
            for diagram in item.get("diagrams") or []:
                diagram["_reviewChanged"] = True
                diagram["_reviewChangeLevel"] = "major"
            for diagram in item.get("solutionDiagrams") or []:
                diagram["_reviewChanged"] = True
                diagram["_reviewChangeLevel"] = "major"
            if isinstance(item.get("figure"), dict):
                item["figure"]["_reviewChanged"] = True      # 카드가 새것이면 그 삽화도 새것이다
                item["figure"]["_reviewChangeLevel"] = "major"
            summary["added"] += 1
            continue

        changes = [field for field in fields if item.get(field) != old_item.get(field)]
        levels = [_classify_change(old_item.get(field), item.get(field)) for field in changes]
        _mark_changed_diagrams(item.get("diagrams"), old_item.get("diagrams"), changes, levels)
        _mark_changed_diagrams(item.get("solutionDiagrams"), old_item.get("solutionDiagrams"),
                               changes, levels)
        _mark_changed_figure(item, old_item, changes, levels)   # 슬라이드 삽화(카드에 한 벌)
        # 배열 필드는 **바뀐 원소만** 표시하고 부모의 필드 표시는 뗀다(위 GRANULAR_FIELDS 주석).
        granular = [field for field in changes if field in GRANULAR_FIELDS
                    and _mark_changed_elements(item.get(field), old_item.get(field))]
        # 긴 글은 **바뀐 단락만** 표시하고 부모의 필드 표시는 뗀다(위 PARAGRAPH_FIELDS 주석).
        # 바뀐 단락이 0개로 나오면(순서만 바뀐 경우 등) 좁히지 않는다 — 표시가 사라지느니 넓은 편이 낫다.
        paras = {}
        for field in changes:
            if field not in PARAGRAPH_FIELDS:
                continue
            hits = changed_paragraph_indexes(item.get(field), old_item.get(field))
            if hits:
                paras[field] = hits
                granular.append(field)
        if paras:
            item["_changedParas"] = paras
        if granular:
            item["_granular"] = granular
        if changes:
            item["_changed"] = changes
            item["_changeLevel"] = _worst(levels) or "minor"
            summary["modified"] += 1
            summary.setdefault("levels", {})
            summary["levels"][item["_changeLevel"]] = summary["levels"].get(item["_changeLevel"], 0) + 1
            # ★★ **하이라이트에 사유가 없으면 알린다** (열린 날 2026-08-12 — 사용자 **4회째** 지적:
            #   *[발화 생략]* · *[발화 생략]*).
            #   ★ 기능은 있었다 — 뷰어가 `changeNote` 를 툴팁으로 띄운다(2026-07-28 에 만들었다).
            #     **비어 있는 것은 데이터**였고, 그것을 아무도 신고하지 않았다. 사람의 성실성에
            #     걸려 있었으므로 네 번 반복됐다.
            #   트리거를 **빌드**에 건다(AGENTS 「방지장치의 트리거는 반드시 하는 일에」) —
            #   하이라이트를 만드는 바로 그 자리라, 표시가 생기면 사유의 유무가 같이 판정된다.
            if not str(item.get("changeNote") or "").strip():
                summary.setdefault("noNote", []).append(str(item.get("id") or "?"))
        elif str(item.get("changeNote") or "").strip():
            # ★★ **반대쪽도 신고한다 — 사유는 있는데 바뀐 것이 없는 자리** (신설 2026-08-13).
            #   사용자 지적: *[발화 생략]* —
            #   툴팁이 «분수를 인라인 수식으로 조판했다» 고 하는데 그 삽화에는 분수가 없었다.
            #   ★ 원인은 **배치 사유를 여러 카드에 복사해 붙인 것**이다. 사유 글의 내용이
            #     그 카드의 것인지는 기계가 판정할 수 없지만, **안 바뀐 카드에 사유가 붙은 것**은
            #     기계가 안다 — 복사해 붙일 때 가장 먼저 드러나는 자국이 그것이다.
            #   ★ 「사유 없음」과 **한 자리에서** 판정한다. 두 곳에 적으면 갈라진다.
            summary.setdefault("staleNote", []).append(str(item.get("id") or "?"))
    stale = summary.get("staleNote") or []
    if stale:
        import sys as _sys
        if "--quiet" in _sys.argv:
            print("  [사유만 있음] %d건" % len(stale))
        else:
            print("  [사유만 있음] 바뀐 것이 없는데 changeNote 가 붙어 있다 — %s%s"
                  % (", ".join(stale[:6]), " …" if len(stale) > 6 else ""))
            print("       끝난 배치의 사유이거나 **다른 카드의 사유를 복사한 것**이다."
                  " `python tools/clear_change_notes.py` 로 걷거나 그 자리의 사유로 고칠 것.")
        summary["staleNoteSeen"] = (summary.get("staleNoteSeen") or []) + stale
        summary["staleNote"] = []
    missing = summary.get("noNote") or []
    if missing:
        # ★ `--quiet` 에서는 **개수만** 낸다 (2026-08-12, 사용자: *[발화 생략]*). 이 경고를 넣은 그 회차에 출력이 15줄 늘어
        #   작업에 쓸 자리를 도로 잡아먹었다 — 신설한 검사가 스스로 비용이 된 자리다.
        import sys as _sys
        if "--quiet" in _sys.argv:
            print("  [사유 없음] %d건" % len(missing))
        else:
            print("  [사유 없음] 하이라이트 %d건에 changeNote 가 없다 — %s%s"
                  % (len(missing), ", ".join(missing[:6]),
                     " …" if len(missing) > 6 else ""))
        # 컬렉션마다 한 번씩만 알리되 **누적본은 남긴다** — 회귀가 그 자리를 확인한다.
        summary["noNoteSeen"] = (summary.get("noNoteSeen") or []) + missing
        summary["noNote"] = []
    summary["deleted"] += sum(1 for item_id in previous_by_id if item_id not in current_by_id)

def _limit_theory_review(chapter, scope):
    """Keep visual review markers inside the requested contiguous theory range."""
    if not scope:
        return
    start, end = scope.get("sectionStart"), scope.get("sectionEnd")
    if not start or not end:
        return
    active = False
    for section in chapter.get("theory", {}).get("sections") or []:
        if section.get("id") == start:
            active = True
        if not active:
            section.pop("_changed", None)
            for diagram in section.get("diagrams") or []:
                diagram.pop("_reviewChanged", None)
        if section.get("id") == end:
            active = False

def review_note_gate(review_ch, ch_path):
    """변경점 하이라이트에 사유가 빠졌으면 차단 사유, 아니면 None. 순수 함수(파일은 과목 index 만 읽는다).

    재는 것: `add_review_changes` 가 남긴 `summary.noNoteSeen`(사유 없는 하이라이트 id).
    문턱: **전 과목·전 장 기본 error** — 안 켤 과목은 `index.json` 의 `strictWaivers.review_note` 에
      사유와 함께 적는다(`is_strict_chapter` 의 기본값 규칙).
    왜(2026-09-14 기계공작법 ch10 여섯째 지적 3): 다섯째 배치가 사유를 한 건도 안 달아 「올리면 무엇이 바뀌었는지」가
      안 떴다 — 빌드는 `[사유 없음]` 경고만 냈다.
    ★ 선언식(`strictChapters.review_note`)은 **2026-09-20 에 기본 error 로 승격했다** — 선언한 장 밖에서
      사유 없는 수정이 그대로 커밋됐다(2026-09-19 여섯 건 `b2efbcc6` · 이 승격 직전에도 다섯 건이 남아 있었다).
      옛 판정 *[발화 생략]* 를 사용자가 뒤집었다
      (2026-09-19 *[발화 생략]*). 승격 시점의 실측 잔량은 0 이라 다른 과목 빌드를 멈추지 않는다.
    못 보는 것: 사유 **내용**이 그 카드의 것인지(복사해 붙인 사유는 `staleNote` 가 반쪽만 잡는다).
    """
    from .checks_content import is_strict_chapter
    missing = (((review_ch or {}).get("_reviewChanges") or {}).get("summary") or {}).get("noNoteSeen") or []
    if not missing or not is_strict_chapter(ch_path, (), "review_note"):
        return None
    return ("변경점 하이라이트 %d건에 사유(changeNote)가 없다 — %s — `python tools/set_change_notes.py --chapter=%s --from=<사유.json> --apply`"
            % (len(missing), ", ".join(missing[:6]), os.path.basename(ch_path)))


def add_review_changes(ch, ch_path, enabled):
    r"""검수 표시를 붙인 사본. **숨긴 탭에는 아무 표시도 만들지 않는다.**

    ★★ 왜 아예 안 만드나 (열린 날 2026-08-07, **4회차 재발**).

    사용자: *[발화 생략]*

    뷰어는 이미 `hiddenPages` 를 목록에서 **언제나** 뺀다(토글과 무관). 그런데 데이터 쪽은
    표시를 **계속 만들고 있었고**, 그래서 같은 판정이 두 곳으로 갈렸다 — AGENTS 가
    *[발화 생략]* 고 진단해 둔 바로 그 축이다.
    실제로 2026-08-07 에 보고 축을 한 번 고쳤는데, 같은 날 **컬렉션별 내역 출력**을 새로
    만들면서 `(숨긴 탭)` 이라는 꼬리표를 달아 **또 새어 나왔다.** 라벨을 붙이는 것으로는
    안 된다 — 세지 않아야 할 것은 **세지 않아야** 한다.

    **한 번도 검수하지 않은 컬렉션에 변경점을 쌓는 것은 그 자체로 잘못이다.** AGENTS:
    *[발화 생략]* 나중에 그 탭을 열면 어차피 전부를 읽는다.

    판정 키는 **`hiddenTabs` 하나**다(뷰어와 같은 것). 문풀까지 검수를 마친 과목·챕터는
    그 선언이 없으므로 **아무 영향도 받지 않는다** — 컬렉션 이름으로 자르면 그쪽이 깨진다.
    """
    if not enabled:
        return ch
    previous = _review_baseline(ch_path)
    if previous is None:
        return ch

    hidden = set(ch.get("hiddenTabs") or [])
    review_ch = json.loads(json.dumps(ch, ensure_ascii=False))
    summary = {"added": 0, "modified": 0, "deleted": 0}
    fields = REVIEW_FIELDS
    for name in REVIEW_COLLECTIONS:
        if name in hidden:
            # ★ 건너뛴다 — **빈 목록을 넘기면 안 된다.** `_compare_review_items` 는 기준선에만
            #   있는 항목을 `deleted` 로 세므로, 빈 목록을 주면 그 컬렉션 전체가 '삭제됨'으로
            #   요약에 들어간다. 세지 않기로 한 것이 다른 칸에서 되살아나는 셈이다.
            continue
        _compare_review_items(_collection_items(review_ch, name),
                              _collection_items(previous, name), fields[name], summary)
    _limit_theory_review(review_ch, review_ch.get("reviewScope"))
    # The badge count must describe markers that remain after scope limiting.
    summary["modified"] = sum(1 for name in REVIEW_COLLECTIONS
                              for item in _collection_items(review_ch, name)
                              if item.get("_changed"))
    review_ch["_reviewChanges"] = {"summary": summary}
    return review_ch
