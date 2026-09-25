# -*- coding: utf-8 -*-
"""Template injection, output writing, and viewer-template checks."""
import hashlib
import html as _htmlmod
import json
import os
import re
import subprocess
from urllib.parse import quote

from .checks_content import lint_chapter, resolve_review_prerequisites
from .review import add_review_changes, review_note_gate, viewer_changes_for
from .textutil import BAD_CHARS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def review_set_from_map(ch_path):
    """대응표(`chNN.objective-map.json`)가 `reviewSet` 이름을 선언하면 목표별 문항 번호를 묶어 낸다.
    분모가 문제 묶음일 때만 뜻이 있다 — 교재 학습목표 목록이 분모인 대응표는 선언하지 않는다.
    번호는 ref 의 앞 글자(R)를 뗀 것. 못 보는 것: 번호가 교재 번호와 실제로 맞는가(대응표를 쓸 때 사람이 본다).
    """
    from .checks_content import objective_map_path
    mp = objective_map_path(ch_path)
    if not os.path.exists(mp):
        return None
    with open(mp, encoding="utf-8") as f:
        m = json.load(f)
    label = m.get("reviewSet")
    if not label:
        return None
    items = m.get("items") or []
    by_lo, excluded = {}, []
    for it in items:
        num = re.sub(r"^[A-Za-z]+", "", it.get("ref", ""))
        if it.get("excluded"):
            excluded.append({"num": num, "why": it["excluded"]})
            continue
        for lo in it.get("objectives") or []:
            by_lo.setdefault(lo, []).append(num)
    return {"label": label, "total": len(items), "byObjective": by_lo, "excluded": excluded}


def _shared_site_root():
    """main 워크트리의 경로를 찾는다 — **템플릿은 여기서 산다** (2026-09-02, 사용자 요청:
    *[발화 생략]*). `site/template/**`는 과목마다 사실이 다르지 않은 순수 공통이라, main 에서
    고치면 **머지 없이** 모든 과목이 다음 빌드부터 그 내용을 그대로 쓴다.
    `tools/**` 는 여기 대상이 아니다 — 그건 실행되는 코드 자체라 각 워크트리가 실제로
    갖고 있어야 돈다(그래서 스크립트 로직을 고칠 때는 여전히 머지가 필요하다).
    main 브랜치를 못 찾으면(단독 클론·git 실패 등) 자기 워크트리의 사본으로 되돌아간다 —
    그때는 지금까지처럼 이 워크트리에 커밋된 사본이 쓰인다. 이 조회는 모듈을 import 할 때
    **한 번만** 돈다(빌드마다 다시 묻지 않는다).
    """
    try:
        out = subprocess.run(["git", "-C", ROOT, "worktree", "list", "--porcelain"],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=5).stdout
    except Exception:
        return ROOT
    cur_path = None
    for ln in out.splitlines():
        if ln.startswith("worktree "):
            cur_path = ln[len("worktree "):].strip()
        elif ln.startswith("branch ") and cur_path:
            ref = ln[len("branch "):].strip()
            branch = ref[len("refs/heads/"):] if ref.startswith("refs/heads/") else ref
            if branch == "main" and os.path.isdir(cur_path):
                return cur_path
    return ROOT


def _template_root():
    """템플릿 정본 경로. 격리 검증은 main 폴백 대신 명시한 사본을 쓴다.

    평소에는 main의 공통 템플릿을 계속 공유한다. 다만 공통 템플릿을 고치는 브랜치에서
    그 사본을 검증할 때는 ``JEONGRI_TEMPLATE_ROOT``를 준다. 이 스위치가 없으면
    수정 전 main을 읽어 테스트가 초록이어도 산출물에는 수정이 없는 거짓 통과가 된다.
    """
    forced = os.environ.get("JEONGRI_TEMPLATE_ROOT")
    if not forced:
        return _shared_site_root()
    root = os.path.abspath(forced)
    required = os.path.join(root, "site", "template")
    if not os.path.isdir(required):
        raise ValueError("JEONGRI_TEMPLATE_ROOT에 site/template가 없다: " + root)
    return root


SHARED_ROOT = _template_root()


def _shared_or_local(*parts):
    shared = os.path.join(SHARED_ROOT, *parts)
    return shared if os.path.isfile(shared) else os.path.join(ROOT, *parts)


TEMPLATE = _shared_or_local("site", "template", "viewer.template.html")
TABLES_TEMPLATE = _shared_or_local("site", "template", "tables.template.html")
# 과목 사이 한 벌인 표(물질 무관 격자). `_` 로 시작하는 폴더는 chNN.json 이 없어 과목으로 안 잡힌다
#   (`audit_content.subject_dirs`).
COMMON_TABLES = os.path.join(ROOT, "data", "_공통표")
COMMON_COMPRESSIBILITY = os.path.join(COMMON_TABLES, "compressibility.json")
# ★★ **두 화면이 함께 쓰는 조각** (신설 2026-08-18). 스포트라이트 튜토리얼은 챕터 뷰어와
#   별책 표 뷰어 **둘 다**에서 돈다 — 두 템플릿에 같은 코드를 두면 그 순간 두 벌이 되고
#   한쪽만 고쳐진다(이 리포가 «재사용 = 복제 = 갈라짐» 으로 여러 번 닫은 자리).
#   → 정본은 `site/template/<이름>.part.html` 하나이고, 각 템플릿은 `<!--@part 이름-->` 로
#     **자리만** 선언한다. 뷰어 쪽은 그 뒤 자산 분리를 그대로 타므로 페이지는 안 커진다.
PART_DIR = os.path.join(ROOT, "site", "template")
_PART_RE = re.compile(r"<!--@part\s+([a-z0-9_-]+)\s*-->")


def include_parts(html):
    """`<!--@part 이름-->` 를 `site/template/이름.part.html` 로 바꾼다. 순수에 가깝게.

    ★ **없는 조각은 조용히 지나가지 않는다** — 자리만 남고 코드가 안 실리면 그 화면에서
      기능이 통째로 사라지는데 빌드는 통과한다(규칙 11 의 그 침묵). 그래서 예외를 던진다.
    """
    def sub(m):
        path = os.path.join(PART_DIR, m.group(1) + ".part.html")
        if not os.path.isfile(path):
            raise ValueError(path + ": 없는 조각을 `<!--@part " + m.group(1) + "-->` 가 가리킨다")
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    return _PART_RE.sub(sub, html)


NOTE_KEY_RE = re.compile(r"^지적\([^)]*\)")

