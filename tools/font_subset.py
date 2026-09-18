# -*- coding: utf-8 -*-
r"""화면에 실제로 나오는 글자만 남긴 **웹폰트 부분집합**을 만든다.

★ 왜 이 도구가 필요한가 (2026-08-13, 실측으로 열림).
  뷰어 CSS 는 읽는 자리에 `"Nanum Myeongjo","Noto Serif KR","Batang",Georgia,serif` 를,
  나머지에 `"Pretendard",…` 를 선언한다. 그런데 **선언한 것과 그려지는 것은 다르다** —
  브라우저 실측 결과 이 기기에는 Nanum Myeongjo 도 Noto Serif KR 도 **설치돼 있지 않고**,
  본문 세리프는 시스템 폴백이 그리고 있었다(폭이 «없는 글꼴»과 정확히 같다).
  즉 **독자 기기마다 다른 글꼴로 보인다** — 조판을 재는 자들이 전제한 글꼴이 아니다.

★ 왜 부분집합인가. 한글 글꼴은 전체를 실으면 얼굴 하나에 수 MB 다. 그런데 이 자료가 쓰는
  글자는 **정해져 있다**(챕터 JSON + 템플릿이 전부다). 쓰는 글자만 남기면 한 자릿수 KB~수백 KB 로
  줄어든다. 그래서 «전부 싣기»가 아니라 «쓰는 것만 싣기»가 맞는 형태다.

★★ **부분집합은 OFL 이 말하는 «수정본(Modified Version)» 이다.**
  OFL FAQ 가 못 박는다 — *[발화 생략]*
  Pretendard 의 RFN 은 `Pretendard`·`Source`·`Inter`·`M PLUS 1`, 나눔글꼴의 RFN 은
  `NanumMyeongjo`·`Nanum` 계열이다. 따라서 **부분집합에는 원래 이름을 쓸 수 없고**,
  이 도구가 `--as` 로 받은 새 이름을 글꼴 안의 이름표에도 함께 박는다.
  · 원본 라이선스 전문과 저작권 표시는 산출물 옆에 그대로 둔다(OFL 필수 조건).
  · 이름을 바꾸는 것은 «출처를 감추는 것»이 아니다 — 오히려 **원본과 헷갈리지 않게 하라**는
    것이 그 조항의 목적이고, 출처는 라이선스 파일과 이 독스트링이 밝힌다.

★ 글자 목록은 **손으로 적지 않는다.** 내용이 바뀌면 쓰는 글자도 바뀌므로, 챕터 JSON 과
  템플릿을 그때그때 훑어 모은다. 손으로 적으면 새 낱말이 들어온 날 그 글자만 두부가 된다.

쓰는 법
  python tools/font_subset.py corpus                 # 무엇이 얼마나 쓰이는지만 센다(읽기 전용)
  python tools/font_subset.py corpus --all-subjects  # **전 과목 합집합** (커밋된 것만 읽는다)
  python tools/font_subset.py build --src <파일> --as <새이름> [--out <디렉터리>] [--all-subjects]

★ 실어 두는 한 벌은 **`--all-subjects` 로 만든다** — 글꼴은 공통 뷰어가 선언하므로 과목마다
  다른 부분집합을 두면 같은 화면 규격이 과목마다 다른 글꼴 위에서 재어진다.

의존: `fonttools[woff]`(부분집합·woff2 쓰기). 없으면 build 는 무엇을 설치해야 하는지 말하고 멈춘다.
"""
import os
import re
import sys
import json
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from audit_content import CHAPTERS, DATA                      # noqa: E402
from buildlib.checks_content import iter_visible_texts        # noqa: E402

# ★ 화면에 글자가 나오는 자리는 데이터만이 아니다 — 템플릿의 UI 문구·버튼·범례도 독자가 읽는다.
#   여기를 빠뜨리면 «초기화»·«정답 · 풀이 뼈대 펼치기» 같은 글자가 두부가 된다.
TEMPLATE_FILES = (
    os.path.join(ROOT, "site", "template", "viewer.template.html"),
    os.path.join(ROOT, "site", "template", "tables.template.html"),
    os.path.join(ROOT, "tools", "buildlib", "render.py"),   # 목록 페이지(HOME_TEMPLATE)
)

