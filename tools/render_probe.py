# -*- coding: utf-8 -*-
r"""빌드된 장을 **자족 HTML 한 장**으로 접어 낸다 — 서버 없이 눈으로 보려고 (신설 2026-09-10).

    python tools/render_probe.py "공학수학 2" ch07
    python tools/render_probe.py "공학수학 2" ch07 --out <경로>

★ **왜 열렸나.** AGENTS 삽화 규격이 *[발화 생략]* 라고 못 박는데, 실제로는 막히는 자리가 있다:
  ⑴ 빌드 산출물은 뷰어를 `site/_assets/viewer.<해시>.js|css` 로 **뽑아내 참조**한다
     (AGENTS 「뷰어는 페이지에 안 실린다」 — 30과목 300장이면 중복만 ~42MB 라 옳은 설계다)
  ⑵ 미리보기 창은 로컬 파일을 `data:` 스냅숏으로 연다. 그 문서에서는 **상대 경로 `../_assets/`
     가 풀리지 않아** 뷰어 JS·CSS 가 통째로 안 붙는다. 화면은 뜨는데 `renderMath` 가 없고
     본문이 비어 있다 — 즉 «열리기는 했다» 와 «렌더를 봤다» 가 겉모습이 비슷하다.
  ⑶ 무인 실행(예약 작업)에서는 개발 서버를 띄울 수 없다(승인할 사람이 없다).
  그래서 검수가 조용히 건너뛰어졌다. 이 자는 그 세 조각을 없애고 **파일 하나**로 만든다.

★ **산출물은 스크래치패드로 간다 — `site/` 에 쓰지 않는다.** 절대 규칙 1(빌드 산출물 손편집
  금지)과 부딪히지 않게, 이 자는 `site/` 를 **읽기만** 한다.

★ **이 자는 판정하지 않는다.** 자족 파일을 내놓을 뿐이고, 무엇이 맞는지는 사람이 본다.
  그리고 **원본과 다른 것을 보고 있을 위험**이 남는다 — 인라인하면서 상대 경로가 바뀌므로
  글꼴(`site/fonts/`)은 절대 경로로 바꿔 준다. 그 밖의 차이는 이 도구의 한계로 남는다.
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ASSET_REF = re.compile(r'(?:\.\./)?_assets/(viewer\.[0-9a-f]+\.(?:js|css))')


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def inline(html):
    """`<link>`·`<script src>` 을 자산 내용으로 바꾼다. 못 찾은 참조는 **말하고 남긴다**."""
    missing = []

    def swap(m):
        tag, name = m.group(0), m.group(1)
        path = os.path.join(SITE, "_assets", name)
        if not os.path.isfile(path):
            missing.append(name)
            return tag
        body = read(path)
        if name.endswith(".css"):
            # 글꼴은 `site/fonts/` 상대 경로다 — 자족 파일은 자리가 다르므로 절대 경로로 바꾼다.
            body = body.replace("../fonts/", "file:///" + SITE.replace("\\", "/") + "/fonts/")
            return "<style>" + body + "</style>"
        return "<script>" + body + "</script>"

    out = re.sub(r'<link[^>]*href="(?:\.\./)?_assets/(viewer\.[0-9a-f]+\.css)"[^>]*>',
                 lambda m: swap(m), html)
    out = re.sub(r'<script[^>]*src="(?:\.\./)?_assets/(viewer\.[0-9a-f]+\.js)"[^>]*>\s*</script>',
                 lambda m: swap(m), out)
    return out, missing


def figure_page(subject, chapter, fig_id):
    """삽화 하나만 담은 **JS 없는** HTML. 못 찾으면 `(None, 사유)`.

    ★ **왜 따로 있나 (2026-09-10).** 위 자족 HTML 은 뷰어 JS 가 **돌아야** 카드를 그린다.
      그런데 미리보기 창이 로컬 파일을 `data:` 스냅숏으로 열면 스크립트가 안 돈다 —
      슬라이드 삽화는 카드가 그려질 때 DOM 에 들어가므로 **화면에 아무것도 안 나온다.**
      실측 2026-09-10: `fig-11-principal-slide` 를 그 경로로 보려다 빈 화면만 봤다.
      삽화의 좌표·겹침을 눈으로 재는 데 뷰어는 필요 없으므로, SVG 만 떼어 정적 페이지로 낸다.

    ☐ **이 페이지가 못 보는 것:** 단계별 `show` 동작(전부 보이는 마지막 프레임만 나온다) ·
      뷰어 CSS 가 삽화에 얹는 것 · 카드 안에서의 실제 폭(슬라이드는 586px 안에 들어간다).
    """
    path = os.path.join(ROOT, "data", subject, chapter + ".json")
    if not os.path.isfile(path):
        return None, "그런 장이 없다: " + path
    import json
    with open(path, encoding="utf-8") as fh:
        chap = json.load(fh)
    found = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("id") == fig_id and node.get("svg"):
                found.append(node["svg"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(chap)
    if not found:
        return None, "그 삽화가 이 장에 없다: " + fig_id
    # 폭 586px 은 슬라이드 카드의 안쪽 폭 실측값이다(슬라이드모드 사양 「viewBox 폭은 640」).
    return ("<!doctype html><meta charset='utf-8'><title>" + fig_id + "</title>"
            "<body style='margin:0;background:#f1f3ee;font:14px system-ui'>"
            "<div style='width:586px;margin:24px auto;padding:14px;background:#fff'>"
            + found[0] + "</div></body>"), None


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("subject", help="과목 폴더 이름 (site/ 아래 그대로)")
    ap.add_argument("chapter", help="chNN")
    ap.add_argument("--out", default=None, help="낼 자리 (기본: 스크래치패드 또는 그 옆)")
    ap.add_argument("--figure", default=None,
                    help="이 삽화 하나만 JS 없이 낸다 (슬라이드 삽화를 눈으로 볼 때)")
    args = ap.parse_args()

    if args.figure:
        page, why = figure_page(args.subject, args.chapter, args.figure)
        if page is None:
            sys.exit(why)
        out = args.out or os.path.join(
            os.environ.get("CLAUDE_SCRATCHPAD") or os.environ.get("TEMP") or ROOT,
            args.figure + ".fig.html")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(page)
        print("삽화 한 장(JS 없음): " + out)
        print("  ☐ 단계별 show 동작은 이 페이지가 못 본다 — 마지막 프레임만 보인다")
        return 0

    src = os.path.join(SITE, args.subject, args.chapter + ".html")
    if not os.path.isfile(src):
        sys.exit("그런 장이 없다: " + src + "\n   ※ 먼저 `python tools/build_site.py` 를 돌릴 것")
    html, missing = inline(read(src))
    left = ASSET_REF.findall(html)
    out = args.out or os.path.join(
        os.environ.get("CLAUDE_SCRATCHPAD") or os.environ.get("TEMP") or ROOT,
        args.subject.replace(" ", "_") + "-" + args.chapter + ".probe.html")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("자족 HTML: " + out)
    if missing or left:
        # 조용히 반쪽짜리를 내지 않는다 — 「열렸다」와 「렌더를 봤다」가 갈리는 자리가 여기다.
        print("  ★ [미인라인] 아직 바깥을 가리키는 참조가 있다: "
              + ", ".join(sorted(set(missing) | set(left)))
              + "\n     그대로 열면 그 조각은 **안 붙은 채** 보인다 — 검수 근거로 쓰지 말 것")
        return 1
    print("  바깥 참조 0건 — 이 파일만으로 뷰어가 돈다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