# ── 발행 페이지에서 개발 주석을 걷어낸다 ──────────────────────────────────────
#
# 열린 날 2026-08-14 (고체역학 세션이 「공개-전-점검」을 도입하다 발견 · 사용자 지시로 여기서 고침).
#
# **무엇이 새어나갔나.** 빌드는 `viewer.template.html` 을 **통째로 인라인**한다. 그 템플릿은
# 이 리포의 다른 모든 파일과 같은 규율로 쓰여 있어서 — *왜 이 규칙이 열렸나* 를 실사고와 함께
# 적는다 — **사용자 발언이 1인칭 그대로** 들어 있다. 그 전부가 발행 페이지에 실린다.
# 실측(2026-08-14, `site/동역학/ch19.html`): 주석 줄 **1,161개** · 「사용자 지적/실사고/열린 날」
# 이 들어간 줄 **133개**. 공개-전-점검 §1 의 ⑴자기 과실 기록 ⑶활동 로그가 그대로 나가는 자리다.
#
# ★ **왜 템플릿에서 주석을 빼는 쪽으로 안 고치나.** 그 주석이 이 리포에서 가장 값나가는 기록이다
#   (AGENTS 「이 문서는 쪼개지 않는다」와 같은 근거 — 규칙이 왜 열렸는지가 없으면 다음 세션이
#   규칙을 무시한다). 없앨 것은 *기록*이 아니라 *발행본에 실리는 것*이라, **빌드가 걷어낸다.**
#
# ★ **줄 단위로만 걷는다** — 문자열 안의 `//`·`/*` 를 건드리지 않기 위해서다. 뒤에 붙은 주석
#   (`x = 1;  // 왜`)은 남는다. 그건 새는 양이 아니라 **안전**을 산 값이다:
#   실측으로 이 템플릿에는 **여러 줄에 걸친 문자열이 없고**(백틱이 홀수인 줄 0개) 빌드가 `${`
#   를 이미 금지하므로, 줄 첫머리의 주석 표식은 문자열 안일 수 없다.
#
# 잠금 `test_checks.py::test_published_page_has_no_dev_comments`.

_LINE_COMMENT = re.compile(r"^\s*//")
_BLOCK_OPEN = re.compile(r"^\s*/\*")
_HTML_OPEN = re.compile(r"^\s*<!--")


def strip_dev_comments(template):
    """템플릿의 **한 줄을 통째로 차지하는 주석**을 걷어낸다. 순수 함수 — 테스트가 직접 부른다.

    걷는 것: `//` 로 시작하는 줄 · 줄 첫머리에서 열린 `/* … */` 블록 · 같은 형태의 `<!-- … -->`.
    남기는 것: 코드 뒤에 붙은 주석 · 조건부 주석(`<!--[if`) · 한 줄 안에서 열고 닫히는 것 중
    **코드가 함께 있는 줄**.
    """
    out, mode = [], None
    for line in template.split("\n"):
        if mode == "block":
            if "*/" in line:
                mode = None
            continue
        if mode == "html":
            if "-->" in line:
                mode = None
            continue
        if _HTML_OPEN.match(line) and not line.lstrip().startswith("<!--["):
            if "-->" not in line:
                mode = "html"
            continue
        if _BLOCK_OPEN.match(line):
            if "*/" not in line:
                mode = "block"
            continue
        if _LINE_COMMENT.match(line):
            continue
        out.append(line)
    # 주석만 있던 자리에 남은 빈 줄이 세 줄 넘게 이어지면 하나로 줄인다(발행본 부피).
    return re.sub(r"\n{4,}", "\n\n", "\n".join(out))


# ── 뷰어를 페이지에서 떼어 전 과목이 공유한다 ────────────────────────────────
#
# 열린 날 2026-08-15. **실측이 근거다** — 페이지 335KB = 데이터 192KB + **뷰어 143KB**.
# 뷰어는 장마다 글자 하나 다르지 않은데 장마다 다시 실렸다: 54장에 중복만 7.5MB,
# 30과목 300장이면 **~42MB**. 나중에 할수록 비싸다(300장 재빌드 + 검수 동선).
#
# ★ **판정선은 자리표 하나다.** `{{…}}` 가 든 `<style>`·`<script>` 는 페이지에 남고,
#   없는 블록은 자산으로 뽑힌다. 경계 표식(`/* SPLIT */` 류)을 두지 않은 이유는 —
#   **표식과 실제 자리는 갈라지기 때문이다.** 자리표가 있는 블록은 «장마다 값이 다른 것»
#   이라는 뜻이고, 그것이 곧 «페이지에 남아야 하는 것»의 정의다. 정의로 판정하면 갈라질 자리가 없다.
#
# ★★ **파일 이름이 내용 해시다** — `viewer.<sha10>.js`. 이유가 둘이다:
#   ⑴ 캐시. 뷰어를 고치면 이름이 바뀌므로 브라우저가 낡은 것을 쥐고 있을 수 없다.
#   ⑵ **낡은 갈래가 안 깨진다.** 과목 12개가 각자 `git merge main` 하는 구조라, 어떤 과목은
#      옛 뷰어로 빌드된 채 배포에 섞인다. 이름이 하나(`viewer.js`)면 마지막에 복사한 것이
#      남의 페이지까지 갈아치워 **markup 은 옛것인데 JS 는 새것**인 화면이 된다 — 조용히
#      틀린 화면이 이 리포에서 가장 비싼 실패다. 해시 이름은 둘이 그냥 공존한다.
#
# ★ `deploy_all` 이 워크트리마다 `site/_assets/` 를 번들로 **합친다**(덮지 않는다).
#   같은 이름이면 내용이 같다는 것이 해시의 뜻이므로 충돌이 성립하지 않는다.
#
# 잠금 `test_checks.py::test_viewer_is_split_into_shared_assets`.

def out_root():
    """산출물을 쓸 뿌리. **입력은 언제나 `ROOT`** 이고 이것은 «어디에 쓰나»만 가른다.

    ★★ 왜 열렸나 (2026-08-15). `deploy_all` 은 번들을 만들려고 워크트리마다
      `build_site --all` 을 **검수 표시 꺼짐**으로 돌리는데, 그 빌드가 **그 워크트리의
      `site/` 를 그대로 덮어썼다.** 즉 **배포 한 번이 다른 과목 세션의 화면에서 변경점 표시를
      지운다** — 그 세션은 자기가 안 건드린 화면이 바뀐 줄 모른다. AGENTS 「기준선」 절이
      *[발화 생략]* 며 막아 온 바로 그 부류를, 배포 도구가 뒷문으로 하고 있었다.
    ★ 그래서 이 세션은 번들 확인을 **일부러 안 돌리고** 회귀로 대신했다(2026-08-15) —
      «확인하려고 돌렸더니 남의 화면이 바뀌는» 자를 쓸 수는 없다.
    → 번들 빌드는 `BUILD_OUT_ROOT` 로 **딴 데다 쓴다.** 안 주면 지금까지와 똑같다.
    """
    return os.environ.get("BUILD_OUT_ROOT") or ROOT


ASSETS_DIRNAME = "_assets"
ASSETS_HREF = "../" + ASSETS_DIRNAME + "/"

_TAG_RE = re.compile(r"(?s)<(style|script)\b([^>]*)>(.*?)</\1\s*>")
_ASSET_RE = re.compile(r"^viewer\.[0-9a-f]{10}\.(css|js)$")
_VIEWER_CACHE = {}


def split_viewer_assets(html):
    """자리표가 없는 `<style>`·`<script>` 를 뽑아 `(껍데기, {파일명: 본문})` 로 돌려준다.

    순수 함수 — 파일을 쓰지 않는다(테스트가 직접 부른다).
    """
    assets, out, pos = {}, [], 0
    for m in _TAG_RE.finditer(html):
        tag, attrs, body = m.group(1), m.group(2), m.group(3)
        if "{{" in body or "src=" in attrs or "href=" in attrs:
            continue
        kind = "css" if tag == "style" else "js"
        name = "viewer." + hashlib.sha256(body.encode("utf-8")).hexdigest()[:10] + "." + kind
        assets[name] = body
        ref = ('<link rel="stylesheet" href="' + ASSETS_HREF + name + '">') if kind == "css" \
            else ('<script src="' + ASSETS_HREF + name + '"></script>')
        out.append(html[pos:m.start()])
        out.append(ref)
        pos = m.end()
    out.append(html[pos:])
    return "".join(out), assets