# 항상 넣는 것 — 아직 안 쓰였어도 다음 문장에서 바로 나올 수 있는 자리다.
# 이걸 안 넣으면 «숫자 하나 고쳤더니 그 숫자만 두부» 같은 사고가 난다.
# ★★ **뷰어가 그리는 기호도 여기 든다** (2026-09-08). `‖`(U+2016, 노름)은 데이터 어디에도
#   글자로 안 적힌다 — 저자는 `\|` 라고 쓰고 **뷰어의 `renderMath` 가 그 글리프를 만든다.**
#   말뭉치는 데이터와 템플릿 «문자열»만 훑으므로 이런 글자는 영원히 안 걸리고, 그래서
#   *[발화 생략]* 가 사실처럼 굳어 ASCII 이중 파이프로 대신 그리고 있었다.
#   원본 넷 전부에 있다(`font_subset.py has --src=… ‖` 로 확인).
#   → **렌더러가 만들어 내는 글자는 여기 적는다.** 말뭉치가 못 보는 자리다.
ALWAYS = set(
    "‖ "
    "0123456789"
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    " !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"
    "°·×–—‘’“”… "
)


def _strip_comments(src):
    r"""**주석을 걷어낸다** — 주석의 한글은 화면에 안 나간다.

    ★ 왜 중요한가: 주석까지 세면 부분집합에 안 쓰는 글자가 섞이는 것은 둘째 문제이고,
      **빌드 경고가 오탐을 낸다.** 주석 한 줄을 고쳤을 뿐인데 *[발화 생략]* 가
      뜨면 그 경고는 곧 무시된다 — **경보 피로가 검사기를 죽인다.**
    ★ `//` 는 **줄 맨 앞에 올 때만** 주석으로 본다. 문자열 안의 `//`(경로·URL)까지 지우면
      진짜 화면 문구를 잃는데, 그건 두부로 이어지는 반대편 실패다. 둘 중에서는 **더 넣는 쪽**이 낫다.

    ★★ **`<!-- -->` 를 안 걷고 있었다 (2026-08-15).** 위 두 줄은 CSS·JS 형태만 알았는데
      이 도구가 주로 읽는 `viewer.template.html` 은 **HTML 이다.** 그래서 템플릿에 설명
      주석을 한 줄 붙였더니 그 한글이 말뭉치에 들어와 빌드가 *[발화 생략]*
      을 신고했다(실측: 뷰어 분리 주석의 «없**앤**»). **바로 이 독스트링이 막겠다고 적어 둔
      그 오탐**이라, 주석 문구를 고치는 것이 아니라 자를 고친다.
      · 조건부 주석(`<!--[if IE]>`)도 함께 걷는다 — 거기 한글이 있을 수 없어 손해가 없다.
      · **빌드도 같은 것을 지운다**(`render.strip_dev_comments`) — 화면에 안 나가는 것을
        말뭉치가 세면 두 자가 다른 화면을 재게 된다.
    """
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", src)


def _template_strings():
    """템플릿에서 **화면에 나갈 수 있는 부분**만 흘린다.

    목록 페이지 쪽(`render.py`)은 파이썬 소스라 통째로 보면 주석·독스트링이 전부 들어온다.
    그래서 **`HOME_TEMPLATE` 문자열 하나만** 잘라 쓴다 — 그게 실제로 나가는 HTML 이다.
    """
    for path in TEMPLATE_FILES:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        if path.endswith(".py"):
            marker = "HOME_TEMPLATE = "
            if marker not in src:
                continue
            src = src.split(marker, 1)[1].split('\n"""', 1)[0]
        for line in _strip_comments(src).splitlines():
            if re.search(r"[가-힣]", line):
                yield line


