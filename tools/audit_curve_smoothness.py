# -*- coding: utf-8 -*-
"""**곡선으로 그린 것이 실제로 매끄러운가** (열린 날 2026-09-10).

    python tools/audit_curve_smoothness.py                 # 전 과목 (지금 학기 먼저)
    python tools/audit_curve_smoothness.py --only=<과목>
    python tools/audit_curve_smoothness.py --limit=<각도>  # 문턱을 바꿔 재 본다
    python tools/audit_curve_smoothness.py --histogram     # 문턱을 고르려고 분포를 본다

★ **왜 열렸나** — 사용자 2026-09-10: *[발화 생략]* · *[발화 생략]*. **재지적**이라는 것이 요점이다.

  구조적 원인: `tools/svg_curve_points.py` 는 사인·원호 좌표를 **찍는 생성기**이지 이미 그려진
  것을 **재는 자**가 아니다. 그래서 「17점 polyline 이라 꺾여 보인다」를 한 번 손으로 고쳐도
  다른 삽화에 남은 같은 부류는 아무 검사도 안 탔다. 지적이 인스턴스로만 닫힌 자리다(규칙 7).

## 무엇을 재나

`polyline`·`polygon` 의 `points` 와 `path` 의 `d` 안에서 **직선(`M`/`L`)만으로 이어진 점 사슬**을
꺼내, 이웃 세 점이 만드는 **꺾임각**(앞 선분 방향과 뒤 선분 방향의 사잇각)을 전부 잰다.
`C`·`Q`·`A` 로 그린 자리는 애초에 매끄러우므로 사슬을 거기서 끊는다.

## 곡선인지 어떻게 아나 — 직선 도형을 안 잡으려고

★ **첫 판을 버렸다(같은 날).** 처음에는 「꺾임각 중앙값이 0 이 아니면 곡선」으로 잡았는데,
전 과목 90개 사슬 중 **82개가 걸렸다** — 저항 기호·스프링 지그재그가 꼭짓점마다 137° 로 꺾여
중앙값 조건을 그대로 통과했기 때문이다. 자를 결론으로 쓰기 전에 자를 먼저 잰 자리다(규칙 21).

지금 쓰는 판정은 **「모서리에서 사슬을 끊는다」** 다.

1. 꺾임이 `CORNER_DEG`(60°)를 넘는 꼭짓점은 **곡선의 면이 아니라 모서리**다 — 거기서 끊는다.
   지그재그는 모든 꼭짓점이 모서리라 조각이 남지 않고, 사각 테두리도 마찬가지로 사라진다.
2. 남은 조각이 `MIN_POINTS`(5) 점 이상이고 꺾임각 중앙값이 `CURVE_INTENT_DEG`(3°) 이상이면
   **점으로 흉내 낸 곡선**으로 본다. 한 도형 안에 테두리와 곡선이 섞여 있어도 곡선 쪽만 남는다.
3. 그 조각의 **볼록 깊이**가 `--limit` 를 넘으면 신고한다.

## ★ 문턱은 각도가 아니라 **픽셀**이다 (규칙 16 — 고른 값)

각도만으로는 못 정한다. 같은 12° 라도 선분이 6px 이면 안 보이고 100px 이면 확 꺾여 보인다 —
실측이 그랬다(응용고체 `fig-11-principal-slide` 는 12.2° 인데 촘촘해서 매끄럽고,
기계재료 `fig-glass-viscosity` 는 10.0° 인데 선분이 66px 라 각져 보인다).

그래서 재는 것은 **원호와 현 사이의 벌어짐**(sagitta)이다. 꺾임각 θ, 짧은 쪽 선분 L 일 때

    깊이 = (L / 2) · tan(θ / 4)

이고, 이것이 **선 두께의 절반**을 넘으면 꺾임이 선 밖으로 삐져나와 눈에 띈다.
이 리포의 곡선 기본 두께가 2px 이므로 `DEFAULT_LIMIT = 1.0px` 을 고른다.

## ☐ 이 자가 못 보는 것 (규칙 21)

- **매끄러움을 「보이는가」로 재지 않는다.** 각도만 본다 — 선분이 3px 로 아주 짧으면 20° 로 꺾여도
  화면에서는 안 보인다. 그래서 **선분 길이도 함께 찍는다**(판정은 사람이 한다).
- **베지에가 매끄러운지는 안 본다.** `C` 로 그렸는데 제어점이 엉켜 튀는 것은 이 자가 못 잡는다.
- **60° 언저리는 못 가른다.** 원을 여섯 점으로 그린 육각형은 꼭짓점마다 60° 라 「모서리」로 읽혀
  통째로 빠진다. 점이 아주 적은 곡선은 이 자가 아니라 사람 눈이 잡아야 한다.
- **일부러 꺾은 곡선을 못 가른다** — 박리·충격파처럼 꺾임이 뜻인 자리가 있다. 그래서 **게이트가
  아니라 목록**이고, 넘길 자리는 삽화의 `curveWaiver` 에 사유를 적으면 내려간다.
- **`transform` 을 안 편다.** 회전·축척이 걸린 사슬은 각도가 그대로라 회전에는 안전하지만,
  비등방 축척(`scale(2,1)`)이 걸리면 잰 각이 화면의 각과 다르다.
- **요약·모의고사 장(`ch90` 이상)은 안 본다** — 다른 삽화 자들과 같은 경계다.
"""
import json
import math
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import audit_content                                                    # noqa: E402
import audit_chain_selfsufficiency as chain                             # noqa: E402
import audit_figure_balance as balance                                  # noqa: E402

