# -*- coding: utf-8 -*-
"""Render selected JSON-embedded SVG figures to PNG for visual review.

Usage:
    python tools/render_figure_review.py data/열역학/ch02.json --id fig-card-cycle-energy
    python tools/render_figure_review.py data/열역학/ch05.json --changed-since <sha>

PNG proof is written only below review-artifacts/figure-review/.  This avoids a
localhost/browser dependency: inspect the resulting image with view_image.

`--changed-since` 를 만든 이유 (열린 날 2026-07-29):
    일괄 수정 도구(`tools/fix_figure_text_scale.py`)는 **한 번에 삽화 55개**를 바꾸는데
    검수 경로는 `--id` 하나씩뿐이었다. 변경량과 검수 단위가 맞지 않으면 검수는
    **원리적으로** 따라잡지 못한다 — 실제로 4회차 일괄 확대분이 통째로 미검수로 남아
    `verify_workorder.py` 가 86건을 토했다. "빠뜨렸다"가 아니라 구조가 원인이었다.
    그래서 기준 커밋과 대조해 **바뀐 삽화만 한꺼번에** 렌더하는 길을 연다.
"""
import argparse
import hashlib
import http.server
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import fitz

# 한글이 든 도움말·경로를 찍는다. Windows 기본 cp949로는 '—' 하나에도 죽는다
# (실측 2026-07-29: `--help` 가 UnicodeEncodeError). io.TextIOWrapper 로 감싸면
# build_review.py 의 runpy 이중 래핑 사고가 나므로 reconfigure 를 쓴다(AGENTS 「알려진 함정」).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
AUDIT_ROOT = ROOT / "review-artifacts" / "figure-review"

_TEXT_TAG_RE = re.compile(r"<text\b[^>]*>")
_STROKE_ATTR_RE = re.compile(r"""\s+stroke(?:-width)?\s*=\s*(['"])[^'"]*\1""")
_PAINT_ORDER_RE = re.compile(r"""\s+paint-order\s*=\s*(['"])[^'"]*\1""")


def strip_review_halo(svg):
    """halo(paint-order:stroke)를 걷어낸 SVG를 돌려준다 — 래스터 검수 전용.

    왜 필요한가 (열린 날 2026-07-26, ch02 재검수): fitz는 `paint-order='stroke'`를 지키지 않아
    흰 스트로크(width 3)가 12px 글자를 통째로 덮는다. 그 결과 PNG에서 halo 라벨이 **흰 뭉치도
    아니고 아예 사라진다.** AGENTS는 이 아티팩트를 '흰 뭉치'로만 적어 두었는데, 실제 증상이
    완전 소실이라 검수자는 **라벨을 처음부터 안 그린 것으로 오진한다** — ch02 t축 눈금 숫자
    1·2·3·4 / 2·4·6이 실제로 그렇게 보였다.

    halo를 벗기면 글자가 보이고, 밑을 지나는 선도 함께 보인다. 검수 목적에는 그쪽이 더 낫다 —
    halo가 가리고 있던 겹침을 눈으로 확인할 수 있기 때문이다. 화면(브라우저)은 paint-order를
    지키므로 데이터는 그대로 두고 **검수 래스터에서만** 벗긴다.
    """
    def scrub(match):
        tag = match.group(0)
        if "paint-order" not in tag:
            return tag
        return _PAINT_ORDER_RE.sub("", _STROKE_ATTR_RE.sub("", tag))

    return _TEXT_TAG_RE.sub(scrub, svg)