# ── 전 과목 합집합 (2026-08-15) ──────────────────────────────────────────────
#
# **글꼴은 콘텐츠가 아니라 뷰어의 일부다.** 선언하는 자리가 공통 템플릿이라 12과목이 같은 네
# 얼굴을 요구하는데, 부분집합은 «그 워크트리의 과목» 하나만 보고 만들어져 **열역학에만** 있었다.
# 실측(2026-08-15, 고체역학 ch05 브라우저): woff2 **404 넷** · 실어 둔 얼굴 4개 전부
# `status: error` · `Jeongri Serif` 폭이 «없는 글꼴»과 같음 — 명조 자리는 **이미 갈려 있었다.**
# (본문이 멀쩡해 보인 것은 이 기기에 Pretendard 가 깔려 있어서다. 독자 기기에는 없을 수 있고
#  그게 애초에 글꼴을 싣기로 한 이유다.)
#
# ★ **과목마다 한 벌씩 두지 않는다.** 그러면 같은 글꼴이 과목마다 다른 부분집합이 되어
#   «어느 화면에서 무엇이 두부가 되나»를 아무도 못 센다. 합집합 한 벌이면 그 질문이 사라진다 —
#   뷰어를 `_assets` 한 벌로 뽑은 것과 같은 판정이다.
#
# ★★ **남의 워크트리를 파일시스템으로 열지 않는다** (AGENTS 「다른 과목은 커밋으로 읽는다」).
#   `git show` 로 **커밋된 상태만** 읽는다 — 그 과목 세션이 반쯤 고쳐 둔 것을 정본으로
#   오인하지 않기 위해서다. 대상 갈래는 **워크트리가 달린 것**으로 잡는다(과목 이름을 안 적는다).

