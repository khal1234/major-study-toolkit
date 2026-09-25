"""삽화 동작 — 선언을 **정지 프레임 N장**으로 편다. 정본 설계는 `docs/2026-09-07-삽화-동작-사양.md`.

왜 이 모듈이 있나: *[발화 생략]*
(사용자, 2026-09-07). CSS·SMIL 을 손으로 쓰면 빌드가 `t=0.37` 의 좌표를 모르지만,
**선언으로 두면 프레임을 전개할 수 있고 그때부터는 정지 삽화 검사를 프레임 수만큼 돌리는 일**
이다. 이 리포가 치수선·각도 호·분수·등축을 옮겼던 그 길과 같다.

    from buildlib.motion import motion_issues, expand_frames
    for why in motion_issues(fig_id, dg.get("motion")): errors.append(why)
    for idx, frame_svg in expand_frames(dg["svg"], dg["motion"]): check_svg(...)

★ **이 자가 지금 못 하는 것**(사양의 닫힌 목록에서 **일부러 줄인 것**이라 여기 적는다):

- **`scale` 은 아직 안 연다.** 사양은 닫힌 목록에 넣었지만, 저자가 뜻하는 것은 언제나
  「제 자리에서 커진다」이고 그러려면 **그 요소의 bbox 중심**이 필요하다. 중심 없이
  `scale(s)` 를 붙이면 viewBox 원점 기준이라 그림이 통째로 날아간다 — 그건 사양이 아니라
  버그다. 중심을 재는 자를 붙일 때 연다.
- **`grow` 는 `<line>`·`<polyline>` 만.** 「자란다」를 검사가 실제로 보려면 **기하가 짧아져야**
  한다(`stroke-dasharray` 로 흉내 내면 검사기는 여전히 온전한 길이를 본다 — 그러면 중간
  프레임 결함을 잡는다는 이 사양의 이득이 통째로 사라진다). 곡선 `path` 는 자를 붙인 뒤 연다.
- **발행 CSS 는 여기서 안 만든다**(구현 순서 3). 이 모듈은 「재는 쪽」이다.
- **`rotate` 는 `pivot` 을 저자가 준다**(`scale` 을 안 연 이유와 같다 — 중심을 추정하지 않는다).
  대상은 `<g>` 하나이고, 그 안에 `<text>` 가 있으면 오류다(±90° 를 넘으면 글자가 뒤집힌다).
- **`morph` 는 `<line>`·`<polyline>` 의 점을 같은 개수끼리 선형 보간한다.** 곡선 `path` 는 못 본다.
- **`spotlight` 는 SVG 의 최상위 자식 단위로 어둡게 한다.** 밝힐 id 가 최상위 `<g>` 안에 있으면
  그 `<g>` 통째로 밝다 — 한 묶음 안에서 일부만 밝히는 것은 못 한다.
"""
import math
import re

# 사양의 닫힌 목록. 여는 것은 **재는 자가 생긴 뒤**다 — 위 독스트링의 두 줄이 그 사유다.
MOTION_ATTRS = ("opacity", "grow", "dx", "dy", "rotate", "morph")
MOTION_EASES = ("linear", "easeInOut")
ROTATE_TAGS = ("g",)
MORPH_TAGS = ("line", "polyline")
# 무대 조명에서 조명 밖 요소의 불투명도. 고른 값이다(규칙 16): 0.4 는 회로의 나머지가 여전히
# 읽혀 주인공이 안 갈리고, 0.1 은 배경이 사라져 「같은 회로」라는 맥락이 끊긴다. 사양
# (`docs/2026-09-07-삽화-동작-사양.md` 무대 조명 절)이 적은 0.25 를 그대로 쓴다.
SPOTLIGHT_DIM = 0.25
# 어두워지고 밝아지는 데 쓰는 몫 — 그 트랙 구간 길이의 15 %. 고른 값이다: 0 이면 한 프레임에
# 툭 꺼져 「무대 조명」이 아니라 깜빡임이 되고, 절반 가까이면 조명이 다 켜지기 전에 동작이 끝난다.
SPOTLIGHT_RAMP = 0.15
# 변환을 찍는 순서. 사양이 「합성 순서는 평행이동 → 회전」 하나로 못 박아 달라고 했다 —
# 변환 목록이 `translate(…) rotate(θ px py)` 이면 점은 먼저 pivot 둘레로 돌고 그다음 옮겨진다.
TRANSFORM_ORDER = ("rotate", "dx", "dy")
# 하한은 셈이다 — 프레임이 하나면 「시작과 끝」이 없어 움직임이 아니고, 그건 그냥 정지
# 삽화라 이 선언을 쓸 이유가 없다. 둘이 최소 단위다.
MOTION_FRAMES_MIN = 2
# 고른 값이다(잰 값이 아니다 — 규칙 16). 견준 것은 **검사 비용**과 **뜻의 개수**다:
# 프레임 하나가 곧 `check_svg` + `check_figure_lint` 한 벌이고 빌드는 삽화 785개를 돈다.
# 사양이 예로 든 첫 삽화가 4단계라, 단계 사이를 부드럽게 잇는 데 단계당 3프레임이면
# 12 다. 그보다 많이 필요하면 삽화 하나가 너무 많은 것을 말하려는 신호로 본다.
MOTION_FRAMES_MAX = 12
GROW_TAGS = ("line", "polyline")


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pairs(value):
    """[[x, y], …] 을 (x, y) 목록으로. 모양이 틀리면 None."""
    if not isinstance(value, list):
        return None
    out = []
    for p in value:
        if not isinstance(p, list) or len(p) != 2 or _num(p[0]) is None or _num(p[1]) is None:
            return None
        out.append((float(p[0]), float(p[1])))
    return out