def viewer_rev(template):
    """뷰어 **판본** — 템플릿 sha256 의 앞 12자. 순수 함수 — 테스트가 직접 부른다.

    ★ 왜 자산 파일 이름이 아니라 템플릿인가: 자산은 CSS·JS 여럿으로 갈리고 자리표가 든
      블록은 자산이 아니라 페이지에 남는다. **화면을 만드는 것은 템플릿 하나**라 그것이 판본이다.
      쓰는 자리는 `review.viewer_changes_for` — «수락한 뒤 화면이 바뀌었나» 를 이 값으로 판정한다.
    """
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]


def prepare_viewer(template):
    """뷰어 템플릿 → `(껍데기, {파일명: 본문})`. 자산 파일을 `site/_assets/` 에 쓴다.

    한 프로세스에서 한 번만 쓴다. 이전 해시 자산은 유지한다. 빌드 도중 아직 갱신되지
    않은 HTML과 열려 있는 독자 탭이 참조할 수 있으므로 여기서 지우면 CSS/JS가 404가 된다.
    """
    key = hashlib.sha256(template.encode("utf-8")).hexdigest()
    hit = _VIEWER_CACHE.get(key)
    if hit:
        return hit

    shell, assets = split_viewer_assets(strip_dev_comments(include_parts(template)))
    # ★ 내장 검사의 **범위가 줄지 않게** 자산 본문에도 같은 자를 댄다. 예전에는 이 셋이
    #   «통째로 인라인된 HTML» 하나만 봤다 — 뽑아낸 뒤 여기 안 대면 뷰어 코드는 아무도
    #   안 보게 된다(규칙 11: 범위를 확인 안 한 0건은 «없다»가 아니다).
    for name, body in assets.items():
        if "${" in body:
            raise ValueError(TEMPLATE + ": '${' found in " + name)
        for c in BAD_CHARS:
            if c in body:
                raise ValueError(TEMPLATE + ": control char " + hex(ord(c)) + " in " + name)
    if not assets:
        raise ValueError(TEMPLATE + ": 뽑아낼 공용 자산이 없다 — 자리표가 든 블록만 남았나?")

    asset_dir = os.path.join(out_root(), "site", ASSETS_DIRNAME)
    os.makedirs(asset_dir, exist_ok=True)
    for name, body in assets.items():
        path = os.path.join(asset_dir, name)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)

    _VIEWER_CACHE[key] = (shell, assets)
    return shell, assets


