# 하이라이트 켠 빌드 래퍼 + 주입 결과 자가 확인.
# 왜 래퍼인가: `REVIEW_HIGHLIGHTS=1 python ...` 처럼 환경변수 접두어를 붙이면 allow 규칙에
# 안 걸려 승인 프롬프트가 뜬다. 또 `... | grep | wc` 같은 복합 명령도 매칭이 깨진다.
# → env 세팅과 확인 출력을 전부 이 스크립트 안에서 처리하고, 호출은 한 줄로 단순하게.
# 사용: python tools/build_review.py [--all]
#   ※ 기준선(.review-snapshot)은 건드리지 않는다 — --accept-review* 는 거부한다.
#
# 위치 주의: 이 파일은 리포에 커밋되는 고정 도구다(2026-07-20 tools/scratch/ 에서 승격).
# 실행은 무승인이지만 이 파일 자체의 수정은 승인 대상이다(.claude/settings.json ask 목록).
# 그래야 "도구를 먼저 고친 뒤 무승인 실행"이라는 우회가 막힌다.
import os, sys, runpy, re

# reconfigure를 쓸 것 — TextIOWrapper 재감싸기는 build_site.py를 runpy로 부를 때
# 이중 래핑이 되어 buffer가 닫힌다(2026-07-20 실제 발생). 자세한 설명은 build_site.py 상단.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
os.environ["REVIEW_HIGHLIGHTS"] = "1"

args = sys.argv[1:] or ["--all"]
# ★★ **접두로 본다 — 정확 일치로 두면 새 플래그가 그대로 통과한다** (고침 2026-08-13).
#   열린 날: 같은 날 기준선 장치를 넓히며 `--accept-review-as-built`·`--accept-review-user-saw=`
#   가 생겼는데, 이 목록이 두 이름을 **정확 일치**로만 보고 있어 셋 다(그리고 전부터 있던
#   `--accept-review-rev=`·`--accept-review-only=`) 조용히 지나갔다. 이 래퍼의 존재 이유가
#   *"검수 전에는 기준선을 안 건드린다"* 인데 **이름이 하나 늘 때마다 구멍이 생기는 구조**였다.
#   → 접두로 보면 앞으로 무슨 이름이 붙어도 자동으로 막힌다. **열거는 빠뜨려도 통과되고,
#     접두는 빠뜨릴 것이 없다** — 이 리포가 오늘 텍스트 분수에서 겪은 것과 같은 부류다.
for arg in args:
    if arg.startswith("--accept-review"):
        sys.exit(f"거부: {arg} 는 기준선을 옮긴다. 검수 전에는 쓰지 말 것"
                 " (밀어야 하면 tools/build_site.py 를 직접 쓴다 — 거기에는 삼킴 게이트가 있다).")

sys.argv = ["tools/build_site.py"] + args
try:
    runpy.run_path("tools/build_site.py", run_name="__main__")
except SystemExit as e:
    if e.code:
        raise

print("\n=== 하이라이트 주입 확인 ===")
# 과목 하드코딩 금지(2026-07-27: 열역학 고정이라 math 브랜치에서 확인 루프가 통째로 침묵했다).
# data/<과목>/ 를 스캔해 존재하는 산출물만 센다.
import glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from buildlib.review import (marks_from_built_html, visible_collections,   # noqa: E402
                             stale_acceptances)

# ★ **합계만 찍지 않는다** (2026-08-07, 재발 지적으로 열림).
#   예전 출력은 `본문변경 22` 뿐이라, 그 22 안에 **이미 수락한 이론 10절**이 들어 있다는 것이
#   화면에 안 보였다. 그래서 전 세션이 그 상태를 *"정상"* 이라고 판단해 넘겼고, 사용자가
#   *"확인했다고 했는데도 안 옮겨놨더라"* 로 다시 지적했다. **합계는 컬렉션을 감춘다.**
for p in sorted(glob.glob("site/*/ch*.html")):
    if p.replace("\\", "/").startswith("site/template/"):
        continue
    h = open(p, encoding="utf-8").read()
    # 클래스명·JS 변수명까지 세면 기준선 직후에도 가짜 변경이 남는다.
    # 주입된 CH JSON의 실제 마커만 정확히 센다.
    changed = len(re.findall(r'"_changed": \[', h))
    diagrams = len(re.findall(r'"_reviewChanged": true', h))
    print(f"  {p}: 본문변경 {changed} · 삽화배지 {diagrams}")
    ch_path = os.path.join("data", p.replace("\\", "/").split("/")[1],
                           os.path.splitext(os.path.basename(p))[0] + ".json")
    chapter, marks = marks_from_built_html(p)
    if chapter is None or not any(marks.values()):
        continue
    # ★ 숨긴 탭은 **여기 올 수 없다** — `add_review_changes` 가 표시를 아예 안 만든다.
    #   한때 `(숨긴 탭 — 화면에 안 보인다)` 라는 꼬리표를 달아 출력했는데, 그것이
    #   *"안 본다고 한 것을 보라"* 는 뜻이 되어 사용자 재지적을 받았다(4회차). 라벨로는 못 막는다.
    #   그래도 방어적으로 확인해 둔다 — 판정이 갈리면 조용히 새는 것이 이 부류의 습성이다.
    shown = set(visible_collections(chapter))
    for name in ("theory", "derivation", "practice", "problems"):
        ids = marks.get(name) or []
        if ids and name in shown:
            print(f"      - {name}: {len(ids)}건  "
                  + ", ".join(ids[:6]) + (" …" if len(ids) > 6 else ""))
        elif ids:
            print(f"      ! {name}: 숨긴 탭에 표시가 생겼다 — add_review_changes 와 판정이 갈렸다")
    for name, left, at in stale_acceptances(ch_path, chapter, marks):
        print(f"    ★ {name}: {at} 에 수락해 놓고 {len(left)}건이 남아 있다 — 다시 밀 것")

snaps = sorted(glob.glob("data/*/.review-snapshot/ch*.json"))
print("\n기준선 스냅샷: " + (", ".join(snaps) if snaps else "없음") + "  (git과 무관 — 커밋해도 유지)")