def motion_issues(fig_id, motion):
    """선언이 스키마를 지키나. **후보가 아니라 오류다** — 빌드가 그대로 실패로 쓴다."""
    out = []
    if motion is None:
        return out
    tag = str(fig_id) + " [motion]: "
    if not isinstance(motion, dict):
        return [tag + "객체여야 한다"]

    frames = motion.get("frames")
    if not isinstance(frames, int) or not (MOTION_FRAMES_MIN <= frames <= MOTION_FRAMES_MAX):
        out.append(tag + "frames 는 %d~%d 사이의 정수여야 한다 — 받은 값 %r"
                   % (MOTION_FRAMES_MIN, MOTION_FRAMES_MAX, frames))

    caption = motion.get("caption")
    if not isinstance(caption, str) or not caption.strip():
        out.append(tag + "caption 은 발행된다 — 「무엇을 보라」를 한 줄로 적을 것"
                         "(저자 메모가 아니다)")

    tracks = motion.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        out.append(tag + "tracks 가 비었다")
        return out

    for i, track in enumerate(tracks):
        where = tag + "tracks[%d] " % i
        if not isinstance(track, dict):
            out.append(where + "객체여야 한다")
            continue
        target = track.get("target")
        if not isinstance(target, str) or not target.strip():
            out.append(where + "target 은 **id 가 붙은 요소 하나**여야 한다 — "
                               "class 로 여러 개를 한꺼번에 움직이지 않는다"
                               "(자가 「무엇이 움직였나」를 못 되짚는다)")
        attr = track.get("attr")
        if attr not in MOTION_ATTRS:
            out.append(where + "attr 은 닫힌 목록에서 고른다 %s — 받은 값 %r"
                       % (list(MOTION_ATTRS), attr))
        ease = track.get("ease", "linear")
        if ease not in MOTION_EASES:
            out.append(where + "ease 는 닫힌 목록에서 고른다 %s — 임의 베지어를 열면 "
                               "중간 좌표를 사람이 예측할 수 없다" % list(MOTION_EASES))
        for key in ("from", "to"):
            # morph 는 0→1 진행률이 기본이라 from·to 를 안 적어도 된다. 적었으면 수여야 한다.
            if attr == "morph" and key not in track:
                continue
            if _num(track.get(key)) is None:
                out.append(where + "%s 는 수여야 한다 — 받은 값 %r" % (key, track.get(key)))
        if attr == "rotate":
            pivot = track.get("pivot")
            if (not isinstance(pivot, list) or len(pivot) != 2
                    or _num(pivot[0]) is None or _num(pivot[1]) is None):
                out.append(where + "rotate 는 pivot [x, y] (viewBox 좌표)가 필수다 — 중심을 "
                                   "추정하지 않는다. 받은 값 %r" % (pivot,))
        if attr == "morph":
            a_pts, b_pts = _pairs(track.get("points_from")), _pairs(track.get("points_to"))
            if a_pts is None or b_pts is None or len(a_pts) < 2:
                out.append(where + "morph 는 points_from·points_to 에 [x, y] 점을 둘 이상씩 "
                                   "적는다")
            elif len(a_pts) != len(b_pts):
                out.append(where + "morph 두 점 벌의 개수가 다르다 (%d 대 %d) — 보간할 짝이 "
                                   "없다" % (len(a_pts), len(b_pts)))
        spot = track.get("spotlight")
        if spot is not None and (not isinstance(spot, list) or not spot
                                 or not all(isinstance(s, str) and s.strip() for s in spot)):
            out.append(where + "spotlight 는 밝게 둘 id 의 목록이어야 한다 — 받은 값 %r" % (spot,))
        at = track.get("at")
        if (not isinstance(at, list) or len(at) != 2
                or _num(at[0]) is None or _num(at[1]) is None):
            out.append(where + "at 은 [시작, 끝] 두 수여야 한다 (0~1) — 받은 값 %r" % (at,))
        else:
            a, b = float(at[0]), float(at[1])
            if not (0.0 <= a < b <= 1.0):
                out.append(where + "at 은 0 ≤ 시작 < 끝 ≤ 1 이어야 한다 — 받은 값 %r" % (at,))
    return out