def note_keys(node):
    """이 챕터 데이터에 든 `changeNote` 의 **부류 머리**(`지적(…)`)를 흘린다.

    ★ 왜 머리만 보나: 카드마다 «조치» 문장이 달라서 사유 글 전체를 키로 쓰면 같은 부류가
      갈린다 — 뷰어의 `reviewNoteKey` 가 이미 그렇게 판정하고, **여기도 같은 규칙을 쓴다**
      (두 곳이 다른 키를 쓰면 전역 카운트가 화면과 어긋난다).
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "changeNote" and isinstance(value, str):
                m = NOTE_KEY_RE.match(value.strip())
                if m:
                    yield m.group(0)
            else:
                for hit in note_keys(value):
                    yield hit
    elif isinstance(node, list):
        for value in node:
            for hit in note_keys(value):
                yield hit


# ── 저자 전용 필드는 발행 JSON 에 싣지 않는다 (2026-08-14) ────────────────────
#
# 열린 날 2026-08-14. 다른 세션이 「발행 HTML 에 개발 주석 표식이 없다」 검사를 넣자
# `ch00.html` 이 걸렸는데, 그 문자열이 있던 자리는 **`rationale`** — 저자가 *왜 이렇게 만들었나*
# 를 적어 두는, **화면이 한 번도 안 읽는 필드**였다. 빌드가 챕터 JSON 을 통째로 주입하니
# 저자 메모가 그대로 발행물에 실려 나가고 있었다.
#
# ★ **낱말을 고치는 것은 인스턴스 처방이다**(그날 실제로 한 낱말을 바꿔 게이트를 통과시켰다).
#   부류는 «화면이 안 읽는 필드가 발행물에 실린다» 이고, 그러면 저자가 사유를 성실히 적을수록
#   더 많이 새어 나간다 — 기록을 권하는 이 리포에서는 **정확히 거꾸로 가는 구조**다.
# ★ 목록에 아무거나 넣으면 화면이 죽으므로, 회귀가 **«뷰어가 이 키를 정말 안 읽는가»** 를 함께
#   본다(`test_author_only_fields_never_ship`). `changeNote`·`reviewNote` 는 변경점 사유를
#   화면에 띄우는 데 쓰이므로 **여기 넣으면 안 된다.**
# ★ 2026-09-09 재발 — `noTheoryDiagramReason`(2026-09-09 신설)이 같은 길로 새어 나갔다.
#   *[발화 생략]* 를 적는 판정 필드라 사용자 발화 인용이 그대로 들어 있고,
#   뷰어는 이 키를 한 번도 안 읽는다(템플릿 조회 0건). 문항 층의 `noDiagramReason` 도 같다.
#   **부류가 같으므로 낱말이 아니라 목록을 고친다** — 새 판정 필드를 만들 때 여기에 올린다.
# ★ 2026-09-10 — `lintWaivers` 도 같은 부류다. 「이 경고를 왜 닫았나」를 적는 **판정 필드**이고
#   뷰어는 이 키를 한 번도 안 읽는다(템플릿 조회 0건). 사유에 사용자 발화가 들어가는 것도 같다.
#   검사·감사는 발행본이 아니라 **원본**을 읽으므로 여기 올려도 면제는 그대로 돈다.
AUTHOR_ONLY_KEYS = ("rationale", "noTheoryDiagramReason", "noDiagramReason", "lintWaivers")


def strip_author_only(node):
    """저자 전용 키를 재귀로 걷어낸 **사본**을 돌려준다. 원본은 안 건드린다(감사·검사가 읽는다)."""
    if isinstance(node, dict):
        return {k: strip_author_only(v) for k, v in node.items() if k not in AUTHOR_ONLY_KEYS}
    if isinstance(node, list):
        return [strip_author_only(v) for v in node]
    return node


def build_chapter(template, subject, cfg, ch_path, chapter_nav, review_enabled, course_tree,
                  note_seen=None, local_ports=None):
    ch = json.load(open(ch_path, encoding="utf-8"))
    ch = resolve_review_prerequisites(ch, ch_path)
    lint_chapter(ch, ch_path)
    num = ch["chapterNumber"]
    title = ch["chapterTitle"]
    ch = add_review_changes(ch, ch_path, review_enabled)
    note_block = review_note_gate(ch, ch_path)
    if note_block:
        raise ValueError(ch_path + ": " + note_block)
    review_set = review_set_from_map(ch_path)
    if review_set:
        ch = dict(ch, reviewSet=review_set)
    ch_json = json.dumps(strip_author_only(ch), ensure_ascii=False)
    if "</script" in ch_json.lower():
        raise ValueError(ch_path + ": data contains '</script' — cannot inject safely")

    html, _assets = prepare_viewer(template)
    html = html.replace("{{PAGE_TITLE}}", subject + " " + str(num) + "장 · " + title)
    html = html.replace("{{SUBJECT}}", subject)
    html = html.replace("{{CH_NUM2}}", str(num).zfill(2))
    html = html.replace("{{CH_TITLE}}", title)
    html = html.replace("{{COVER_SUB}}", cfg.get("coverSub", ""))
    # ★ 과목 전용 UI 는 과목 플래그로만 붙인다 (2026-07-28).
    # 공통 템플릿에 `수증기 표` 링크가 **조건 없이** 박혀 있어 공학수학 화면에도 떴다
    # (사용자 지적: [발화 생략]).
    # SUBJECT_CONFIG 에 steamTables 플래그가 **이미 있었는데** tables.html 을 만들지 말지에만
    # 쓰였고 링크는 그 밖에 있었다 — 플래그가 없어서가 아니라 **한 곳에만 적용**해서 난 결함이다.
    # 템플릿에 과목 이름을 하드코딩하지 않는다: 공통 파일은 과목을 몰라야 한다
    # (serve_site.vbs 가 포트를 폴더 이름으로 정하는 것과 같은 원칙).
    # 2026-09-24 E18: 그 플래그(`steamTables`)는 `appendices` 선언으로 일반화됐다 — 링크와
    # 페이지 생성이 여전히 **한 선언**을 본다(`appendix_links` · `build_appendix_page`).
    html = html.replace("{{STEAM_LINK}}", appendix_links(subject, cfg))
    # 실험 페이지 단추 — `index.json` 의 그 장 항목 `labs: [{href, title}]` 가 정본이다
    # (2026-09-12, 사용자 *[발화 생략]*).
    # 과목 이름은 여기 없다 — 장 항목이 선언한 것만 붙는다.
    mine_nav = next((c for c in (chapter_nav or []) if c.get("number") == num), {})
    lab_links = "".join(
        '<a class="steam-table-link lab-link" href="' + lab["href"] + '">' + lab["title"] + '</a>'
        for lab in (mine_nav.get("labs") or []))
    html = html.replace("{{LAB_LINKS}}", lab_links)
    html = html.replace("{{CHAPTER_NAV_JSON}}", json.dumps(chapter_nav, ensure_ascii=False))
    # ★★ **사이드바는 이 과목만 싣는다** (2026-08-15, 사용자 지시). 예전에는 전 과목 트리를
    #   장마다 넣고 뷰어가 «이 과목만» 설정으로 접었는데, 설정이면 **데이터는 어차피 다 실린다.**
    #   실측(ch02): 전 과목 트리 7.1KB/장 — 30과목이면 25KB × 300장 ≈ **7.5MB 중복**이다.
    #   화면 판단으로 좁히니 중복이 따라서 사라졌다(뷰어 분리와 같은 자리 · 다른 과목은 홈에서 본다).
    #   ★ 여기서 거르는 것이 정본이다 — 뷰어도 한 번 더 거르지만 그건 낡은 산출물 대비다.
    mine = [s for s in (course_tree or []) if s.get("name") == subject]
    html = html.replace("{{COURSE_TREE_JSON}}", json.dumps(mine, ensure_ascii=False))
    html = html.replace("{{SUBJECT_JSON}}", json.dumps(subject, ensure_ascii=False))
    # ★ 「과목→로컬 포트」 배선은 2026-08-15 에 사이드바(전 과목 트리)용으로는 사라졌다 — 그
    #   자리는 지금도 죽어 있다(위 COURSE_TREE 주석). **되살아난 것은 다른 소비자다** — 본문 안
    #   과목 간 딥링크(`[[과목@chNN:앵커|…]]`, 2026-08-29). 사이드바처럼 장마다 전 과목 맵을
    #   싣지 않고, 그 장에 실제로 걸린 링크가 있을 때만 fmtOne 이 이 표를 찾아본다.
    html = html.replace("{{LOCAL_PORTS_JSON}}", json.dumps(local_ports or {}, ensure_ascii=False))
    # ★★ 앞 장들에서 **이미 보여 준** 같은 부류의 건수. 전 장 공통 수정을 장마다 3개씩
    #   보여 주면 7장에서 21번이고, 그건 «한 번 이해하면 나머지는 정보 0» 인 것을 21번 보는 것이다
    #   (사용자 2026-08-13: *[발화 생략]*). 화면에는 전역 상태가 없으므로
    #   **빌드가** 세어 넣는다 — 챕터 HTML 은 서로 독립이다.
    html = html.replace("{{REVIEW_NOTE_SEEN_JSON}}",
                        json.dumps(dict(note_seen or {}), ensure_ascii=False))
    if note_seen is not None:
        for key in note_keys(ch):
            note_seen[key] = note_seen.get(key, 0) + 1
    # ★★ **뷰어가 바뀐 것도 검수 동선에 올린다** (2026-08-23, 사용자 지적 — `review.py` 의
    #   `viewer_changes_for` 주석이 정본). 절 단위 마크는 못 붙인다: 어느 절이 영향받는지
    #   데이터로 알 수 없다. 그래서 **챕터 머리의 배너 한 줄**이고, `본문변경` 카운터에는
    #   넣지 않는다 — 넣으면 그 수가 «데이터가 바뀐 건수» 라는 뜻을 잃는다.
    html = html.replace("{{VIEWER_CHANGES_JSON}}", json.dumps(
        viewer_changes_for(ch_path, viewer_rev(template)) if review_enabled else [],
        ensure_ascii=False))
    html = html.replace("{{CHAPTER_JSON}}", ch_json)

    # 내장 검사
    if "{{" in html:
        raise ValueError(ch_path + ": unfilled template marker remains")
    if "${" in html:
        raise ValueError(ch_path + ": '${' found (template-literal corruption risk)")
    for c in BAD_CHARS:
        if c in html:
            raise ValueError(ch_path + ": control char " + hex(ord(c)) + " found")
    # ★ 재주입 마커. 예전에는 `var CH = ` 와 `;\n\nfunction esc` 사이를 봤는데, 뷰어를
    #   자산으로 뽑아내면서 `function esc` 가 이 파일에서 사라졌다 — **뒤쪽 마커를 그대로
    #   두면 전 챕터가 빌드 실패로 넘어진다.** 지금 재는 것은 둘이다:
    #   ⑴ `marks_from_built_html` 이 읽는 «줄 첫머리의 `var CH = `» ⑵ 뷰어 자산 참조.
    #   ⑵ 가 없으면 화면이 통째로 죽는데(스타일·JS 가 다 그쪽에 있다) 빌드는 통과한다.
    if not re.search(r"(?m)^var CH = ", html):
        raise ValueError(ch_path + ": reinjection marker broken (줄 첫머리 'var CH = ')")
    if ASSETS_HREF not in html:
        raise ValueError(ch_path + ": 뷰어 자산 참조가 없다 — 화면이 빈 채로 나간다")

    out_dir = os.path.join(out_root(), "site", subject)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "ch" + str(num).zfill(2) + ".html")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    mirror = cfg.get("mirrors", {}).get(num)
    if mirror:
        os.makedirs(os.path.dirname(mirror), exist_ok=True)
        with open(mirror, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
    return out_path, mirror

_TABLES_LABEL_CACHE = {}


def tables_label(subject):
    """물성표 화면의 이름 — 물만 싣는 표는 「수증기 표」, 다른 물질(냉매·공기)도 싣는 표는 「상태량 표」.

    재는 것: `data/<과목>/tables/steam.json` 에 `substances` 가 있는가(데이터가 정한다 — 과목 이름을 모른다).
    왜: 사용자(2026-09-20) [발화 생략].
    """
    if subject not in _TABLES_LABEL_CACHE:
        path = os.path.join(ROOT, "data", subject, "tables", "steam.json")
        try:
            with open(path, encoding="utf-8") as fh:
                many = bool(json.load(fh).get("substances"))
        except OSError:
            many = False
        _TABLES_LABEL_CACHE[subject] = "상태량 표" if many else "수증기 표"
    return _TABLES_LABEL_CACHE[subject]


# ── 부록 — 과목이 선언한 참조표 페이지 (신설 2026-09-24, 설계도 E18) ─────────────
#
# 사용자(전전 ch01 인박스 E18): *[발화 생략]*. 판정(2026-09-24 *[발화 생략]*):
# 틀은 전 과목, 내용은 과목 선언.
#
# ★ 선언 = `SUBJECT_CONFIG[과목]["appendices"] = [{id, title, file}]`. `file` 은 `data/<과목>/`
#   기준 경로이고 페이지는 `site/<과목>/<id>.html` 에 나온다. **링크와 페이지가 같은 목록을 본다** —
#   2026-07-28 에 링크만 게이트 밖이라 공학수학 화면에 수증기 표가 떴던 부류를 구조로 막는다.
# ★ 종류는 파일이 정한다: `steam.json` 이면 기존 물성표 뷰어(`build_tables_page`, 이름은
#   `tables_label` 이 데이터로 정하므로 `title` 을 안 적는다), 그 밖은 범용 표
#   (`{sections:[{heading, note?, columns, rows}]}`, 칸은 글자 또는 `{"svg": …}`).
# 잠금 `test_checks.py::test_appendices_are_one_declaration`.

APPENDIX_TEMPLATE = _shared_or_local("site", "template", "appendix.template.html")
_APPENDIX_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


def appendices_of(cfg):
    """과목 설정의 부록 선언 목록(없으면 빈 목록). 형식이 틀리면 조용히 넘기지 않고 던진다."""
    items = list((cfg or {}).get("appendices") or [])
    seen = set()
    for it in items:
        aid = it.get("id", "")
        if not _APPENDIX_ID_RE.match(aid) or aid in seen:
            raise ValueError("appendices: id 가 비었거나 겹치거나 형식 밖이다: %r" % aid)
        seen.add(aid)
        if not it.get("file"):
            raise ValueError("appendices[%s]: file 이 없다" % aid)
        if not is_steam_appendix(it) and not it.get("title"):
            raise ValueError("appendices[%s]: 범용 표는 title 이 있어야 한다" % aid)
    return items


def is_steam_appendix(item):
    return os.path.basename(item.get("file", "")) == "steam.json"


def appendix_title(subject, item):
    return tables_label(subject) if is_steam_appendix(item) else item["title"]


def appendix_links(subject, cfg):
    """뷰어 머리의 부록 링크들. 선언 순서 그대로."""
    return "".join(
        '<a class="steam-table-link" href="' + it["id"] + '.html" target="_blank"'
        ' rel="noopener">' + _htmlmod.escape(appendix_title(subject, it), quote=False) + '</a>'
        for it in appendices_of(cfg))


def render_appendix_body(data):
    """범용 부록 JSON → 본문 HTML. 순수 함수 — 테스트가 직접 부른다.

    글자 칸은 이스케이프한다. `{"svg": …}` 칸만 그대로 싣는다(생성기 산출물 — 손으로 쓰지 않는다).
    """
    out = []
    for sec in data.get("sections") or []:
        cols = sec.get("columns") or []
        out.append('<section class="appx-section">')
        out.append("<h2>" + _htmlmod.escape(sec.get("heading", ""), quote=False) + "</h2>")
        if sec.get("note"):
            out.append('<p class="appx-note">' + _htmlmod.escape(sec["note"], quote=False) + "</p>")
        out.append('<div class="appx-wrap"><table><thead><tr>')
        out.extend("<th>" + _htmlmod.escape(c, quote=False) + "</th>" for c in cols)
        out.append("</tr></thead><tbody>")
        for row in sec.get("rows") or []:
            if len(row) != len(cols):
                raise ValueError("부록 표 %r: 칸 수 %d ≠ 머리 %d — %r"
                                 % (sec.get("heading"), len(row), len(cols), row))
            out.append("<tr>")
            for cell in row:
                if isinstance(cell, dict):
                    if not str(cell.get("svg", "")).lstrip().startswith("<svg"):
                        raise ValueError("부록 표 %r: 사전 칸은 {\"svg\": \"<svg…\"} 만 된다"
                                         % sec.get("heading"))
                    out.append('<td class="appx-sym">' + cell["svg"] + "</td>")
                else:
                    out.append("<td>" + _htmlmod.escape(str(cell), quote=False) + "</td>")
            out.append("</tr>")
        out.append("</tbody></table></div></section>")
    if not out:
        raise ValueError("부록 JSON 에 sections 가 없다")
    return "\n".join(out)


def build_appendix_page(subject, item):
    """선언 하나 → `site/<과목>/<id>.html`. 물성표는 기존 뷰어로 보낸다."""
    if is_steam_appendix(item):
        return build_tables_page(subject, page_id=item["id"])
    src = os.path.join(ROOT, "data", subject, item["file"])
    with open(src, encoding="utf-8") as fh:
        data = json.load(fh)
    body = render_appendix_body(data)
    template = open(APPENDIX_TEMPLATE, encoding="utf-8").read()
    html = (strip_dev_comments(template)
            .replace("{{SUBJECT}}", _htmlmod.escape(subject, quote=False))
            .replace("{{TITLE}}", _htmlmod.escape(item["title"], quote=False))
            .replace("{{SOURCE}}", _htmlmod.escape(data.get("source", ""), quote=False))
            .replace("{{BODY}}", body))
    if "{{" in html:
        raise ValueError(APPENDIX_TEMPLATE + ": unfilled template marker remains")
    for c in BAD_CHARS:
        if c in html:
            raise ValueError(src + ": control char " + hex(ord(c)) + " found")
    out_path = os.path.join(out_root(), "site", subject, item["id"] + ".html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out_path


def build_tables_page(subject, page_id="tables"):
    """과목별 물성표 페이지(site/<과목>/tables.html) 생성. `subject`는 `data/<과목>/` 폴더 이름.

    ★ **과목 이름을 하드코딩하지 않는다** (2026-09-03 결함 수정 — AGENTS 「공통 도구에 과목별
    사실을 박지 않는다」의 그 폴백 함정 그대로였다). 예전엔 `STEAM_TABLE_DATA`·출력 경로 둘 다
    "열역학"이 문자열로 박혀 있어, 다른 과목이 `steamTables: True`를 켜도 `data/열역학/…`를
    찾다가 FileNotFoundError로 죽었다 — 열역학이 아닌 워크트리에는 그 폴더 자체가 없다.
    호출자(`build_site.py`)가 `subjects_meta`에서 실제 과목 이름을 넘긴다.
    """
    steam_table_data = os.path.join(ROOT, "data", subject, "tables", "steam.json")
    template = open(TABLES_TEMPLATE, encoding="utf-8").read()
    steam = json.load(open(steam_table_data, encoding="utf-8"))
    steam_json = json.dumps(steam, ensure_ascii=False)
    if "</script" in steam_json.lower():
        raise ValueError(steam_table_data + ": data contains '</script' — cannot inject safely")

    # ★ 튜토리얼 선언은 **표 데이터 옆**에 산다(`tutorial.json`) — 이 화면이 어느 과목의 것인지는
    #   `steam_table_data` 하나가 이미 정하고 있으므로 그 폴더를 따라간다. 파일이 없으면 `null`
    #   이고 튜토리얼은 **아무것도 안 만든다**(선언이 곧 opt-in — 없는 것은 실패가 아니다).
    tut_path = os.path.join(os.path.dirname(steam_table_data), "tutorial.json")
    tut_json = "null"
    if os.path.isfile(tut_path):
        with open(tut_path, encoding="utf-8") as fh:
            tut_json = json.dumps(json.load(fh), ensure_ascii=False)
        if "</script" in tut_json.lower():
            raise ValueError(tut_path + ": data contains '</script' — cannot inject safely")

    # 압축성 선도 격자는 물질과 무관해 과목 사이 한 벌(`data/_공통표/`, `gen_compressibility.py`)이다 —
    #   표 페이지를 여는 과목은 전부 같은 격자를 받는다. 파일이 없으면 `null` 이고 그 탭이 안 뜬다.
    z_path = COMMON_COMPRESSIBILITY
    z_json = "null"
    if os.path.isfile(z_path):
        with open(z_path, encoding="utf-8") as fh:
            z_json = json.dumps(json.load(fh), ensure_ascii=False)

    html = (strip_dev_comments(include_parts(template))
            .replace("{{COMPRESS_JSON}}", z_json)
            .replace("{{SUBJECT}}", subject)
            .replace("{{TABLES_LABEL}}", tables_label(subject))
            .replace("{{STEAM_JSON}}", steam_json)
            .replace("{{TUTORIAL_JSON}}", tut_json))
    if "{{" in html:
        raise ValueError(TABLES_TEMPLATE + ": unfilled template marker remains")
    if "${" in html:
        raise ValueError(TABLES_TEMPLATE + ": '${' found (template-literal corruption risk)")
    for c in BAD_CHARS:
        if c in html:
            raise ValueError(TABLES_TEMPLATE + ": control char " + hex(ord(c)) + " found")
    if "var STEAM = " not in html:
        raise ValueError(TABLES_TEMPLATE + ": reinjection marker broken")

    out_path = os.path.join(out_root(), "site", subject, page_id + ".html")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out_path


LAB_DIRNAME = "lab"


def lab_pages(subject):
    """`data/<과목>/lab/*.html` — 손으로 쓴 실험 페이지의 원본 목록(정렬, 없으면 빈 목록).

    잰다: 그 폴더의 `.html` 만. 못 본다: 페이지가 참조하는 상대 경로가 실제로 있는지.
    """
    src_dir = os.path.join(ROOT, "data", subject, LAB_DIRNAME)
    if not os.path.isdir(src_dir):
        return []
    return sorted(os.path.join(src_dir, n) for n in os.listdir(src_dir) if n.endswith(".html"))


def copy_lab_pages(subject):
    """실험 페이지를 `site/<과목>/lab/` 로 복사한다. 원본은 `data/` 쪽 하나뿐이다(절대 규칙 1).

    돌려주는 것: 쓴 산출물 경로 목록. 문턱 없음 — 있는 만큼 복사한다.
    """
    pages = lab_pages(subject)
    if not pages:
        return []
    out_dir = os.path.join(out_root(), "site", subject, LAB_DIRNAME)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for src in pages:
        with open(src, encoding="utf-8") as fh:
            html = fh.read()
        out_path = os.path.join(out_dir, os.path.basename(src))
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(html)
        written.append(out_path)
    return written


HOME_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>전공 정리 · 과목 선택</title>
<style>
/* 글꼴은 챕터 화면과 **같은 한 벌**이다 — 경로만 다르다(이 파일은 site/ 바로 아래에 있다).
   왜 싣는지와 왜 이름이 다른지는 `site/fonts/README.md` 가 정본. */
@font-face{font-family:"Jeongri Sans"; font-weight:400; font-style:normal; font-display:swap;
  src:url("fonts/JeongriSans-Regular.woff2") format("woff2");}
@font-face{font-family:"Jeongri Sans"; font-weight:700; font-style:normal; font-display:swap;
  src:url("fonts/JeongriSans-Bold.woff2") format("woff2");}
@font-face{font-family:"Jeongri Serif"; font-weight:700; font-style:normal; font-display:swap;
  src:url("fonts/JeongriSerif-Bold.woff2") format("woff2");}
/* ★★★ 이 페이지의 팔레트·글꼴·크기 사다리는 **뷰어(`site/template/viewer.template.html`)의
   `:root` 가 정본이고 여기는 그 짝이다.** 값을 고칠 일이 생기면 두 곳을 함께 고친다.
   ★ 왜 이 주석이 필요한가 (2026-08-13): 챕터 화면이 「AI 냄새」 배치로 종이(회녹)·강조(청록)·
     모서리(3px)·글꼴(Pretendard/명조)·글자 사다리를 전부 바꾸는 동안, **이 페이지는 그중
     하나도 못 받고 크림 종이 + 구리 강조 + 14px 모서리로 남아 있었다.** 배치가 챕터만 돌았고
     아무도 이 화면을 열어 보지 않았기 때문이다 — 그런데 **방문자는 여기서 시작한다.**
     한쪽만 바뀌면 목록에서 챕터로 들어가는 순간 색이 갈려 «같은 자료»로 안 읽힌다.
   ★ 잠금 `test_checks.py::test_home_page_shares_the_viewer_palette` — 두 파일의 토큰을 대조한다.
     주석으로만 적으면 다음 배치가 또 한쪽만 고친다(이 결함이 정확히 그렇게 생겼다). */
:root{
  --paper:#f0f3ec; --paper-raised:#f8faf5; --ink:#2b3138; --sub:#575145;
  --blue:#2c4a66; --copper:#2f6b63; --copper-soft:#d9e8e4; --line:#ded6c2;
  /* 글자 크기 사다리 — 뷰어와 같은 네 단(+표지). 근거는 그쪽 토큰 주석이 정본. */
  --fs-micro:11.5px; --fs-small:13px; --fs-body:15.5px; --fs-head:19px; --fs-cover-title:28px;
}
@media (prefers-color-scheme: dark){
  :root{ --paper:#151814; --paper-raised:#1c201b; --ink:#d8d3c8; --sub:#a39c8a;
    --blue:#8fb3d1; --copper:#e2915a; --copper-soft:#332318; --line:#31363d; }
}
*{box-sizing:border-box;}
body{margin:0; background:var(--paper); color:var(--ink);
  font-family:"Jeongri Sans","Pretendard","Apple SD Gothic Neo","Malgun Gothic","Noto Sans KR",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:var(--fs-body); line-height:1.7; -webkit-font-smoothing:antialiased;}
/* ★★ 과목이 늘면 **스크롤이 일이 된다** (사용자 지적 2026-08-15: *[발화 생략]*). 실측(접힌 카드 87px + 여백 14px):
   12과목 ≈ 1.4k px(2화면) · **30과목 ≈ 3.2k px(4.5화면)**.
   처방 둘 — ⑴ **학기로 묶어** 찾는 범위를 줄이고 ⑵ **격자**로 세로 길이를 1/2~1/3로 만든다.
   글줄이 읽히는 폭(≈760px)은 머리말·면책만 지키면 된다 — 카드는 제목 한 줄이라 넓어도 된다. */
.wrap{max-width:1040px; margin:0 auto; padding:56px 20px 80px;}
.home-head{margin-bottom:32px; max-width:760px;}
.home-title{font-family:"Jeongri Serif","Nanum Myeongjo","Noto Serif KR","Batang",Georgia,serif;
  font-size:var(--fs-cover-title); font-weight:700; margin:0 0 8px; line-height:1.3;}
.home-sub{color:var(--sub); font-size:var(--fs-small); margin:0;}
/* 면책 문구 — 개인 정리 자료임을 첫 화면에서 밝힌다 (사용자 요청 2026-07-28). */
.home-note{margin:14px 0 0; padding:10px 14px; border-left:3px solid var(--line);
  background:var(--paper-raised); color:var(--sub); font-size:var(--fs-small); border-radius:0 3px 3px 0;}
/* 학기 묶음 — 제목은 «어디를 볼지»를 줄이는 장치라 눈에 띄되 카드보다 조용해야 한다. */
.sem{margin:0 0 30px;}
.sem-title{display:flex; align-items:baseline; gap:10px; margin:0 0 12px;
  font-size:var(--fs-small); font-weight:700; color:var(--sub);
  letter-spacing:.04em; text-transform:none;}
.sem-title::after{content:""; flex:1; height:1px; background:var(--line);}
.sem-count{font-weight:400; font-size:var(--fs-micro);}
/* ★ `auto-fill`+`minmax` 라 폭이 좁으면 저절로 1열이 된다 — 모바일에 따로 규칙을 두지 않는다.
   `align-items:start` 가 없으면 한 카드를 펼쳤을 때 **같은 줄의 카드가 함께 늘어난다.** */
.subject-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:12px; align-items:start;}
.subject{background:var(--paper-raised); border:1px solid var(--line);
  border-radius:3px; overflow:hidden;}
.sc-head{display:flex; align-items:center; gap:14px; padding:14px 18px; cursor:pointer;
  list-style:none; user-select:none;}
.sc-head::-webkit-details-marker{display:none;}
.sc-head:hover{background:var(--paper);}
.sc-headtext{flex:1; min-width:0;}
.sc-name{display:block; font-family:"Jeongri Serif","Nanum Myeongjo","Noto Serif KR","Batang",Georgia,serif;
  font-size:var(--fs-head); font-weight:700; line-height:1.4;}
.sc-sub{display:block; color:var(--sub); font-size:var(--fs-micro); margin-top:3px;}
.sc-chev{flex:none; color:var(--sub); font-size:var(--fs-small); transition:transform .18s ease;}
.subject[open] .sc-chev{transform:rotate(90deg);}
.subject[open] .sc-head{border-bottom:1px solid var(--line);}
.sc-rows{display:flex; flex-direction:column; gap:2px; padding:10px 12px 14px;}
.hc-row{display:flex; align-items:center; gap:12px; padding:10px 12px;
  text-decoration:none; color:var(--ink); border-radius:2px; border:1px solid transparent;}
.hc-row:hover{background:var(--paper); border-color:var(--line);}
.hc-row.disabled{opacity:.5; cursor:default;}
.hc-no{font-family:ui-monospace,"SF Mono",Consolas,monospace; color:var(--copper);
  font-weight:700; flex:none; min-width:26px;}
.hc-title{flex:1; font-size:var(--fs-body);}
/* 상태 칩은 컨트롤 계열이라 모서리를 그대로 둔다 — 뷰어도 칩·버튼만 알약을 유지한다. */
.hc-badge{flex:none; font-size:var(--fs-micro); font-weight:700; padding:3px 9px; border-radius:100px;}
.hc-badge.done{background:var(--copper-soft); color:var(--copper);}
.hc-badge.todo{background:transparent; border:1px solid var(--line); color:var(--sub);}
.home-foot{color:var(--sub); font-size:var(--fs-micro); text-align:center; margin-top:36px;}
/* 다른 포트로 나가는 링크임을 조용히 표시한다 — 누르면 주소창이 바뀌는 것이 예고 없이 오면
   «왜 포트가 달라졌지» 가 된다. 색을 쓰지 않는다(뜻을 가진 색은 이미 다른 일을 한다). */
.subject[data-away] .sc-name::after{content:" ↗"; font-size:var(--fs-micro); color:var(--sub);
  font-weight:400; vertical-align:super;}
</style>
</head>
<body>
<div class="wrap">
<header class="home-head">
<h1 class="home-title">전공 정리</h1>
<p class="home-sub">과목을 선택하세요.</p>
<p class="home-note">개인 학습 정리용입니다. 교재·수업 내용과 다르거나 틀린 곳이 있을 수 있습니다.</p>
</header>
{{CARDS}}
<p class="home-foot">전공 학습 자료 · 로컬 뷰어</p>
</div>
<script>
// ★★ **로컬에서는 과목마다 포트가 다르다 — 주소를 런타임에 고른다** (2026-08-15).
//   사용자: *[발화 생략]* ·
//   *[발화 생략]*.
//   ★ **빌드 시점에 박지 않는 이유:** 같은 `index.html` 이 로컬(포트별)과 배포 번들(한 사이트)
//     양쪽에서 맞아야 한다. 빌드가 절대 주소를 박으면 배포본이 로컬을 가리키게 된다.
//   ★ 예전에는 이 판정이 **장마다**(300장) 실렸다. 사이드바를 «이 과목만» 으로 좁히면서
//     그 자리는 사라졌고, 지금 남은 소비자는 **이 홈 한 장**뿐이다.
var LOCAL_PORTS = {{LOCAL_PORTS_JSON}};
(function(){
  var host = location.hostname;
  if(host !== 'localhost' && host !== '127.0.0.1') return;   // 배포본에서는 상대 주소가 맞다
  var cards = document.querySelectorAll('.subject[data-subject]');
  for(var i=0;i<cards.length;i++){
    var name = cards[i].getAttribute('data-subject');
    var port = LOCAL_PORTS[name];
    if(!port || String(port) === location.port) continue;    // 자기 포트면 그대로 둔다
    cards[i].setAttribute('data-away','');
    var links = cards[i].querySelectorAll('a.hc-row');
    for(var j=0;j<links.length;j++){
      links[j].href = location.protocol + '//' + host + ':' + port + '/'
        + links[j].getAttribute('href');
    }
  }
})();
</script>
</body>
</html>"""