SUMMARY_CHAPTER_FROM = 90   # 다른 삽화 자들과 같은 경계다(요약·모의고사 장은 안 본다)
MIN_POINTS = 5              # 화살촉(3점)·치수선·삼각형을 빼는 최소치 — 넷은 사각형이라 다섯부터
CURVE_INTENT_DEG = 3.0      # 이보다 작으면 좌표를 소수 한 자리로 적은 데서 오는 반올림이다
CORNER_DEG = 60.0           # 이보다 크게 꺾인 꼭짓점은 곡선의 면이 아니라 모서리다
MIN_SEGMENT = 0.5           # 이보다 짧은 선분은 방향이 잡음이라 사슬을 끊는다
DEFAULT_LIMIT = 1.0         # px — 곡선 두께 2px 의 절반(위 「문턱은 픽셀이다」 절)
WAIVER_KEY = "curveWaiver"

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
POLY = re.compile(r"<(polyline|polygon)\b[^>]*?\spoints\s*=\s*(['\"])(.*?)\2", re.S)
PATH = re.compile(r"<path\b[^>]*?\sd\s*=\s*(['\"])(.*?)\1", re.S)
CMD = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])")


def _nums(text):
    return [float(x) for x in NUM.findall(text)]


def polyline_runs(points_text):
    """`points` 속성 하나를 점 사슬 하나로. 순수 함수."""
    vals = _nums(points_text)
    pts = list(zip(vals[0::2], vals[1::2]))
    return [pts] if len(pts) >= MIN_POINTS else []


def path_runs(d_text):
    """`d` 에서 **직선만으로 이어진** 점 사슬들을 꺼낸다. 순수 함수.

    곡선 명령(`C`·`S`·`Q`·`T`·`A`)을 만나면 사슬을 끊는다 — 거기는 이미 매끄럽다.
    """
    tokens = [t for t in CMD.split(d_text) if t.strip() != ""]
    runs, cur = [], []
    x = y = 0.0
    start = None
    i = 0

    def flush():
        if len(cur) >= MIN_POINTS:
            runs.append(list(cur))
        cur.clear()

    while i < len(tokens):
        cmd = tokens[i]
        if not CMD.fullmatch(cmd):
            i += 1
            continue
        args = _nums(tokens[i + 1]) if i + 1 < len(tokens) and not CMD.fullmatch(tokens[i + 1]) else []
        i += 2 if args else 1
        low = cmd.lower()
        if low == "m":
            flush()
            for k in range(0, len(args) - 1, 2):
                dx, dy = args[k], args[k + 1]
                x, y = (x + dx, y + dy) if cmd.islower() else (dx, dy)
                if k == 0:
                    start = (x, y)
                cur.append((x, y))
        elif low == "l":
            for k in range(0, len(args) - 1, 2):
                dx, dy = args[k], args[k + 1]
                x, y = (x + dx, y + dy) if cmd.islower() else (dx, dy)
                cur.append((x, y))
        elif low == "h":
            for dx in args:
                x = x + dx if cmd.islower() else dx
                cur.append((x, y))
        elif low == "v":
            for dy in args:
                y = y + dy if cmd.islower() else dy
                cur.append((x, y))
        elif low == "z":
            if start:
                x, y = start
            flush()
        else:                                   # C·S·Q·T·A — 여기는 매끄럽다
            flush()
            if args:
                x, y = (x + args[-2], y + args[-1]) if cmd.islower() else (args[-2], args[-1])
    flush()
    return runs


def turn_angles(points):
    """이웃 세 점이 만드는 꺾임각(도)과 그 자리의 선분 길이. 순수 함수."""
    out = []
    for i in range(1, len(points) - 1):
        ax, ay = points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]
        bx, by = points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la < MIN_SEGMENT or lb < MIN_SEGMENT:
            continue
        cos = max(-1.0, min(1.0, (ax * bx + ay * by) / (la * lb)))
        out.append((math.degrees(math.acos(cos)), min(la, lb)))
    return out