def _git(args):
    import subprocess                                                          # noqa: E402
    return subprocess.run(["git", "-C", ROOT, "-c", "core.quotepath=false"] + args,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def subject_branches():
    """살아 있는 갈래 — 워크트리가 달린 것만. 과목 이름을 알지 않는다."""
    out = []
    for line in _git(["worktree", "list", "--porcelain"]).stdout.splitlines():
        if line.startswith("branch "):
            name = line.split(" ", 1)[1].strip().rsplit("/", 1)[-1]
            if name not in out:
                out.append(name)
    return out


def branch_chapters(branch):
    """그 갈래에 **커밋된** 챕터 JSON 을 `(경로, 데이터)` 로 흘린다."""
    listing = _git(["ls-tree", "-r", "--name-only", branch, "--", "data/"]).stdout
    for path in listing.splitlines():
        path = path.strip()
        if not re.search(r"/ch\d{2}\.json$", path):
            continue
        raw = _git(["show", branch + ":" + path]).stdout
        if not raw.strip():
            continue
        try:
            yield path, json.loads(raw)
        except json.JSONDecodeError:
            # 깨진 것을 **조용히 건너뛰지 않는다** — 그 과목 글자가 통째로 빠지면 나중에
            # 그 화면만 두부가 되는데, 그때는 원인을 못 찾는다.
            print("  [건너뜀] JSON 을 못 읽었다: %s:%s" % (branch, path))


SWEPT_SUBJECTS = []
"""마지막 `--all-subjects` 순회가 **실제로 읽은 과목 폴더** 이름들.

★ 왜 갈래가 아니라 과목을 적나 (2026-09-08). 이 자는 「갈래 하나만 보고 만들면 남의 과목이
두부가 된다」를 막으려고 **갈래 목록**을 남겼는데, 2026-09-07 평탄화로 갈래가 `main` 하나가
됐다. 그래서 목록은 언제나 `['main']` 이고 그것을 세던 회귀는 **영원히 통과할 수 없는 자**가
됐다(실제로 이 날 걸렸다). 지키려던 것은 「합집합인가」이지 「갈래가 여럿인가」가 아니므로,
**읽은 과목 수**로 다시 적는다 — 전제가 죽으면 조항이 아니라 전제를 다시 잰다.
"""


def _sources(all_subjects):
    """말뭉치의 출처를 `(라벨, 챕터데이터)` 로 흘린다 — 한 과목이냐 전 과목이냐만 가른다."""
    del SWEPT_SUBJECTS[:]
    if not all_subjects:
        for ch in CHAPTERS:
            with open(os.path.join(DATA, ch + ".json"), encoding="utf-8") as fh:
                yield ch, json.load(fh)
        return
    for branch in subject_branches():
        seen = 0
        for path, data in branch_chapters(branch):
            seen += 1
            # `data/<과목>/chNN.json` 에서 과목 이름을 뽑는다 — 과목 이름을 코드가 알지 않는다.
            parts = path.split("/")
            if len(parts) >= 3 and parts[-2] not in SWEPT_SUBJECTS:
                SWEPT_SUBJECTS.append(parts[-2])
            yield branch, data
        if not seen:
            # ★ 0장도 **찍는다.** 안 찍으면 «읽었는데 비었다»와 «못 읽었다»가 화면에서 같아진다
            #   (규칙 11: 범위를 확인 안 한 0건은 「없다」가 아니다).
            yield branch, {}


def collect(all_subjects=False):
    """이 과목이 실제로 쓰는 문자 집합을 모은다. (chars, 출처별 통계)"""
    chars = set(ALWAYS)
    stats = {}
    for label, data in _sources(all_subjects):
        before = len(chars)
        for _where, text in iter_visible_texts(data):
            chars.update(text)
        stats[label] = stats.get(label, 0) + (len(chars) - before)
    before = len(chars)
    for line in _template_strings():
        chars.update(line)
    stats["template"] = len(chars) - before
    chars = {c for c in chars if c >= " " and c != ""}
    return chars, stats


def buckets(chars):
    """문자를 갈래로 나눠 센다 — 어느 갈래가 용량을 먹는지 보여야 판단이 선다."""
    out = {"한글 음절": [], "한글 자모": [], "라틴": [], "숫자": [], "그리스": [],
           "한자": [], "기호·구두점": []}
    for c in sorted(chars):
        o = ord(c)
        if 0xAC00 <= o <= 0xD7A3:
            out["한글 음절"].append(c)
        elif 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
            out["한글 자모"].append(c)
        elif c.isdigit() and o < 0x80:
            out["숫자"].append(c)
        elif ("A" <= c <= "Z") or ("a" <= c <= "z"):
            out["라틴"].append(c)
        elif 0x0370 <= o <= 0x03FF or 0x1D400 <= o <= 0x1D7FF:
            out["그리스"].append(c)
        elif 0x4E00 <= o <= 0x9FFF:
            out["한자"].append(c)
        else:
            out["기호·구두점"].append(c)
    return out


def cmd_corpus(argv):
    chars, stats = collect("--all-subjects" in argv)
    print("[말뭉치] 서로 다른 문자 %d개" % len(chars))
    for name, items in buckets(chars).items():
        if items:
            print("  %-10s %5d" % (name, len(items)))
    print("[출처별 새로 들어온 문자]")
    for key, n in stats.items():
        print("  %-10s +%d" % (key, n))
    if "--list" in argv:
        print("".join(sorted(chars)))
    # 기호는 눈으로 한 번 보는 것이 값어치가 있다 — 두부가 되면 가장 먼저 티가 난다.
    if "--symbols" in argv:
        for c in buckets(chars)["기호·구두점"]:
            print("U+%04X %s  %s" % (ord(c), c, unicodedata.name(c, "?")))
    return 0


def cmd_build(argv):
    try:
        from fontTools import subset                              # noqa: F401
        from fontTools.ttLib import TTFont                        # noqa: F401
    except ImportError:
        sys.exit("fonttools 가 없다. `python -m pip install \"fonttools[woff]\"` 로 설치할 것 "
                 "(woff2 쓰기에 brotli 가 함께 들어온다).")
    from fontTools import subset
    from fontTools.ttLib import TTFont

    def arg(name, default=None):
        return next((a.split("=", 1)[1] for a in argv if a.startswith(name + "=")), default)

    src = arg("--src")
    new_name = arg("--as")
    # ★ 굵기를 **명시로 받는다** — 글꼴 안의 nameID 2 로 추측하면 안 된다.
    #   OpenType 은 nameID 2 에 Regular/Bold/Italic/Bold Italic 넷만 허용해서
    #   **SemiBold 도 «Regular» 로 적혀 있다.** 추측하면 SemiBold 산출물이 Regular 를 덮는다
    #   (파일 이름이 같아진다). 자리마다 갈리는 것을 막는 이 리포의 방식 그대로,
    #   **부르는 쪽이 선언**하고 도구는 그것을 쓴다.
    style = arg("--style")
    out_dir = arg("--out", os.path.join(ROOT, "site", "fonts"))
    if not src or not new_name or not style:
        sys.exit("--src=<원본 글꼴 파일> --as=<새 글꼴 이름> --style=<Regular|SemiBold|Bold> 이 필요하다. "
                 "이름을 바꾸는 이유는 이 파일 독스트링의 OFL 항목에 있다.")
    if not os.path.isfile(src):
        sys.exit("원본을 찾을 수 없다: " + src)

    all_subjects = "--all-subjects" in argv
    chars, _stats = collect(all_subjects)
    os.makedirs(out_dir, exist_ok=True)
    font = TTFont(src)

    # ★ **가변 글꼴은 굵기 하나로 굳혀서 싣는다** (2026-08-13).
    #   가변 축을 남기면 파일이 훨씬 크고, 우리가 쓰는 굵기는 400·600·700 셋뿐이다.
    #   `--wght` 를 주면 그 축 값으로 인스턴스를 뜬다 — **명시로 받는다**(추측하면 굵기가 갈린다).
    wght = arg("--wght")
    if wght:
        if "fvar" not in font:
            sys.exit("가변 글꼴이 아니라서 --wght 를 적용할 수 없다: " + src)
        from fontTools.varLib import instancer                       # noqa: E402
        font = instancer.instantiateVariableFont(font, {"wght": float(wght)}, inplace=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.desubroutinize = True
    options.layout_features = ["*"]      # 한글 조합·커닝을 살린다
    options.name_IDs = ["*"]
    options.notdef_outline = True
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)

    # ★ 이름표를 새 이름으로 바꾼다 — RFN 조항이 요구하는 것이 이것이다.
    #   1(family)·2(subfamily)·4(full)·6(postscript)·16·17(typographic) 을 함께 바꿔야
    #   브라우저·OS 가 같은 이름으로 본다(하나만 바꾸면 자리마다 갈린다).
    #   nameID 2 는 OpenType 이 넷만 허용하므로 Bold 만 그대로 쓰고 나머지는 Regular 로 둔다 —
    #   실제 굵기는 17(typographic subfamily)과 **CSS 의 `@font-face` 선언**이 말한다.
    ps_name = re.sub(r"[^A-Za-z0-9]", "", new_name)
    style = re.sub(r"[^A-Za-z0-9]", "", style)
    ot_style = "Bold" if style.lower() == "bold" else "Regular"
    for record in font["name"].names:
        if record.nameID in (1, 16):
            record.string = new_name
        elif record.nameID == 2:
            record.string = ot_style
        elif record.nameID == 17:
            record.string = style
        elif record.nameID == 4:
            record.string = new_name + " " + style
        elif record.nameID == 6:
            record.string = ps_name + "-" + style

    out = os.path.join(out_dir, ps_name + "-" + style + ".woff2")
    font.flavorData = None
    font.save(out)
    size = os.path.getsize(out)

    # ★★ **어떤 글자를 넣었는지 남긴다** — 이 파일이 빌드 경고의 근거다.
    #   부분집합은 «오늘 내용»에 묶여 있어서, 새 낱말이 들어오면 그 글자만 두부가 된다.
    #   그런데 그건 **화면을 열어 보기 전에는 안 보인다.** 빌드가 이 목록과 지금 말뭉치를
    #   대조해 알리게 하려면 목록이 파일로 남아 있어야 한다(폰트 안의 cmap 을 읽게 하면
    #   빌드가 fonttools 에 매달린다 — 다른 과목·다른 기기에서 빌드가 죽는다).
    # ★ **범위를 함께 적는다** (2026-08-15). 이 목록이 «한 과목치»인지 «전 과목 합집합»인지
    #   파일만 봐서는 구별이 안 됐다. 공용 한 벌로 옮기면서 그 구별이 곧 «이 글꼴이 남의 과목
    #   화면도 덮는가»가 되므로, 무엇을 보고 만들었는지를 산출물이 스스로 말하게 한다.
    manifest = os.path.join(out_dir, "corpus.json")
    with open(manifest, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"scope": "all-subjects" if all_subjects else "this-subject",
                   "branches": subject_branches() if all_subjects else [],
                   "subjects": sorted(SWEPT_SUBJECTS),
                   "chars": "".join(sorted(chars))}, fh, ensure_ascii=False, indent=1)

    print("[부분집합] %s → %s" % (os.path.basename(src), os.path.relpath(out, ROOT)))
    print("  글자 %d개 · %.1f KB" % (len(chars), size / 1024.0))
    print("  [말뭉치 기록] %s" % os.path.relpath(manifest, ROOT))
    print("  ★ OFL 원문과 저작권 표시를 %s 옆에 함께 둘 것 (필수 조건)."
          % os.path.relpath(out_dir, ROOT))
    return 0