def build_home(subjects, ports=None):
    """과목 랜딩 페이지(site/index.html) 생성 — 빌드된 챕터만 링크, 나머지는 회색 표시.

    subjects: [{"name": 과목명, "coverSub": 부제, "chapters": [{number,title,status}],
                "labs": [{href,title,chapterNumber,chapterTitle}]}]
    """
    def esc(s):
        return _htmlmod.escape(str(s))

    # ★★ **학기로 묶는다** (2026-08-15). 선언은 각 과목 `index.json` 의 `semester` 이고
    #   공통 코드는 **읽기만** 한다 — 여기에 학기·과목 이름을 적으면 새 과목이 생긴 날
    #   이 파일만 옛 세상을 말한다(AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
    #   ★ 선언이 없는 과목은 **「학기 미정」으로 맨 뒤**에 둔다. 조용히 섞으면 «아직 안 적었다»가
    #     화면에서 안 보이고, 그러면 영영 안 적힌다(2-2 일곱 과목이 지금 그 상태다).
    # ★★ **교양은 학기가 아니라 분류로 뺀다** (2026-08-15, 사용자 지시: *[발화 생략]*). 학기 축에 섞으면 [발화 생략] 가 한 덩이가
    #   되는데, 찾는 사람 머릿속에서 그 둘은 다른 서랍이다. 그래서 **묶는 축을 하나 더** 둔다.
    #   교양은 학기와 무관하게 **맨 뒤**다 — 전공을 찾으러 오는 자리이기 때문이다.
    groups = {}
    for s in subjects:
        cat = (s.get("category") or "").strip()
        key = "교양" if cat == "교양" else (s.get("semester") or "").strip()
        groups.setdefault(key, []).append(s)
    tail = [k for k in ("", "교양") if k in groups]      # 학기 미정 → 교양 순으로 뒤에
    ordered = ([(k, groups[k]) for k in sorted(k for k in groups if k and k != "교양")]
               + [(k, groups[k]) for k in tail])

    def card(s):
        rows = ""
        for ch in s["chapters"]:
            num = str(ch["number"]).zfill(2)
            fname = "ch" + num + ".html"
            # ★ **남의 과목은 이 워크트리에 파일이 없다** — 그래서 파일 존재로만 판정하면
            #   전 과목 홈에서 남의 장이 전부 «작성 예정» 으로 회색이 된다(2026-08-15).
            #   그 과목 트리가 `built` 를 말해 주면 그것을 믿는다(그쪽 워크트리가 재 본 값이다).
            exists = ch.get("built")
            if exists is None:
                exists = os.path.isfile(os.path.join(out_root(), "site", s["name"], fname))
            done = ch.get("status") == "done"
            badge = "완료" if done else "작성 중"
            bcls = "done" if done else "todo"
            inner = ('<span class="hc-no">' + num + '</span>'
                     '<span class="hc-title">' + esc(ch["title"]) + '</span>'
                     '<span class="hc-badge ' + bcls + '">' + badge + '</span>')
            if exists:
                href = quote(s["name"] + "/" + fname, safe="/")
                rows += '<a class="hc-row" href="' + href + '">' + inner + '</a>'
            else:
                rows += '<div class="hc-row disabled" title="작성 예정">' + inner + '</div>'
        lab_rows = ""
        for lab in s.get("labs", []):
            href = quote(s["name"] + "/" + lab["href"], safe="/")
            title = lab.get("title") or "실험실"
            lab_rows += ('<a class="hc-row hc-lab" href="' + href + '">'
                         '<span class="hc-no">LAB</span>'
                         '<span class="hc-title">' + esc(title) + '</span>'
                         '<span class="hc-badge done">실험실</span></a>')
        if lab_rows:
            rows += '<div class="hc-labs" aria-label="실험실">' + lab_rows + '</div>'
        return ('<details class="subject" data-subject="' + esc(s["name"]) + '">'
                '<summary class="sc-head">'
                '<span class="sc-headtext">'
                '<span class="sc-name">' + esc(s["name"]) + '</span>'
                '<span class="sc-sub">' + s.get("coverSub", "") + '</span>'
                '</span>'
                '<span class="sc-chev">▸</span>'
                '</summary>'
                '<div class="sc-rows">' + rows + '</div>'
                '</details>')

    cards = ""
    for sem, members in ordered:
        label = "교양" if sem == "교양" else ((sem + " 학기") if sem else "학기 미정")
        cards += ('<section class="sem">'
                  '<h2 class="sem-title">' + esc(label)
                  + '<span class="sem-count">' + str(len(members)) + '과목</span></h2>'
                  '<div class="subject-grid">'
                  + "".join(card(s) for s in members)
                  + '</div></section>')

    out = strip_dev_comments(HOME_TEMPLATE).replace("{{CARDS}}", cards)
    out = out.replace("{{LOCAL_PORTS_JSON}}", json.dumps(ports or {}, ensure_ascii=False))
    out_path = os.path.join(out_root(), "site", "index.html")
    # ★ 폴더를 **여기서 만든다** (2026-08-15). 예전에는 챕터 빌드가 `site/<과목>/` 을 만들면서
    #   `site/` 도 함께 생겨 우연히 돌았다 — 그런데 ⑴ 챕터가 0개인 과목 ⑵ 출력 뿌리가 새 폴더인
    #   번들 빌드에서는 그 우연이 성립하지 않는다. 둘이 겹친 날 일곱 갈래가 통째로 죽었다.
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    return out_path


