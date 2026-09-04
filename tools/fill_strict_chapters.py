# -*- coding: utf-8 -*-
"""새 챕터를 **모든 strict 목록**에 한 번에 올린다 (신설 2026-08-24).

★ **왜 열렸나.** 승격 목록의 판정은 「공통 상수의 파일 이름 목록 ∪ 그 과목이 선언한 것」이다.
  그래서 새 과목의 ch00·ch01 은 **원조 과목의 파일 이름과 우연히 겹쳐** 선언 없이도 통과한다 —
  선언이 빠진 것이 안 보인다. 그러다 겹치지 않는 번호가 생기는 순간 한꺼번에 드러난다.
  실측 2026-08-24: 유체역학 ch03 에서 `middot` 하나, 응용열역학 ch08 에서 **아홉 키**가
  같은 날 연달아 걸렸다(둘 다 회귀가 잡았고, 둘 다 손으로 키를 찾아 적었다).

★ **부류로 고친다.** 남은 2-2 과목 다섯이 각각 네 챕터를 여는데, 그때마다 같은 세 걸음
  (빌드 → 회귀 실패 → 키 찾아 적기)을 반복할 이유가 없다. **목록은 코드가 알고 있다** —
  `buildlib.checks_content` 의 `*_STRICT_CHAPTERS` 상수가 그 정본이다.

★ **완화가 아니다.** 이 도구는 승격을 **넓히기만** 한다 — 이미 있는 키를 지우거나 챕터를
  빼지 않는다. 승격은 「검사를 error 로 켠다」는 뜻이라, 빠짐없이 켜는 쪽이 언제나 엄한 쪽이다.
  보류(`pendingChapters`)와 면제(`strictWaivers`)는 건드리지 않는다 — 그건 사람의 판정이다.

    python tools/fill_strict_chapters.py            # 무엇이 빠졌는지만 본다
    python tools/fill_strict_chapters.py --apply    # index.json 에 채운다
"""

import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def optin_keys(root=None):
    """`docs/검사-기본값-기준선.txt` 의 **옛 키**(선언해야 켜지는 것들).

    ★ 왜 필요한가 — 이 키들은 공통 상수를 갖지 않는다. `is_strict_chapter(ch_path, (), "키")`
      형태라 **과목 선언 말고는 켤 방법이 없고**, 그래서 새 과목의 index 에는 통째로 빠진다
      (실측 2026-08-24: 기계공작법 첫 챕터에 상수 키 13개만 들어가고 `tone`·`term_pairing`·
      `theory_figures` 같은 옛 키는 하나도 안 들어갔다 — 경고로만 뜨고 빌드는 통과한다).
      그 파일이 그 목록의 정본이므로 여기서 읽는다(목록을 도구에 적지 않는다).
    """
    path = os.path.join(root or ROOT, "docs", "검사-기본값-기준선.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []                     # 못 읽으면 상수 키만 — 넓히기 도구라 조용히 좁아진다
    return sorted({ln.strip() for ln in lines
                   if ln.strip() and not ln.lstrip().startswith("#")})


def strict_keys():
    """공통 코드가 아는 승격 키 전부. **목록을 여기 적지 않는다.**

    ★ 한 모듈만 보면 안 된다 — `MIDDOT_STRICT_CHAPTERS` 는 `checks_content` 가 아니라
      다른 검사 모듈에 있었고, 그래서 첫 판이 그 키를 통째로 놓쳤다(실측 2026-08-24).
      상수가 어디 사는지는 시간이 지나면 옮겨 다니므로 **패키지를 훑는다.**
    """
    import importlib                                                      # noqa: E402
    tail = "_STRICT_CHAPTERS"
    lib = os.path.join(ROOT, "tools", "buildlib")
    keys = set(optin_keys())
    for fname in sorted(os.listdir(lib)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        try:
            mod = importlib.import_module("buildlib." + fname[:-3])
        except Exception:                     # 못 읽는 모듈이 있어도 나머지는 본다
            continue
        keys.update(name[:-len(tail)].lower() for name in dir(mod)
                    if name.endswith(tail) and name.isupper())
    return sorted(keys)


def subject_dirs(root=ROOT):
    """`data/<과목>` 중 index.json 을 가진 것. 과목 이름을 코드에 적지 않는다."""
    data = os.path.join(root, "data")
    if not os.path.isdir(data):
        return []
    out = []
    for name in sorted(os.listdir(data)):
        path = os.path.join(data, name)
        if os.path.isfile(os.path.join(path, "index.json")):
            out.append(path)
    return out


def plan(index):
    """`(키 → 더할 챕터들)`. 순수 함수 — 테스트가 직접 부른다."""
    files = [str(c.get("file")) for c in (index.get("chapters") or []) if c.get("file")]
    strict = index.get("strictChapters") or {}
    add = {}
    for key in sorted(set(strict_keys()) | set(strict)):
        have = set(strict.get(key) or [])
        missing = [f for f in files if f not in have]
        if missing:
            add[key] = missing
    return add


def apply(index, add):
    """`add` 를 index 에 반영한 새 dict. **지우지 않는다 — 넣기만 한다.**"""
    out = dict(index)
    strict = dict(out.get("strictChapters") or {})
    for key, files in add.items():
        strict[key] = list(strict.get(key) or []) + list(files)
    out["strictChapters"] = {k: strict[k] for k in sorted(strict)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 채운다(기본은 미리보기)")
    ap.add_argument("--keys", action="store_true", help="공통 코드가 아는 승격 키만 찍는다")
    args = ap.parse_args(argv)

    if args.keys:
        keys = strict_keys()
        print("[승격 키] " + str(len(keys)) + "개")
        print("  " + ", ".join(keys))
        return 0

    dirs = subject_dirs()
    if not dirs:
        print("[해당 없음] 이 갈래에는 과목 데이터가 없다 — 0건")
        return 0

    touched = 0
    for path in dirs:
        idx_path = os.path.join(path, "index.json")
        with open(idx_path, encoding="utf-8") as fh:
            index = json.load(fh)
        add = plan(index)
        name = os.path.basename(path)
        if not add:
            print("[=] " + name + " — 모든 챕터가 모든 목록에 있다")
            continue
        touched += 1
        print(("[+] " if args.apply else "[예정] ") + name + " — 키 " + str(len(add)) + "개")
        for key, files in sorted(add.items()):
            print("      " + key + ": " + ", ".join(files))
        if not args.apply:
            continue
        with open(idx_path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(apply(index, add), fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    if touched and not args.apply:
        print("\n실제로 채우려면 --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