def iter_diagrams(node):
    # ★ `diagrams` 만 훑던 자리다(2026-08-23). 유도 카드의 **슬라이드는 `figure` 한 개**로
    #   사는데 그것을 안 봐서, 브라우저 캡처가 막혔을 때 쓰라고 만든 이 PNG 경로가
    #   정작 «새로 그려서 눈으로 봐야 하는 것» 을 통째로 못 냈다. 같은 날 카드 10장에서
    #   `diagrams` 를 걷어내 슬라이드가 유일한 그림이 되면서 사각지대가 카드 전체로 커졌다.
    #   ★ 동역학도 같은 날 같은 자리에서 걸렸다 — 두 과목이 따로 고쳐 여기서 만났다.
    if isinstance(node, dict):
        # 풀이 접기 안에만 그리는 답 도해도 독자가 실제로 보는 SVG다. 지문 그림과
        # 분리했다는 이유로 PNG 검수 경로에서 빠지면 작은 글자·잘린 라벨이 조용히 남는다.
        pools = [node.get("diagrams"), node.get("solutionDiagrams"), [node.get("figure")]]
        for pool in pools:
            if isinstance(pool, list):
                for diagram in pool:
                    if isinstance(diagram, dict) and diagram.get("id") and diagram.get("svg"):
                        yield diagram
        for value in node.values():
            yield from iter_diagrams(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_diagrams(value)


# ★★ **왜 엔진이 둘인가** (열린 날 2026-08-12, 사용자 지적: *[발화 생략]*).
#
#   맞는 지적이다 — 그라데이션은 SVG 의 기본 기능이고 **브라우저는 정상으로 그린다.**
#   못 그리는 것은 이 파일이 쓰던 **래스터라이저(fitz/PyMuPDF)** 하나뿐이다. 실측
#   (2026-08-12, `fig-quasi-nonequilibrium-pistons`): 평면 채움인 왼쪽 피스톤은 멀쩡한데
#   `linearGradient` 를 쓴 오른쪽 피스톤이 **통째로 검은 사각형**으로 나온다.
#
#   ★ 이게 왜 중요한가 — **검수 경로의 한계가 데이터 규격을 좁히고 있었다.** 삽화 시각 문법
#     초안이 *[발화 생략]* 라고 적었는데, 그건 그림을
#     도구에 맞추는 것이다. 도구를 고치면 그 제약 자체가 사라진다.
#
#   그래서 **설치된 브라우저(Edge·Chrome)를 헤드리스로** 돌려 찍는 길을 기본으로 둔다.
#   내려받는 것이 없고(Windows 11 에 Edge 가 기본 탑재), 무엇보다 **독자가 보는 그 렌더러**라
#   fitz 가 못 보던 세 가지가 한꺼번에 사라진다: 그라데이션 · `paint-order` halo ·
#   `tspan dy` 첨자. 브라우저가 없는 환경에서는 fitz 로 자동 폴백한다(경로가 끊기지 않는다).
_BROWSERS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
)
# 뷰어가 삽화를 그리는 폭. 화면 실효 크기(AGENTS 「글자 크기 위계」)를 재는 그 분모와 같은 값이라,
# 이 폭으로 찍어야 PNG 가 독자 화면과 같은 배율이 된다.
VIEWER_FIGURE_WIDTH = 612
_VIEWBOX_RE = re.compile(r"""viewBox\s*=\s*(['"])\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\1""")


def find_browser():
    """설치된 헤드리스 브라우저 경로. 없으면 None. 순수 함수 — 테스트가 직접 부른다."""
    for candidate in _BROWSERS:
        if Path(candidate).exists():
            return candidate
    return None


def viewbox_size(svg):
    """(폭, 높이) — viewBox 가 없으면 (None, None). 순수 함수."""
    match = _VIEWBOX_RE.search(svg or "")
    if not match:
        return None, None
    return float(match.group(4)), float(match.group(5))


# ★★ **뷰어와 같은 글꼴 스택을 준다** (열린 날 2026-08-12).
#   안 주면 시스템 기본 글꼴로 그려져 **글자 폭이 화면과 달라진다** — 캡션이 잘리는지 아닌지를
#   이 PNG 로 판정하는데, 폭이 다르면 그 판정이 통째로 무의미하다(실제로 한 번 헛짚었다).
#   값은 `site/template/viewer.template.html` 의 body 스택을 그대로 옮긴 것이다.
VIEWER_FONT_STACK = ("Pretendard, 'Apple SD Gothic Neo', 'Malgun Gothic', 'Noto Sans KR',"
                     " -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif")


def review_page(svg):
    """검수용 HTML 한 장. 뷰어와 **같은 폭·같은 글꼴**에 얹어 화면과 맞춘다. 순수 함수."""
    return ("<!doctype html><meta charset='utf-8'>"
            "<style>html,body{margin:0;padding:0;background:#fff;font-family:%s}"
            "svg{display:block;width:%dpx;height:auto;font-family:inherit}</style>"
            "<body>%s</body>" % (VIEWER_FONT_STACK, VIEWER_FIGURE_WIDTH, svg))


def serve_page(html):
    """그 페이지 하나만 내주는 임시 로컬 서버. (서버, URL). 부른 쪽이 `shutdown()` 한다.

    ★★ **왜 파일이 아니라 서버인가 — 리포 경로에 한글이 있기 때문이다** (실측 2026-08-12).
      `file:///…/전공정리프로젝트/…` 를 인자로 주면 Edge 가 **`ERR_FILE_NOT_FOUND` 안내
      페이지를 찍는다**(URI 인코딩·전용 프로필·평문 경로 세 형태를 다 시도했고 셋 다 같았다).
      같은 HTML 을 ASCII 경로에 두면 정상으로 찍히므로 원인은 경로의 한글이다.
      ★ 그렇다고 임시 파일을 리포 **밖**에 쓸 수는 없다(AGENTS 규칙 9 — 쓰기는 리포 안과
        스크래치패드뿐이고, 스크래치패드는 세션마다 달라 공통 도구가 기댈 자리가 아니다).
      메모리에서 내주면 **파일을 아예 안 만들고** 경로 문제도 사라진다 — 127.0.0.1 의
      임시 포트라 바깥으로 열리지도 않는다.
    """
    body = html.encode("utf-8")
    served = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):                                    # noqa: N802
            served.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):                        # 콘솔을 더럽히지 않는다
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.served = served
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, "http://127.0.0.1:%d/figure.html" % server.server_address[1]