def lint_viewer_css_comments(template):
    r"""뷰어 `<style>` 의 주석이 균형을 이루는가 (열린 날 2026-08-07).

    **무엇이 새어나갔나.** 주석 블록 끝의 `*/` 를 남겨 둔 채 그 아래에 설명을 덧붙였더니
    `… 않는다 */` + 산문 + `*/` 가 되어 **CSS 가 그 자리에서 깨졌다.** 브라우저는 조용히
    회복하면서 뒤따르는 규칙(`.imath .frac` 등)을 통째로 버렸고, 화면은 *[발화 생략]*
    상태가 됐다. **빌드는 전부 통과했다** — HTML 로서는 아무 문제가 없기 때문이다.

    ★ 이 부류가 위험한 이유: 실패가 **화면에만** 나타나고 도구는 전부 초록이다. DOM 을 재
      보지 않았다면 규격을 고쳤다고 보고했을 것이다(실제로 재 봐서 잡았다 — 폰트가
      13.95px 여야 하는데 15.5px 이었다).
    ★ 왜 정규식 하나로 충분한가: `/*`·`*/` 는 CSS 에서 중첩되지 않는다. 그래서 여는 것과
      닫는 것을 **순서대로** 세면 어긋남이 반드시 드러난다.
    """
    style = re.search(r"<style>(.*?)</style>", template, re.S)
    if not style:
        raise ValueError(TEMPLATE + ": <style> block missing")
    body = style.group(1)
    depth, line = 0, 1
    for tok in re.finditer(r"/\*|\*/|\n", body):
        text = tok.group(0)
        if text == "\n":
            line += 1
            continue
        if text == "/*":
            if depth:                      # CSS 주석은 중첩되지 않는다 — 안쪽 `/*` 는 그냥 글자다
                continue
            depth = 1
        else:
            if not depth:
                raise ValueError(TEMPLATE + ": <style> line %d — 열리지 않은 주석을 `*/` 로 "
                                            "닫았다. 그 뒤 CSS 규칙이 통째로 무시된다" % line)
            depth = 0
    if depth:
        raise ValueError(TEMPLATE + ": <style> 의 주석이 닫히지 않았다 (`*/` 누락)")