def _ease(name, t):
    if name == "easeInOut":
        return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
    return t


def track_value(track, u):
    """전체 진행 `u`(0~1) 에서 이 트랙의 값. 구간 밖에서는 끝값으로 붙잡는다."""
    a, b = float(track["at"][0]), float(track["at"][1])
    lo, hi = float(track.get("from", 0)), float(track.get("to", 1))
    if u <= a:
        return lo
    if u >= b:
        return hi
    return lo + (hi - lo) * _ease(track.get("ease", "linear"), (u - a) / (b - a))


def _element_span(svg, target):
    """`id` 로 요소 하나를 찾는다. 돌려주는 것은 (시작, 끝, 태그이름) — 못 찾으면 None."""
    m = re.search(r"<([A-Za-z][\w:-]*)\b[^>]*\bid\s*=\s*['\"]" + re.escape(target) + r"['\"]",
                  svg)
    if not m:
        return None
    start = m.start()
    end = svg.find(">", m.end())
    if end < 0:
        return None
    return start, end + 1, m.group(1)


def _set_attr(tag_text, name, value):
    """여는 태그 하나에 속성을 넣거나 갈아끼운다."""
    pattern = re.compile(r"\s" + re.escape(name) + r"\s*=\s*(['\"]).*?\1")
    if pattern.search(tag_text):
        return pattern.sub(" " + name + "='" + value + "'", tag_text, count=1)
    closer = "/>" if tag_text.rstrip().endswith("/>") else ">"
    return tag_text[:tag_text.rfind(closer)] + " " + name + "='" + value + "'" + closer


def _get_attr(tag_text, name):
    m = re.search(r"\s" + re.escape(name) + r"\s*=\s*(['\"])(.*?)\1", tag_text)
    return m.group(2) if m else None


def _grow_line(tag_text, ratio):
    x1, y1 = _num(_get_attr(tag_text, "x1")), _num(_get_attr(tag_text, "y1"))
    x2, y2 = _num(_get_attr(tag_text, "x2")), _num(_get_attr(tag_text, "y2"))
    if None in (x1, y1, x2, y2):
        return tag_text
    tag_text = _set_attr(tag_text, "x2", "%.4g" % (x1 + (x2 - x1) * ratio))
    return _set_attr(tag_text, "y2", "%.4g" % (y1 + (y2 - y1) * ratio))


def _points(text):
    nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text or "")]
    return list(zip(nums[0::2], nums[1::2]))


def _grow_polyline(tag_text, ratio):
    pts = _points(_get_attr(tag_text, "points"))
    if len(pts) < 2:
        return tag_text
    seg = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
           for i in range(len(pts) - 1)]
    total = sum(seg)
    if total <= 0:
        return tag_text
    want = total * max(0.0, min(1.0, ratio))
    kept = [pts[0]]
    walked = 0.0
    for i, length in enumerate(seg):
        if walked + length <= want or length == 0:
            kept.append(pts[i + 1])
            walked += length
            continue
        f = (want - walked) / length
        kept.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f,
                     pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f))
        break
    if len(kept) < 2:
        kept.append(kept[0])
    return _set_attr(tag_text, "points",
                     " ".join("%.4g,%.4g" % (x, y) for x, y in kept))


