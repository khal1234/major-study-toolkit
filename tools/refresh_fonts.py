# -*- coding: utf-8 -*-
"""웹폰트 부분집합을 **한 명령으로** 다시 만든다 (신설 2026-08-24).

★ **왜 열렸나.** `site/fonts/README.md` 의 절차는 옳지만 손이 여섯 번 간다 — `curl` 로 원본
  넷을 받고(`curl` 은 settings 의 `ask` 라 **받을 때마다 승인창**) `font_subset build` 를 네 번
  친다. 그런데 이 절차의 트리거는 «새 낱말이 들어왔다» 라 **콘텐츠를 쓸 때마다** 걸린다
  (실측 2026-08-24: 유체역학 ch02 를 쓰자 「챌챔혈」 3자가 빠져 회귀가 빨간불이 됐다).
  사용자 지시는 *"루프 돌리던가 하고 1회 허용 안뜨게 해"* 이고, 실행 규율 7 은 반복되는
  승인 프롬프트를 **기계로** 고치라고 한다 — `python tools/*.py` 는 이미 자동 허용이다.

★ **낱말을 바꿔 피하지 않는다.** 「글자가 없으니 다른 말로 쓰자」는 부분집합이 콘텐츠를
  지배하게 두는 것이다. 새 글자가 생기면 **그 자리에서 뽑는다** — 그것이 이 도구의 존재 이유다.

★ **원본은 리포에 두지 않는다**(수 MB 짜리 넷이다). 받는 자리는 **스크래치패드**이고
  `--out` 으로 명시해야 한다(AGENTS 규칙 9 — 쓰기는 리포와 스크래치패드뿐).

주소·이름·굵기는 `site/fonts/README.md` 가 정본이다. 여기 표와 그 문서가 갈리면
`test_checks.py::test_font_refresh_matches_readme` 가 잡는다.

    python tools/refresh_fonts.py --out <스크래치패드>
    python tools/refresh_fonts.py --out <스크래치패드> --keep   # 받은 원본을 지우지 않는다
"""

import argparse
import os
import runpy
import shutil
import subprocess
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 예의 — 사람이 아니라 도구가 받는다는 것을 밝힌다(공용 「규칙/web-fetch」).
UA = "jeongri-font-refresh/1 (repo tooling; contact via project owner)"

PRE = ("https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9"
       "/packages/pretendard/dist/public/static/")
NANUM = ("https://raw.githubusercontent.com/google/fonts/main/ofl/nanummyeongjo/")

# (파일명, 주소, 새 이름, 굵기) — README 의 「그다음 네 얼굴을 뽑는다」 와 같은 넷이다.
FACES = [
    ("Pretendard-Regular.otf", PRE + "Pretendard-Regular.otf", "Jeongri Sans", "Regular"),
    ("Pretendard-SemiBold.otf", PRE + "Pretendard-SemiBold.otf", "Jeongri Sans", "SemiBold"),
    ("Pretendard-Bold.otf", PRE + "Pretendard-Bold.otf", "Jeongri Sans", "Bold"),
    ("NanumMyeongjo-Bold.ttf", NANUM + "NanumMyeongjo-Bold.ttf", "Jeongri Serif", "Bold"),
]


def fetch(url, dest):
    """원본 하나를 내려받는다. 이미 있으면 다시 받지 않는다(같은 태그의 고정 주소다)."""
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        print("[있음] " + os.path.basename(dest))
        return True
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as res, open(dest, "wb") as fh:
            shutil.copyfileobj(res, fh)
    except Exception as exc:                     # 네트워크는 막힐 수 있다 — 사유를 그대로 낸다
        print("[실패] " + os.path.basename(dest) + " — " + str(exc))
        return False
    print("[받음] %s (%d KB)" % (os.path.basename(dest), os.path.getsize(dest) // 1024))
    return True


def build_one(src, name, style):
    """`font_subset build` 를 그대로 부른다 — 부분집합 판정을 두 벌로 두지 않는다."""
    tool = os.path.join(ROOT, "tools", "font_subset.py")
    # ★ `--이름=값` 형태로만 준다 — `font_subset.cmd_build` 의 `arg()` 는 `startswith(name + "=")`
    #   로 읽으므로 띄어쓴 형태는 **조용히 None 이 되어** 「인자가 필요하다」로 죽는다(실측).
    r = subprocess.run([sys.executable, tool, "build", "--src=" + src,
                        "--as=" + name, "--style=" + style, "--all-subjects"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        sys.stdout.write(r.stderr or "")
    return r.returncode == 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True,
                    help="원본을 받을 자리. **스크래치패드**여야 한다(리포에 두지 않는다)")
    ap.add_argument("--keep", action="store_true", help="받은 원본을 지우지 않는다")
    args = ap.parse_args(argv)

    out = os.path.abspath(args.out)
    if os.path.abspath(ROOT) in out or out.startswith(os.path.abspath(ROOT)):
        sys.exit("거부 — 원본을 리포 안에 두지 않는다(수 MB 짜리 넷이다). 스크래치패드를 줄 것.")
    os.makedirs(out, exist_ok=True)

    made, failed = 0, []
    for fname, url, name, style in FACES:
        dest = os.path.join(out, fname)
        if not fetch(url, dest):
            failed.append(fname)
            continue
        if build_one(dest, name, style):
            made += 1
        else:
            failed.append(fname)
        if not args.keep:
            try:
                os.remove(dest)
            except OSError:
                pass

    print("\n[부분집합] %d/%d 얼굴을 다시 만들었다." % (made, len(FACES)))
    if failed:
        print("[남음] " + ", ".join(failed) + " — 주소가 살아 있는지 README 로 확인할 것")
        return 1
    print("확인: 빌드를 다시 돌려 「없는 글자」 경고가 사라졌는지 본다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