def missing_chars(shipped_text, chars):
    """**순수 함수** — 실어 둔 글자(`shipped_text`)에 없는 것만 정렬해 돌려준다.

    판정을 순수 함수로 떼어 두는 이유는 회귀가 잡을 수 있게 하려는 것이다. 파일을 읽는
    부분과 섞어 두면 테스트가 진짜 `corpus.json` 을 건드려야 해서 아무도 안 잠근다.
    공백은 세지 않는다 — 두부가 되지 않는다.
    """
    shipped = set(shipped_text or "")
    return sorted(c for c in set(chars) - shipped if c.strip())


def missing_from_shipped_fonts():
    """지금 말뭉치에는 있는데 **실어 둔 부분집합에는 없는** 글자를 돌려준다.

    ★ 대상이 아닌 과목은 실패가 아니다 — `site/fonts/corpus.json` 이 없으면(=웹폰트를
      안 싣는 과목이면) 빈 목록이다. 선언이 곧 opt-in 이라는 이 리포의 규약 그대로다.
    """
    manifest = os.path.join(ROOT, "site", "fonts", "corpus.json")
    if not os.path.isfile(manifest):
        return []
    with open(manifest, encoding="utf-8") as fh:
        shipped = json.load(fh).get("chars", "")
    if not shipped:
        return []
    chars, _stats = collect()
    return missing_chars(shipped, chars)