def apply_track(svg, track, value):
    """한 트랙의 값 하나를 SVG 에 반영한 새 SVG. 대상이 없으면 그대로 돌려준다."""
    span = _element_span(svg, track.get("target", ""))
    if span is None:
        return svg
    start, end, tag_name = span
    tag_text = svg[start:end]
    attr = track.get("attr")

    if attr == "opacity":
        tag_text = _set_attr(tag_text, "opacity", "%.4g" % value)
    elif attr in ("dx", "dy"):
        shift = ("translate(%.4g,0)" if attr == "dx" else "translate(0,%.4g)") % value
        prev = _get_attr(tag_text, "transform")
        tag_text = _set_attr(tag_text, "transform",
                             shift if not prev else shift + " " + prev)
    elif attr == "grow":
        if tag_name == "line":
            tag_text = _grow_line(tag_text, value)
        elif tag_name == "polyline":
            tag_text = _grow_polyline(tag_text, value)
    elif attr == "rotate":
        px, py = float(track["pivot"][0]), float(track["pivot"][1])
        turn = "rotate(%.4g %.4g %.4g)" % (value, px, py)
        prev = _get_attr(tag_text, "transform")
        tag_text = _set_attr(tag_text, "transform", turn if not prev else turn + " " + prev)
    elif attr == "morph":
        tag_text = _morph(tag_text, tag_name, track, value)
    return svg[:start] + tag_text + svg[end:]


def _morph(tag_text, tag_name, track, ratio):
    a_pts, b_pts = _pairs(track.get("points_from")), _pairs(track.get("points_to"))
    if not a_pts or not b_pts or len(a_pts) != len(b_pts):
        return tag_text
    pts = [(ax + (bx - ax) * ratio, ay + (by - ay) * ratio)
           for (ax, ay), (bx, by) in zip(a_pts, b_pts)]
    if tag_name == "line" and len(pts) == 2:
        for key, v in zip(("x1", "y1", "x2", "y2"),
                          (pts[0][0], pts[0][1], pts[1][0], pts[1][1])):
            tag_text = _set_attr(tag_text, key, "%.4g" % v)
        return tag_text
    if tag_name == "polyline":
        return _set_attr(tag_text, "points", " ".join("%.4g,%.4g" % p for p in pts))
    return tag_text


def _tag_order(track):
    attr = track.get("attr") if isinstance(track, dict) else None
    return TRANSFORM_ORDER.index(attr) if attr in TRANSFORM_ORDER else len(TRANSFORM_ORDER)


def spotlight_level(track, u):
    """이 트랙의 조명이 u 에서 얼마나 켜졌나 — 0(꺼짐)~1(가장 어둡게). 구간 끝에서는 0 이다."""
    a, b = float(track["at"][0]), float(track["at"][1])
    if u <= a or u >= b:
        return 0.0
    ramp = SPOTLIGHT_RAMP * (b - a)
    return min(1.0, min(u - a, b - u) / ramp) if ramp > 0 else 1.0


def _top_level_spans(svg):
    """루트 `<svg>` 의 직계 자식 요소마다 (시작, 끝) — 여는 태그부터 닫는 태그까지."""
    spans = []
    depth = 0
    open_at = None
    for m in re.finditer(r"<(/?)([A-Za-z][\w:-]*)\b[^>]*?(/?)>", svg):
        closing, self_closing = bool(m.group(1)), bool(m.group(3))
        if closing:
            depth -= 1
            if depth == 1 and open_at is not None:
                spans.append((open_at, m.end()))
                open_at = None
            continue
        if depth == 1:
            if self_closing:
                spans.append((m.start(), m.end()))
            else:
                open_at = m.start()
        if not self_closing:
            depth += 1
    return spans


def apply_spotlight(svg, motion, u):
    """u 에서 켜진 조명대로 조명 밖 최상위 요소를 어둡게 한 SVG.

    켜진 트랙이 여럿이면 그 목록의 **합집합**이 밝다. 밝힐 id 를 품은 최상위 묶음도 밝다.
    원래 불투명도에 곱한다 — opacity 트랙이 먼저 준 값을 지우지 않는다.
    """
    active = [t for t in motion.get("tracks", [])
              if isinstance(t, dict) and t.get("spotlight") and spotlight_level(t, u) > 0]
    if not active:
        return svg
    lit = set(s for t in active for s in t["spotlight"])
    level = max(spotlight_level(t, u) for t in active)
    factor = 1.0 - (1.0 - SPOTLIGHT_DIM) * level
    out = svg
    for start, end in reversed(_top_level_spans(svg)):
        chunk = svg[start:end]
        if any(re.search(r"\bid\s*=\s*['\"]" + re.escape(i) + r"['\"]", chunk) for i in lit):
            continue
        head_end = chunk.find(">") + 1
        head = chunk[:head_end]
        prev = _num(_get_attr(head, "opacity"))
        head = _set_attr(head, "opacity", "%.4g" % ((1.0 if prev is None else prev) * factor))
        out = out[:start] + head + chunk[head_end:] + out[end:]
    return out