def wait_for_png(path, timeout=45.0, settle=0.4):
    """PNG 가 생겨 **크기가 멎을 때까지** 기다렸다가 바이트를 준다. 못 받으면 None.

    브라우저가 쓰는 도중에 읽으면 잘린 파일을 증거로 삼게 된다 — 크기가 두 번 같을 때만 읽는다.
    """
    deadline, last = time.time() + timeout, -1
    while time.time() < deadline:
        if path.exists():
            size = path.stat().st_size
            if size and size == last:
                return path.read_bytes()
            last = size
        time.sleep(settle)
    return None


def svg_png_browser(svg, exe, work_dir, name, scale=2):
    """설치된 브라우저로 PNG. 실패하면 None(부르는 쪽이 fitz 로 폴백한다).

    ★ **halo 를 벗기지 않는다** — 그건 fitz 가 `paint-order` 를 안 지켜서 넣은 우회이고,
      브라우저는 지킨다. 벗기면 오히려 화면과 다른 그림을 검수하게 된다.
    """
    width, height = viewbox_size(svg)
    if not width or not height:
        return None
    page_height = max(1, round(VIEWER_FIGURE_WIDTH * height / width))
    shot = (work_dir / (name + ".png")).resolve()
    # ★ **먼저 지운다.** 안 지우면 브라우저가 안 찍어도 *지난번 PNG* 가 남아 있어
    #   `shot.exists()` 가 참이 되고, 낡은 그림을 새 증거로 읽는다(실측 2026-08-12 —
    #   실패 진단이 세 번 헛돌았다. 검수 도구가 조용히 옛 그림을 보여 주는 것이 가장 나쁘다).
    shot.unlink(missing_ok=True)
    server, url = serve_page(review_page(svg))
    try:
        # ★ `--user-data-dir` 가 없으면 **이미 떠 있는 Edge 에 위임**되어 빈 창이 찍힐 수 있다.
        #   `--virtual-time-budget` 는 폰트·레이아웃이 끝나기 전에 찍는 것을 막는다.
        # ★★ **exit code 를 믿으면 안 된다** (실측 2026-08-12 — 여기서 세 번 헛짚었다).
        #   Edge 는 **부모 프로세스가 곧바로 0 으로 돌아가고** 진짜 렌더는 뒤이어 뜬 자식이 한다.
        #   그래서 `subprocess.run` 이 끝난 시점에는 요청이 **한 건도 안 들어와 있고**
        #   (진단 출력 `요청 []`), 그 자리에서 서버를 닫으면 자식이 페이지를 못 받는다.
        #   → **끝났는지는 산출물로 판정한다.** 파일이 생기고 크기가 멎을 때까지 기다린다.
        #   ※ `--user-data-dir` 는 주지 않는다 — 리포 안은 경로에 한글이 섞여 Edge 가 죽고,
        #     리포 밖은 쓰기가 금지다(AGENTS 규칙 9).
        subprocess.run(
            [exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--no-first-run", "--no-default-browser-check",
             "--virtual-time-budget=3000",
             "--force-device-scale-factor=" + str(scale),
             "--window-size=%d,%d" % (VIEWER_FIGURE_WIDTH, page_height),
             "--screenshot=" + str(shot), url],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        data = wait_for_png(shot)
    except (OSError, subprocess.SubprocessError) as exc:
        print("[browser 폴백] " + type(exc).__name__)
        return None
    finally:
        server.shutdown()
        server.server_close()
    if not data:
        # 조용히 폴백하면 *왜* 브라우저를 못 썼는지 다음 세션이 또 캐게 된다.
        print("[browser 폴백] 요청 %s · %s" % (server.served, url))
        return None
    return data


def svg_png(svg, scale=2):
    """fitz 폴백 — 브라우저가 없을 때만 쓴다. halo 를 벗겨야 글자가 보인다(위 주석)."""
    svg = strip_review_halo(svg)
    doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def changed_since(chapter_path, sha):
    """기준 `sha` 이후 svg가 바뀐(또는 새로 생긴) 삽화 id를 챕터 등장 순서로 돌려준다.

    읽기 전용 `git show` 만 쓴다 — push·reset·checkout 같은 게이트 대상 명령은 부르지 않는다
    (회귀 `test_checks.py::test_tools_do_not_bypass_git_gates` 가 이 경계를 잠근다).
    바깥에서 들어오는 텍스트이므로 encoding 을 반드시 명시한다(Windows 기본 cp949면 한글이 깨진다).
    """
    relative = Path(chapter_path).resolve().relative_to(ROOT).as_posix()
    proc = subprocess.run(["git", "-C", str(ROOT), "show", sha + ":" + relative],
                          capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise ValueError("기준 커밋에서 " + relative + " 를 읽을 수 없다: " + proc.stderr.strip())
    before = {figure["id"]: figure["svg"] for figure in iter_diagrams(json.loads(proc.stdout))}
    now = json.loads(Path(chapter_path).read_text(encoding="utf-8"))
    return [figure["id"] for figure in iter_diagrams(now)
            if before.get(figure["id"]) != figure["svg"]]


def render(chapter_path, ids, output_root=AUDIT_ROOT, engine="auto"):
    from figure_proof import proof_directory, source_key
    chapter_path = Path(chapter_path)
    data = json.loads(chapter_path.read_text(encoding="utf-8"))
    figures = {figure["id"]: figure for figure in iter_diagrams(data)}
    missing = sorted(set(ids) - figures.keys())
    if missing:
        raise ValueError("unknown diagram id: " + ", ".join(missing))

    destination = proof_directory(chapter_path, ROOT, output_root)
    destination.mkdir(parents=True, exist_ok=True)
    exe = None if engine == "fitz" else find_browser()
    outputs, engines = [], set()
    for figure_id in ids:
        output = destination / f"{figure_id}.png"
        svg = figures[figure_id]["svg"]
        png = svg_png_browser(svg, exe, destination, figure_id) if exe else None
        used = "browser"
        if png is None:
            png, used = svg_png(svg), "fitz"
        output.write_bytes(png)          # 엔진이 무엇이든 **쓰는 자리는 하나**로 둔다
        engines.add(used)
        # ★ **어느 엔진으로 찍었는지 증거에 남긴다.** fitz 는 그라데이션·halo·첨자를 못 그리므로
        #   *[발화 생략]* 가 데이터 결함인지 아티팩트인지 갈리는데, 남기지 않으면 다음 세션이
        #   PNG 만 보고 판정한다(2026-07-25 에 실제로 반려할 뻔했다).
        (destination / f"{figure_id}.json").write_text(json.dumps({
            "figure_id": figure_id,
            "source": source_key(chapter_path, ROOT),
            "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
            "png_sha256": hashlib.sha256(png).hexdigest(),
            "png": output.name,
            "engine": used,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(output)
    if engines:
        print("[렌더 엔진] " + " · ".join(sorted(engines))
              + ("" if "fitz" not in engines else
                 "  ← fitz 는 그라데이션·halo·첨자를 못 그린다(아티팩트 주의)"))
    return outputs


def main():
    parser = argparse.ArgumentParser(description="Render selected SVG figures to local PNG proof.")
    parser.add_argument("chapter", help="chapter JSON path, relative to repository root")
    parser.add_argument("--id", dest="ids", action="append",
                        help="diagram id to render; repeat for multiple figures")
    parser.add_argument("--changed-since", dest="since", metavar="SHA",
                        help="render every figure whose svg differs from that commit "
                             "(일괄 수정 뒤 검수용 — --id 와 함께 쓰면 합집합)")
    parser.add_argument("--engine", choices=("auto", "fitz"), default="auto",
                        help="auto = 설치된 브라우저(그라데이션·halo·첨자까지 화면 그대로), "
                             "fitz = 옛 래스터라이저. 기본은 auto 이고 브라우저가 없으면 폴백한다")
    args = parser.parse_args()
    if not args.ids and not args.since:
        parser.error("--id 나 --changed-since 중 하나는 있어야 한다")
    chapter = ROOT / args.chapter
    try:
        ids = list(args.ids or [])
        if args.since:
            for figure_id in changed_since(chapter, args.since):
                if figure_id not in ids:
                    ids.append(figure_id)
            if not ids:
                print("[ok] 기준 이후 바뀐 삽화 없음 — " + args.chapter)
                return 0
        outputs = render(chapter, ids, engine=args.engine)
    except (OSError, ValueError, fitz.FileDataError) as exc:
        print(f"[FAIL] {exc}")
        return 1
    for output in outputs:
        print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