def cmd_has(argv):
    """원본 글꼴이 그 글자를 **가지고 있나** — 부분집합을 뜨기 전에 묻는 물음.

    ★ 왜 열었나 (2026-09-08). 뷰어가 노름 `‖`(U+2016)을 ASCII 이중 파이프 `||` 로 대신
      그리고 있었고, 그 근거가 *[발화 생략]* 였다.
      그런데 **그 실측은 「부분집합에 없다」였다** — 부분집합은 말뭉치에 그 글자가 없으면
      당연히 안 넣는다. 「원본에 없다」와 「우리가 안 넣었다」는 다른 말이고, 둘을 가르는
      창구가 없어서 대안이 없는 것처럼 굳어 있었다(규칙 11 — 순회 범위를 모르는 「없다」).
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        sys.exit("fonttools 가 없다. `python -m pip install \"fonttools[woff]\"`")
    src = next((a.split("=", 1)[1] for a in argv if a.startswith("--src=")), None)
    text = "".join(a for a in argv[1:] if not a.startswith("--"))
    if not src or not text:
        sys.exit("--src=<원본 글꼴 파일> 과 찾을 글자가 필요하다.")
    cmap = set()
    for table in TTFont(src)["cmap"].tables:
        cmap.update(table.cmap)
    print("[원본] %s" % os.path.basename(src))
    for c in dict.fromkeys(text):
        print("  U+%04X %s — %s" % (ord(c), c, "있다" if ord(c) in cmap else "없다"))
    return 0


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("corpus", "build", "has"):
        sys.exit(__doc__.strip().splitlines()[0] + "\n"
                 "  python tools/font_subset.py corpus [--list] [--symbols]\n"
                 "  python tools/font_subset.py build --src=<파일> --as=<새이름> [--out=<디렉터리>]\n"
                 "  python tools/font_subset.py has --src=<파일> <글자…>")
    if argv[0] == "has":
        return cmd_has(argv)
    return cmd_corpus(argv) if argv[0] == "corpus" else cmd_build(argv)


if __name__ == "__main__":
    sys.exit(main())