def expand_frames(svg, motion):
    """(프레임 번호, 그 프레임의 정지 SVG) 목록. 선언이 깨졌으면 빈 목록이다.

    첫 프레임은 `u=0`, 마지막은 `u=1` 이다 — **정지 첫 프레임만 봐도 그림이 읽혀야 한다**는
    규약(`prefers-reduced-motion`)이 그 자리에 걸린다. 변환은 `TRANSFORM_ORDER` 순서로 찍어
    (회전을 먼저 찍고 평행이동을 그 앞에 붙인다) 트랙을 적은 순서가 결과를 안 바꾼다.
    """
    if motion_issues("x", motion):
        return []
    frames = int(motion["frames"])
    tracks = sorted(motion["tracks"], key=_tag_order)
    out = []
    for i in range(frames):
        u = 0.0 if frames == 1 else i / float(frames - 1)
        cur = svg
        for track in tracks:
            cur = apply_track(cur, track, track_value(track, u))
        out.append((i, apply_spotlight(cur, motion, u)))
    return out


def missing_targets(svg, motion):
    """선언이 가리키는 id(대상·조명 목록) 중 SVG 에 없는 것. 조용히 아무 일도 안 하는 자리를 막는다."""
    if not isinstance(motion, dict) or not isinstance(motion.get("tracks"), list):
        return []
    out = []
    for track in motion["tracks"]:
        if not isinstance(track, dict):
            continue
        names = [track.get("target")] + list(track.get("spotlight") or [])
        for target in names:
            if isinstance(target, str) and target and _element_span(svg, target) is None:
                out.append(target)
    return sorted(set(out))


def _group_body(svg, start):
    """`start` 에서 여는 `<g>` 의 닫는 태그까지 문자열."""
    depth = 0
    for m in re.finditer(r"<(/?)g\b[^>]*?(/?)>", svg[start:]):
        if m.group(1):
            depth -= 1
            if depth == 0:
                return svg[start:start + m.end()]
        elif not m.group(2):
            depth += 1
    return svg[start:]


def shape_target_issues(svg, motion):
    """`rotate`·`morph` 가 다룰 수 없는 대상을 가리키나 — 조용히 안 움직이거나 글자가 뒤집히는 것을 막는다."""
    if not isinstance(motion, dict) or not isinstance(motion.get("tracks"), list):
        return []
    out = []
    for track in motion["tracks"]:
        if not isinstance(track, dict) or track.get("attr") not in ("rotate", "morph"):
            continue
        span = _element_span(svg, track.get("target", ""))
        if not span:
            continue
        name = track.get("target")
        if track["attr"] == "rotate":
            if span[2] not in ROTATE_TAGS:
                out.append("rotate 는 <g> 묶음만 돌린다 — '%s' 는 <%s> 다" % (name, span[2]))
            elif re.search(r"<text\b", _group_body(svg, span[0])):
                out.append("rotate 묶음 '%s' 안에 <text> 가 있다 — 글자는 회전에서 빼고 dx/dy 로 "
                           "따라가게 따로 적는다(±90° 를 넘으면 뒤집힌다)" % name)
        else:
            if span[2] not in MORPH_TAGS:
                out.append("morph 는 %s 만 다룬다 — '%s' 는 <%s> 다"
                           % (list(MORPH_TAGS), name, span[2]))
            elif span[2] == "line" and len(_pairs(track.get("points_from")) or []) != 2:
                out.append("morph 대상 '%s' 는 <line> 이라 점이 정확히 둘이어야 한다" % name)
    return out


def grow_target_issues(svg, motion):
    """`grow` 가 아직 못 다루는 태그를 가리키고 있나 — 조용히 안 움직이는 것을 막는다."""
    if not isinstance(motion, dict) or not isinstance(motion.get("tracks"), list):
        return []
    out = []
    for track in motion["tracks"]:
        if not isinstance(track, dict) or track.get("attr") != "grow":
            continue
        span = _element_span(svg, track.get("target", ""))
        if span and span[2] not in GROW_TAGS:
            out.append("grow 는 %s 만 실제로 짧아진다 — '%s' 는 <%s> 다"
                       % (list(GROW_TAGS), track.get("target"), span[2]))
    return out