def lint_viewer_setting_registry(template):
    """보기 설정 컨트롤이 저장 레지스트리에서 빠지는 재발을 빌드 단계에서 막는다."""
    match = re.search(r"var viewerSettingDefaults = \{(.*?)\n\};", template, re.S)
    if not match:
        raise ValueError(TEMPLATE + ": viewerSettingDefaults registry missing")
    registered = set(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*:", match.group(1)))
    if not registered:
        raise ValueError(TEMPLATE + ": viewerSettingDefaults registry is empty")

    errors = []
    used = set()
    for tag in re.findall(r"<button\b[^>]*>", template):
        class_match = re.search(r'class="([^"]*)"', tag)
        classes = set(class_match.group(1).split()) if class_match else set()
        if not ({"tool-toggle", "view-tool"} & classes):
            continue
        id_match = re.search(r'id="([^"]+)"', tag)
        control_id = id_match.group(1) if id_match else "(id 없음)"
        keys_match = re.search(r'data-setting-keys="([^"]+)"', tag)
        if not keys_match:
            errors.append(control_id + ": data-setting-keys 누락")
            continue
        keys = set(keys_match.group(1).split())
        used.update(keys)
        missing = sorted(keys - registered)
        if missing:
            errors.append(control_id + ": 미등록 설정 키 " + ", ".join(missing))

    orphaned = sorted(registered - used)
    if orphaned:
        errors.append("컨트롤과 연결되지 않은 설정 키: " + ", ".join(orphaned))
    if errors:
        raise ValueError(TEMPLATE + ": viewer setting registry lint failed — " + " / ".join(errors))