def _median(values):
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def curve_pieces(points):
    """모서리(`CORNER_DEG` 초과)에서 끊은 뒤 남는 「곡선을 흉내 낸 조각」들. 순수 함수.

    돌려주는 것은 조각마다 (꺾임각 목록, 점 수).
    """
    angles = turn_angles(points)                # 꼭짓점 i(1..n-2) 의 각. 길이는 n-2 이하다
    pieces, cur = [], []
    for deg, seg in angles:
        if deg > CORNER_DEG:
            pieces.append(cur)
            cur = []
            continue
        cur.append((deg, seg))
    pieces.append(cur)
    return [(p, len(p) + 2) for p in pieces if len(p) + 2 >= MIN_POINTS]


def sagitta(deg, seg):
    """꺾임각과 선분 길이가 만드는 **원호와 현 사이의 벌어짐**(px). 순수 함수."""
    return 0.5 * seg * math.tan(math.radians(deg) / 4.0)


def measure_svg(svg):
    """SVG 한 장에서 조각마다 (볼록 깊이 px, 그 자리 꺾임각, 점 수, 선분 길이). 순수 함수."""
    runs = []
    for _tag, _q, text in POLY.findall(svg):
        runs.extend(polyline_runs(text))
    for _q, text in PATH.findall(svg):
        runs.extend(path_runs(text))
    out = []
    for pts in runs:
        for piece, npts in curve_pieces(pts):
            if _median([d for d, _s in piece]) < CURVE_INTENT_DEG:
                continue                        # 곧은 선이다 — 흉내 낸 곡선이 아니다
            depth, deg, seg = max((sagitta(d, s), d, s) for d, s in piece)
            out.append((depth, deg, npts, seg))
    return out


def main(argv):
    only = None
    limit = DEFAULT_LIMIT
    histogram = "--histogram" in argv
    for a in argv:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        elif a.startswith("--limit="):
            limit = float(a.split("=", 1)[1])

    dirs = audit_content.subject_dirs()
    if audit_content.reject_unmatched_only(only, dirs):
        return 2
    sem = {os.path.basename(d): chain.subject_semester(d) for d in dirs}
    now = chain.current_semester(audit_content.DATA)

    rough, waived, seen, all_worst = [], 0, 0, []
    for d in dirs:
        subject = os.path.basename(d)
        if only and only not in subject:
            continue
        for name in sorted(f for f in os.listdir(d) if re.fullmatch(r"ch\d+\.json", f)):
            if int(name[2:-5]) >= SUMMARY_CHAPTER_FROM:
                continue
            try:
                with open(os.path.join(d, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            for fig in balance.iter_diagrams(data):
                found = measure_svg(fig.get("svg") or "")
                if not found:
                    continue
                seen += 1
                depth, deg, npts, seg = max(found)
                all_worst.append(depth)
                if depth <= limit:
                    continue
                if fig.get(WAIVER_KEY):
                    waived += 1
                    continue
                rough.append((subject, name[:-5], fig.get("id") or "(id 없음)",
                              depth, deg, npts, seg))

    if histogram:
        print("[분포] 곡선 의도가 있는 조각 %d개의 볼록 깊이" % len(all_worst))
        edges = [0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 1e9]
        for lo, hi in zip(edges, edges[1:]):
            n = sum(1 for w in all_worst if lo <= w < hi)
            if n:
                print("   %5.2f ~ %5.2f px  %s %d" % (lo, min(hi, 99), "#" * min(n, 60), n))

    if rough:
        rows = [(s, c, "%s · 깊이 %.2fpx (%.1f° · %d점 · 선분 %.0fpx)" % (i, dep, dg, n, g), 0)
                for s, c, i, dep, dg, n, g in sorted(rough, key=lambda r: -r[3])]
        print("\n[꺾인 곡선] 볼록 깊이가 %.2fpx 를 넘어 눈에 띈다 — **목록이다**" % limit)
        print("   ※ `tools/svg_curve_points.py` 로 점을 촘촘히 다시 찍거나 `C` 로 바꾼다")
        print("   ※ 일부러 꺾은 자리면 그 삽화에 `\"%s\": \"<사유>\"`" % WAIVER_KEY)
        for subject, ch, detail, _z in chain.semester_order(rows, sem, now)[:40]:
            print("   [%s] %s %s · %s"
                  % (chain.semester_tag(sem, subject), subject, ch, detail))
        if len(rows) > 40:
            print("   … 그리고 %d개 더" % (len(rows) - 40))

    print("\n합계 — 곡선 사슬을 가진 삽화 %d장 · 문턱(%.2fpx) 초과 %d장 · 사유로 넘긴 것 %d장"
          % (seen, limit, len(rough), waived))
    print("※ 게이트가 아니다 — 「일부러 꺾은 곡선」을 기계가 못 가른다(규칙 21)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
