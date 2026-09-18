r"""엑서지 기호 매크로를 `\mathfrak{E}` → `\mathsf{E}` 로 바꾼다 (열린 날 2026-09-08).

**왜 열렸나 — 「고딕」을 잘못 읽었다.**
2026-09-03 사용자 지시는 *[발화 생략]*
였다. 한국어 조판에서 **「고딕」은 산세리프**인데 블랙레터(프락투어, `\mathfrak` → 𝔈)로
구현했다. 2026-09-08 사용자 지적으로 교재를 열어 확인했다:

  `python tools/extract_textbook.py --pdf 8th_Moran --pages 334 --render`

그 쪽(교재 p.312) 식 (7.1)의 엑서지 `E` 는 **업라이트 산세리프**이고 옆의 `U`·`V`·`S` 는
세리프 이탤릭이다. TAKE NOTE 상자도 *"E and e are used for exergy … while E and e denote
energy"* 로 **글자꼴 차이**만 말한다. 프락투어는 교재 어디에도 없다.

**왜 매크로 이름까지 바꾸나.** `\mathfrak` 는 LaTeX 에서 **「블랙레터」라는 뜻**이라, 이름을
두면 다음 저자가 그 뜻대로 읽는다. 화면만 고치고 이름을 두는 것은 거짓말을 남기는 것이다.

**사람이 판정하는 자리:** 없다 — 치환이 기계적이다. 다만 **렌더는 사람이 본다**
(등폭 수식 옆에서 산세리프 굵은 E 가 실제로 갈리는가는 화면으로만 판정된다).

    python tools/fix_exergy_symbol.py            # 훑기만 한다
    python tools/fix_exergy_symbol.py --apply    # 고친다
"""

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OLD = r"\\mathfrak{E}"          # JSON 안에서는 백슬래시가 두 번 적힌다
NEW = r"\\mathsf{E}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="실제로 고친다")
    args = parser.parse_args()

    total = 0
    touched = []
    for path in sorted(ROOT.joinpath("data").rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        count = text.count(OLD)
        if not count:
            continue
        total += count
        touched.append((path, count))
        if args.apply:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8")

    if not touched:
        print("[해당 없음] `\\mathfrak{E}` 0건 — 고칠 것이 없다")
        return 0

    for path, count in touched:
        print(f"  {path.relative_to(ROOT)} — {count}건")
    print(f"합계 {total}건" + ("" if args.apply else " (훑기만 했다 — 고치려면 --apply)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
