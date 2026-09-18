# -*- coding: utf-8 -*-
r"""삽화 기하를 **두 자로 재서 답이 갈리는 자리**를 찾는다 — 우리 파서 vs `svgelements`.

    python tools/audit_svg_geometry_cross.py                      # 전 과목
    python tools/audit_svg_geometry_cross.py --only=<과목폴더>
    python tools/audit_svg_geometry_cross.py --one=data/<과목>/chNN.json --id=<삽화id>

열린 날 2026-09-08. 사용자: *[발화 생략]* — 라이브러리를 **쓰기 전에
우리 자와 견줘 본다**(AGENTS 규칙 11 「같은 값을 두 가지 방법으로 재 본다」).

★ **이 자는 판정하지 않는다.** 두 자의 답이 갈리는 자리를 보여 줄 뿐이고, 어느 쪽이
  맞는지는 그 삽화를 렌더해서 사람이 본다. 다만 **⑴ 구조적 사각지대**는 판정이 필요 없다 —
  우리 `_svg_segments` 가 그 태그를 **읽는 코드 자체가 없으면** 그건 취향이 아니라 구멍이다.

두 부분을 낸다.

**⑴ 구조적 사각지대 인구조사** — `_svg_segments` 가 읽는 것은 `<rect>`(테두리 있는 것) ·
`<line>` · `<path d>` 셋뿐이다. 그래서 아래는 **좌표를 하나도 안 보고도** 못 본다고 말할 수 있다:

  - `<polygon>` · `<polyline>` — 읽는 코드가 없다
  - `<circle>` · `<ellipse>` 의 **둘레** — 2026-09-08 에 교차 검사에만 반쪽으로 열었다
  - `transform=` 이 걸린 조각 — 좌표를 변환하지 않고 날것으로 읽는다
  - `d` 안의 `A`(호) · `C`·`S`·`Q`·`T`(베지에) — `_path_polyline` 이 직선만 읽는다

**⑵ 글자 교차 차분** — 같은 글자 상자(`_text_bbox`, 두 자가 공유한다 — 이 실험에서 바뀌는
것은 **기하뿐**이다)에 대해 교차를 두 기하로 각각 재고, **한쪽만 잡은 것**을 낸다.

☐ 이 자가 못 보는 것: 글자 상자 자체의 오차. 그건 `fontTools` 로 따로 잰다.
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from buildlib import checks_svg as cs                                        # noqa: E402

try:
    from svgelements import SVG, Shape, Text as SvgText                      # noqa: E402
except ImportError:
    sys.exit("svgelements 가 없다 — `python -m pip install svgelements` 뒤에 다시 돌린다")

# 곡선 한 조각을 폴리라인으로 펼 때 쓰는 표본 수. **고른 값**이다.
#   근거: 이 리포 삽화의 곡선은 대개 반지름 40~140 이고, 한 조각을 24 등분하면
#   현과 호의 최대 벌어짐이 r(1-cos(360/24/2 도)) = r x 0.0034 → 0.14~0.48 단위다.
#   글자 상자(가장 작은 글자도 한 변 9 단위 이상)로 판정하는 자리에서 판정을 못 뒤집는다.
CURVE_SAMPLES = 24

DUMP = False

BLIND_TAGS = ("polygon", "polyline", "circle", "ellipse")
CURVE_CMD_RE = re.compile(r"[AaCcSsQqTt]")
TRANSFORM_RE = re.compile(r"<(\w+)([^>]*?)\btransform\s*=")


_PROBE_SVG = {
    "circle": "<circle cx='50' cy='50' r='20' fill='none' stroke='#333'/>",
    "ellipse": "<ellipse cx='50' cy='50' rx='20' ry='10' fill='none' stroke='#333'/>",
    "polygon": "<polygon points='10,10 30,10 30,30' fill='none' stroke='#333'/>",
    "polyline": "<polyline points='10,10 30,10 30,30' fill='none' stroke='#333'/>",
    "path-curve": "<path d='M10 10 A20 20 0 0 1 30 30' fill='none' stroke='#333'/>",
    "transform": "<line x1='10' y1='10' x2='30' y2='10' stroke='#333'"
                 " transform='translate(100 0)'/>",
}


def capability_probe():
    """**지금 이 순간** 우리 수집기가 그 요소를 읽는가 — 최소 삽화를 넣어 직접 본다.

    ★★ **왜 세는 것으로 안 되나** (고친 날 2026-09-08). 이 절은 원래 태그 개수를 세어
      *[발화 생략]* 이라고 찍었는데, 그 문구는 **`BLIND_TAGS` 라는 손으로 적은
      목록**에 걸려 있었다. 그 다섯을 전부 읽게 만든 뒤에도 출력은 그대로 «읽는 코드가
      없다» 였다 — **낡은 전제를 사실처럼 찍는 자**가 된 것이다(규칙 21: 자기 출력을 자기
      증거로 쓰지 않는다). 개수는 여전히 쓸모가 있으니 남기고, 판정만 **살아 있는 검정**
      으로 바꾼다. 그러면 다음에 무엇을 닫아도 이 표가 저절로 따라온다.

    ☐ **어느 자에게 묻는지가 답을 바꾼다.** 원·타원은 `_svg_segments` 가 아니라
      `_stroked_ellipse_segments` 가 모은다 — 첫 판에서 `_svg_segments` 하나에만 물었다가
      «원 93개 못 읽는다» 는 **틀린 답**을 얻었다. 요소마다 **그것을 맡은 자**에게 묻고,
      출력에도 그 이름을 함께 적는다(안 적으면 다음 사람이 같은 오해를 한다).
    """
    owners = {
        "circle": ("_stroked_ellipse_segments", cs._stroked_ellipse_segments),
        "ellipse": ("_stroked_ellipse_segments", cs._stroked_ellipse_segments),
        "polygon": ("_svg_segments", cs._svg_segments),
        "polyline": ("_svg_segments", cs._svg_segments),
        "path-curve": ("_svg_segments", cs._svg_segments),
        "transform": ("_svg_segments", cs._svg_segments),
    }
    out = {}
    for kind, body in _PROBE_SVG.items():
        svg = "<svg viewBox='0 0 200 200'>" + body + "</svg>"
        name, fn = owners[kind]
        try:
            segs = fn(svg)
        except Exception:                                       # noqa: BLE001
            segs = []
        ok = bool(segs)
        if kind == "transform":
            # 읽는 것만으로는 모자란다 — **옮겨진 자리**로 읽어야 한다.
            ok = bool(segs) and abs(segs[0][0] - 110) < 0.01
        out[kind] = ("읽는다 (%s)" % name) if ok else ("**못 읽는다** (%s)" % name)
    return out


def structural_blind_spots(svg):
    """좌표를 안 보고도 «우리 자가 못 읽는다» 고 말할 수 있는 것만 센다."""
    found = {}
    for tag in BLIND_TAGS:
        n = len(re.findall(r"<" + tag + r"\b", svg))
        if n:
            found[tag] = n
    n_tr = len(TRANSFORM_RE.findall(svg))
    if n_tr:
        found["transform"] = n_tr
    n_curve = sum(1 for m in re.finditer(r"<path\b[^>]*?\bd='([^']*)'", svg)
                  if CURVE_CMD_RE.search(m.group(1)))
    if n_curve:
        found["path-curve"] = n_curve
    return found


VIEWBOX_RE = re.compile(r"viewBox='\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)")


def svgelements_segments(svg):
    """`svgelements` 로 읽은 기하를 선분 목록으로. transform·호·베지에가 여기서 다 펴진다.

    ★★ **눈금을 맞춰 놓고 잰다 (2026-09-08, 첫 실행이 여기서 걸렸다).**
    `svgelements` 는 viewBox 를 뷰포트로 **매핑해서** 좌표를 준다 — `viewBox='0 30 560 300'`
    인 삽화에서 우리 상자는 y 120~180, 저쪽은 **y 90~150** 이었다(30 만큼 밀렸다).
    그 상태로 낸 첫 출력이 «우리 자만 놓침 165건» 이었는데, 그 수는 결함이 아니라
    **자가 안 맞은 것**이었다. viewBox 원점만큼 되밀어 같은 좌표계로 돌린다.

    ★ 되민 뒤에도 두 상자가 안 맞으면 그 삽화는 **판정하지 않고 「눈금 불일치」로 따로 뺀다** —
      비율까지 다른 경우(폭·높이 속성이 있는 삽화)를 조용히 결함으로 세지 않기 위해서다.

    ★ 대상은 **테두리가 있는 도형**뿐이다. 채우기만 한 점 표식은 `_svg_filled_shapes` 가
      보는 다른 축이라, 여기 섞으면 「라벨이 가리키는 점」이 전부 교차로 잡힌다.
    """
    try:
        doc = SVG.parse(io.StringIO(svg), reify=True)
    except Exception as exc:                                    # noqa: BLE001
        return None, "파싱 실패: " + str(exc)[:80]
    vb = VIEWBOX_RE.search(svg)
    ox, oy = (float(vb.group(1)), float(vb.group(2))) if vb else (0.0, 0.0)
    segs = []
    for el in doc.elements():
        if isinstance(el, SvgText) or not isinstance(el, Shape):
            continue
        stroke = getattr(el, "stroke", None)
        if stroke is None or getattr(stroke, "value", None) is None:
            continue
        try:
            path = abs(el)                     # transform 을 좌표에 실제로 먹인다
            pieces = list(path.segments())
        except Exception:                                       # noqa: BLE001
            continue
        for piece in pieces:
            try:
                start, end = piece.start, piece.end
            except AttributeError:
                continue
            if start is None or end is None:
                continue
            name = type(piece).__name__
            if name in ("Move", "Close") and name == "Move":
                continue
            if name in ("Line", "Close"):
                segs.append((float(start.x) + ox, float(start.y) + oy,
                             float(end.x) + ox, float(end.y) + oy))
                continue
            prev = None
            for i in range(CURVE_SAMPLES + 1):
                try:
                    pt = piece.point(i / CURVE_SAMPLES)
                except Exception:                               # noqa: BLE001
                    prev = None
                    continue
                cur = (float(pt.x) + ox, float(pt.y) + oy)
                if prev is not None:
                    segs.append((prev[0], prev[1], cur[0], cur[1]))
                prev = cur
    return segs, None


def crossing_indices(segs, boxes):
    hit = set()
    for i, b in enumerate(boxes):
        for s in segs:
            if cs._seg_x_rect(s, b):
                hit.add(i)
                break
    return hit


def our_segments(svg):
    """빌드가 **교차 검사에 실제로 쓰는** 기하와 같은 것을 만든다(원 둘레 반쪽 포함)."""
    return cs._svg_segments(svg) + cs._stroked_ellipse_segments(svg)


def _bbox(segs):
    if not segs:
        return None
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys))


def dump_one(svg, fig_id):
    """★ **자를 재는 자리.** 두 기하의 전체 상자를 나란히 찍는다.

    첫 실행에서 «우리 자만 놓침 165건» 이 나왔을 때 이 덤프가 그 수의 정체를 갈랐다 —
    좌표계가 어긋나 있으면 그 165 는 결함이 아니라 **자의 눈금이 안 맞은 것**이다.
    """
    ours = our_segments(svg)
    theirs, err = svgelements_segments(svg)
    print("   삽화:", fig_id)
    m = re.search(r"viewBox='([^']*)'", svg)
    print("   viewBox:", m.group(1) if m else "(없음)")
    print("   우리       %4d조각  상자 %s" % (len(ours), _bbox(ours)))
    if theirs is None:
        print("   svgelements 실패:", err)
        return
    print("   svgelements %4d조각  상자 %s" % (len(theirs), _bbox(theirs)))


def examine(svg, fig_id, chapter_label, rows, blind, offscale=None):
    spots = structural_blind_spots(svg)
    for tag, n in spots.items():
        blind[tag] = blind.get(tag, 0) + n
    theirs, err = svgelements_segments(svg)
    if theirs is None:
        rows.append((chapter_label, fig_id, "svgelements " + err, "", ""))
        return
    ours_all = our_segments(svg)
    # ★ 눈금 검정 — 사각지대가 하나도 없는 삽화라면 두 자는 **같은 것을 읽는다.**
    #   그런데도 전체 상자가 어긋나면 그 삽화는 좌표계가 안 맞은 것이므로 **판정에서 뺀다.**
    if not spots:
        ba, bb = _bbox(ours_all), _bbox(theirs)
        if ba and bb and max(abs(x - y) for x, y in zip(ba, bb)) > 0.5:
            if offscale is not None:
                offscale.append((chapter_label, fig_id, ba, bb))
            return
    texts = cs._svg_texts(svg)
    if not texts:
        return
    boxes = [cs._text_bbox(t) for t in texts]
    ours = ours_all
    ours_hit = crossing_indices(ours, boxes)
    their_hit = crossing_indices(theirs, boxes)
    only_theirs = sorted(their_hit - ours_hit)
    only_ours = sorted(ours_hit - their_hit)
    if not only_theirs and not only_ours:
        return
    rows.append((chapter_label, fig_id,
                 "우리 자만 놓침" if only_theirs else "우리 자만 잡음",
                 ", ".join(repr(texts[i]["s"][:12]) for i in (only_theirs or only_ours)),
                 "우리 %d조각 / svgelements %d조각" % (len(ours), len(theirs))))


def walk_chapter(path, rows, blind, only_id=None, offscale=None):
    try:
        with open(path, encoding="utf-8") as fh:
            ch = json.load(fh)
    except (OSError, ValueError):
        return 0
    label = os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path)[:-5]
    seen = 0

    def scan_fig(fig):
        nonlocal seen
        if not isinstance(fig, dict):
            return
        fid = fig.get("id", "?")
        if only_id and fid != only_id:
            return
        svg = fig.get("svg") or ""
        if not svg:
            return
        seen += 1
        if DUMP:
            dump_one(svg, fid)
        examine(svg, fid, label, rows, blind, offscale)

    def scan(collection):
        for item in collection or []:
            for d in item.get("diagrams") or []:
                scan_fig(d)
            scan_fig(item.get("figure"))

    scan((ch.get("theory") or {}).get("sections"))
    scan((ch.get("derivation") or {}).get("formulas"))
    scan(ch.get("practice"))
    scan(ch.get("problems"))
    return seen


def main():
    only, one, only_id = None, None, None
    for a in sys.argv[1:]:
        if a.startswith("--only="):
            only = {s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()}
        elif a.startswith("--one="):
            one = a.split("=", 1)[1]
        elif a.startswith("--id="):
            only_id = a.split("=", 1)[1]
        elif a == "--dump":
            globals()["DUMP"] = True
        else:
            sys.exit("모르는 인자: " + a + "\n쓰는 법 — --only=<과목> · --one=<경로> --id=<삽화id>")

    rows, blind, offscale, figs, chapters = [], {}, [], 0, 0
    if one:
        figs += walk_chapter(one, rows, blind, only_id, offscale)
        chapters = 1
    else:
        import audit_content                                                 # noqa: E402
        for folder in audit_content.subject_dirs():
            if only and os.path.basename(folder) not in only:
                continue
            for name in sorted(n for n in os.listdir(folder)
                               if re.fullmatch(r"ch\d{2}\.json", n)):
                chapters += 1
                figs += walk_chapter(os.path.join(folder, name), rows, blind,
                                     None, offscale)

    print("삽화 기하 — 두 자 대조 (우리 파서 vs svgelements)\n")
    print("⑴ 요소별 인구조사 — 그것을 맡은 자가 **지금** 읽는가 (살아 있는 검정)")
    probe = capability_probe()
    if blind:
        for tag, n in sorted(blind.items(), key=lambda kv: -kv[1]):
            print("   %-14s %5d 개   %s" % (tag, n, probe.get(tag, "?")))
    else:
        print("   없음")
    print("\n⑵ 글자 교차 차분 — 같은 글자 상자에 기하만 바꿔 잰 결과")
    if rows:
        for label, fid, kind, which, counts in rows:
            print("   [%s] %s — %s" % (kind, label, fid))
            if which:
                print("        글자: " + which + "   (" + counts + ")")
    else:
        print("   갈린 삽화 없음")
    if offscale:
        print("\n☐ 눈금 불일치 — 판정에서 뺐다(두 자가 같은 좌표계로 안 읽힌 삽화)")
        print("   ※ 남은 차이가 **몇 px** 이면 대개 «칠만 한 화살촉» 이다 — 우리 쪽은 그것을"
              " 선분으로도 세고(글자를 가로지르면 결함이니까) 저쪽은 안 센다. 결함이 아니라"
              " **두 자의 포함 범위가 다른 것**이고, 우리 쪽이 일부러 넓다(2026-09-08 판정).")
        for label, fid, ba, bb in offscale[:8]:
            print("   %s — %s" % (label, fid))
            print("        우리 %s / svgelements %s" % (ba, bb))
        if len(offscale) > 8:
            print("   … 그 밖 %d개" % (len(offscale) - 8))
    print("\n합계 — 삽화 %d개 · 장 %d개 · 갈린 자리 %d건 · 눈금 불일치 %d개"
          % (figs, chapters, len(rows), len(offscale)))
    if figs == 0:
        sys.exit("삽화를 한 개도 안 봤다 — 순회 범위를 확인할 것(0건이 «없다» 가 아니다)")


if __name__ == "__main__":
    main()
