# -*- coding: utf-8 -*-
"""모듈 수준 상수에 **근거가 붙어 있나** — 래칫 (공용 `규칙/방지장치-설계.md` 15항 이식 2026-08-15).

★ **왜 이 부류가 안 잡히나 — 틀린 숫자와 맞는 숫자가 겉모습이 같기 때문이다.**
문장은 근거가 없으면 비어 보이는데 **숫자는 근거가 없어도 «정해진 것» 처럼 보인다.**
그래서 아무도 *«그 8초는 어디서 나왔나»* 를 안 묻는다.
원 실사고(XSanity, 2026-08-15): 크롤링 간격 `20초` · 표본 `100요청이면 충분` · 기간 `3개월` ·
`창당 20쪽` 을 근거 없이 냈고, 나중에 실제로 재 보니 **`100요청` 은 4배 모자랐다.**
더 나쁜 것은 그 사이 **그 수를 근거로 «이러면 충분하다» 는 판단까지 냈다**는 점이다.

**판정선은 둘 중 하나다.**
  · **잰 값** — 무엇을 재서 나왔는지 (예: 정상 응답 180,857 바이트 → 문턱 2,000)
  · **고른 값** — 무엇과 무엇을 견줘 골랐는지 (예: 실측 재현 0.87 → 하한 0.80)
어느 쪽도 아니면 **그 수를 쓰지 말고 먼저 잰다.** 「대충 이 정도면 되겠지」는 재기 전에는
알 수 없는 것을 아는 척하는 것이다.

★ **전부를 FAIL 로 내지 않는다 — 래칫이다.** 사유를 지어내 붙이는 것은 거짓이고, 전부 FAIL 은
경보 피로가 되어 **검사기를 죽인다.** 이 리포가 `audit_check_erosion`(`docs/check-inventory.json`)·
`docs/검사-기본값-기준선.txt` 에서 이미 쓰는 형태다 — 지금 것은 **한 번 소급 면제**하고
**새로 생기는 것만** 막는다.

★★ **기준선의 키에 「값」을 넣는다.** `경로::이름` 만으로 잡으면 면제받은 상수의 **값을 바꿔도**
자가 조용한데, 15항이 막으려는 것이 바로 «근거 없이 정한 값» 이라 **값이 바뀌는 순간이 곧
다시 물어야 하는 순간**이다. 그래서 면제 명단은 **빚 목록**이고, 그 상수를 다시 만지면
그때 근거를 적고 줄을 지운다.

★ **사유 칸을 요구하지 않는다** — 이 리포의 다른 예외 대장(`orphan-checks-allow.txt`·
`개인정보-예외.txt`)은 [사용자 발화 인용 생략] 인데 **여기만 반대**다. 그 대장들은
**사람이 한 줄씩 판정해 넣는 것**이고 이 기준선은 **기계가 한 번에 찍는 소급 면제**라, 사유를
요구하면 곧 지어낸 사유가 붙는다(그게 15항이 금지한 바로 그것이다). **빚은 코드에 근거를
적어서** 갚는다.

★ **함수 안 지역 변수는 대상이 아니다** — 거긴 계산 과정이고, 보려는 것은 **행동을 정하는
손잡이**다(모듈 수준 상수).

★ **값을 되풀이하는 주석은 근거로 안 친다** — `RECEPTOR_Y = 150  # 150` 류가 원 실측에서
대부분이었다. 숫자·기호·공백을 걷어낸 **글자 수 하한**으로 거른다(내용까지는 기계가 못 본다).

사용법:
    python tools/audit_magic_numbers.py           # 새로 생긴 근거 없는 상수 (있으면 exit 1)
    python tools/audit_magic_numbers.py --all     # 면제분까지 전부 + 분포 (읽기 전용, exit 0)
    python tools/audit_magic_numbers.py --accept  # 지금 상태를 기준선으로 (소급 면제)

잠금 `tools/test_checks.py::test_magic_numbers_are_ratcheted_not_flooded`.
"""
import ast
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "docs", "수치-근거-기준선.txt")

# 훑는 자리 — **행동을 정하는 손잡이**가 사는 곳이다. 과목 데이터(`data/`)는 대상이 아니다
# (거긴 교재에서 온 값이고 그 근거는 `sourceRef` 가 따로 진다).
SCAN_DIRS = ("tools", os.path.join(".claude", "hooks"))
# ★ `tools/scratch/` 는 **버릴 스크립트의 자리**다(`test_scratch_scripts_are_not_shared_tools`).
#   거기 상수는 «행동을 정하는 손잡이» 가 아니라 한 번 재고 버리는 누산기라, 세면 그 갈래가
#   상시 빨간불이 된다 — 실제로 thermo 가 `total = 0` 한 줄로 그랬다(2026-08-15).
#   **완화가 아니라 범위다**: 나가는 코드는 그대로 다 잰다.
SKIP_PARTS = {"__pycache__", ".git", "scratch"}

# 근거로 인정하는 주석의 **글자 수 하한**(숫자·기호·공백을 걷어낸 뒤).
#
# ★ **잰 값이다** — 이 리포 전수 214개(`--all` 로 재현, 2026-08-15). 분포:
#   0자 49 · 3~7자 17 · 8자 2 · 9자 3 · 10자 3 · 11자 6 · 12자 4 · 13자 6 · 14자 3 · 15자 4 ·
#   16자 5 · 16자 초과 112. **0자가 최빈이고, 3~7자 띠를 눈으로 전수해 보니 성격이 하나였다:**
#   단위 꼬리표(`# kJ/kg·K` · `# kg/m³` · `# m/s²`)와 좌표 이름표(`# 가로축의 y` ·
#   `# 두 칸 공통 t축 y` · `# 1 단위 = 46px`) — **그 수가 «무엇인지» 를 말할 뿐 «어디서
#   나왔는지» 는 말하지 않는다.** 8자부터는 문장이 시작되고 개수도 촘촘히 이어진다.
#   → 하한을 7로 내리면 단위 꼬리표 다섯이 통과하고, 9로 올리면 8자짜리 문장 둘이 걸린다.
#
# ★★ **첫 실행이 잡은 것은 데이터가 아니라 이 자의 결함이었다** — 그 전말은 `reason_at`.
REASON_MIN_CHARS = 8

# 근거 주석을 **위쪽으로 몇 줄까지** 찾나. 이 리포의 상수 주석은 실측상 전부 바로 윗줄에
# 붙어 있거나(연속 블록) 같은 줄에 있어서, 빈 줄을 만나면 거기서 끊는다 — 줄 수 상한을
# 따로 두면 그 수가 또 근거 없는 수가 된다.
LETTERS = re.compile(r"[\W\d_]+", re.UNICODE)


def source_files(root=ROOT):
    """훑을 파이썬 소스. 순수 함수에 가깝게 — 경로만 돌려준다."""
    out = []
    for rel_dir in SCAN_DIRS:
        base = os.path.join(root, rel_dir)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
            for name in sorted(filenames):
                if name.endswith(".py"):
                    full = os.path.join(dirpath, name)
                    out.append((os.path.relpath(full, root).replace("\\", "/"), full))
    return sorted(out)


_OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}


def number_of(node):
    """숫자 상수면 그 값의 표기, 아니면 None. `-1` 같은 단항 음수도 숫자로 본다.

    ★★ **수식으로 적은 상수도 숫자다** — `12 * 3600` · `15.5 * 0.83` 처럼 **왜 그 값인지를
      식으로 보여 주는** 형태는 이 리포에서 흔하고, 그건 «손잡이가 아닌 것» 이 아니라
      오히려 **가장 손잡이다운 것**이다. 이 갈래를 안 보면 그 자리에 근거를 안 적어도
      조용히 통과한다 — 「빠뜨려도 통과되는 구조」(규칙 7⑷).
    ★ 실측으로 열렸다: 이 자를 만든 바로 그 배치에서 `SUBJECT_DECL_TTL_SEC = 12 * 3600` 을
      새로 적었는데 **자가 그것을 못 봤다.** 자기 규율을 자기가 어긴 자리라 그날 닫았다.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = number_of(node.operand)
        return None if inner is None else ("-" + inner if isinstance(node.op, ast.USub) else inner)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = number_of(node.left), number_of(node.right)
        if left is not None and right is not None:
            return left + _OPS[type(node.op)] + right
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return repr(node.value)
    return None


def constants(src):
    """모듈 수준 `NAME = <숫자>` 목록 — (이름, 값표기, 줄번호). 파싱 실패는 빈 목록."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:                      # ★ body 만 본다 = 모듈 수준만
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        else:
            continue
        value = number_of(node.value) if node.value is not None else None
        if value is None:
            continue
        for name in targets:
            out.append((name, value, node.lineno))
    return out


def reason_at(lines, lineno):
    """그 상수에 붙은 주석 — **같은 줄과 바로 위 블록 중 «긴 쪽».** 없으면 빈 문자열.

    ★★ **처음에는 «같은 줄이 있으면 그것만» 이었고, 그것이 이 자의 첫 오탐이었다** (2026-08-15).
      `SUPERSCRIPT_RATIO = 0.83  # 산문 <sup> 실측 12.5/15` 는 바로 위에 실측 경위가 다섯 줄이나
      적혀 있는데, **같은 줄의 짧은 꼬리표가 그것을 가려** 「근거 없음」으로 났다.
      근거는 **어디에 적혀 있든 근거**라 둘 중 긴 쪽을 본다.
    ★ 「숫자를 인용하면 근거로 친다」로 넓히는 길도 재 봤는데, 그러면
      `# m/s^2 — 공학용 (Eq. 1-4)`·`# 1 단위 = 46px` 이 통째로 통과한다 — **오탐을 오탐으로 갚는** 꼴이다.

    ★★ **아래쪽 「속성 독스트링」도 근거로 친다** (넓힘 2026-08-23, 두 번째 오탐).
      `MITER_SPIKE_SCREEN_PX = 1.0` 바로 **아래**에 근거가 세 줄 적혀 있는데
      (`\"\"\"…31° 사례의 돌출이 2.25 화면px 였으므로 그 절반을 바닥으로 둔다.\"\"\"`)
      위·같은 줄만 보던 이 자가 「근거 없음」으로 신고했다. 그 형태는 PEP 257 이 인정하는
      **속성 독스트링**이고 이 리포가 실제로 쓰는 표기다 — 바로 위 `MITER_SPIKE_RATIO` 도 같은 꼴이다.
      ★ 첫 오탐과 **원인이 같다: 근거가 어디 적혀 있든 근거인데 자가 한 자리만 봤다.**
        그래서 처방도 같다 — 후보를 늘리고 **가장 긴 것**을 쓴다.
      ★ 오탐을 안 만든다: 문자열 리터럴로 **시작하는 줄**만 보고, 글자 수 하한은 그대로 적용된다.
    """
    same = ""
    line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    if "#" in line:
        same = line.split("#", 1)[1].strip()
    above = []
    i = lineno - 2
    while i >= 0:
        stripped = lines[i].strip()
        if not stripped.startswith("#"):
            break
        above.append(stripped.lstrip("#").strip())
        i -= 1
    block = " ".join(reversed(above))
    return max((block, same, docstring_below(lines, lineno)), key=letters)


def docstring_below(lines, lineno):
    """상수 **바로 아래**의 속성 독스트링. 없으면 빈 문자열. 순수 함수 — 테스트가 직접 부른다."""
    i = lineno                                   # 0-기반으로 «다음 줄»
    if i >= len(lines):
        return ""
    head = lines[i].strip()
    for quote in ('"""', "'''"):
        if head.startswith(quote):
            body, rest = [head[len(quote):]], lines[i + 1:]
            if body[0].endswith(quote):          # 한 줄짜리
                return body[0][: -len(quote)].strip()
            for nxt in rest:
                if quote in nxt:
                    body.append(nxt.split(quote, 1)[0])
                    break
                body.append(nxt)
            return " ".join(x.strip() for x in body).strip()
    return ""


def letters(text):
    """숫자·기호·공백을 걷어낸 글자 수 — 「값을 되풀이한 주석」을 거르는 자다."""
    return len(LETTERS.sub("", text or ""))


def scan(root=ROOT):
    """[{key, path, name, value, line, reason, chars, grounded}] — 판정은 안 한다."""
    found = []
    for rel, full in source_files(root):
        with open(full, encoding="utf-8") as fh:
            src = fh.read()
        lines = src.splitlines()
        for name, value, lineno in constants(src):
            reason = reason_at(lines, lineno)
            chars = letters(reason)
            found.append({
                "key": rel + "::" + name + " = " + value,
                "path": rel, "name": name, "value": value, "line": lineno,
                "reason": reason, "chars": chars,
                "grounded": chars >= REASON_MIN_CHARS,
            })
    return found


def load_baseline(path=BASELINE):
    """기준선에 적힌 «소급 면제된 키» 집합. 없으면 빈 집합(= 전부 새것)."""
    keys = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("|", 1)[0].strip()
                if line and not line.startswith("#"):
                    keys.add(line)
    except OSError:
        pass
    return keys


HEADER = """# 수치 근거 기준선 — `tools/audit_magic_numbers.py` 가 읽는다.
#
# 여기 적힌 것은 **빚이다.** 공용 `규칙/방지장치-설계.md` 15항을 켜던 날 이미 있던
# «근거 없는 모듈 수준 상수» 를 한 번 소급 면제한 목록이고, 그 상수를 다시 만질 일이
# 생기면 **그때 코드에 근거를 적고 이 줄을 지운다.**
#
# 형식:  <리포 상대경로>::<이름> = <값>
#   · **값까지가 키다** — 면제받은 상수의 값을 바꾸면 새 항목이 되어 다시 걸린다.
#     15항이 막으려는 것이 «근거 없이 정한 값» 이라, 값이 바뀌는 순간이 다시 물어야 하는 순간이다.
#   · **사유 칸을 요구하지 않는다** (다른 예외 대장과 반대다). 이건 사람이 한 줄씩 판정해
#     넣는 대장이 아니라 기계가 한 번에 찍은 소급 면제라, 사유를 요구하면 곧 «지어낸 사유»가
#     붙는다 — 그게 15항이 금지한 바로 그것이다. 빚은 **코드에 근거를 적어서** 갚는다.
#   · 늘리는 것은 `--accept` 뿐이고, 그 실행은 diff 에 그대로 남는다.
"""


def save_baseline(keys, path=BASELINE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER + "\n")
        for key in sorted(keys):
            fh.write(key + "\n")


def show(items, label, limit=20):
    """목록을 찍되 **자른 것을 자른 만큼 말한다.**

    ★ 「조용히 잘린 순회」를 안 만들려는 것이다(규칙 11) — 화면은 표본이고 정본은 기준선
      파일이라, 몇 개를 안 보여 줬는지 말하지 않으면 읽는 사람이 «이게 전부» 로 읽는다.
    """
    # ★ **하한 언저리부터** 보여 준다(주석 글자 수 내림차순). 0자가 최빈이라 파일 순서로
    #   찍으면 화면이 «주석이 아예 없는 것» 으로 채워지는데, 하한을 판정할 때 봐야 하는 것은
    #   **아슬아슬한 자리**다.
    for f in sorted(items, key=lambda x: -x["chars"])[:limit]:
        print("  [%s] %s:%d  %s = %s   주석 %d자%s"
              % (label, f["path"], f["line"], f["name"], f["value"], f["chars"],
                 "  « " + f["reason"][:40] if f["reason"] else ""))
    if len(items) > limit:
        print("  … 외 %d건 (전부는 기준선 파일과 `--all` 이 갖는다)" % (len(items) - limit))


def main(argv):
    show_all = "--all" in argv
    accept = "--accept" in argv
    found = scan()
    ungrounded = [f for f in found if not f["grounded"]]
    baseline = load_baseline()

    if accept:
        save_baseline({f["key"] for f in ungrounded})
        print("[수치 근거] 소급 면제 %d건을 기준선에 적었다 — %s"
              % (len(ungrounded), os.path.relpath(BASELINE, ROOT).replace("\\", "/")))
        print("            이제부터 **새로 생기는 것만** 막는다. 이 줄들은 빚이다.")
        return 0

    fresh = [f for f in ungrounded if f["key"] not in baseline]
    print("[수치 근거] 모듈 수준 상수 %d개 · 근거 있음 %d개(%d%%) · 소급 면제 %d건 · **새 것 %d건**"
          % (len(found), len(found) - len(ungrounded),
             round(100 * (len(found) - len(ungrounded)) / len(found)) if found else 0,
             len(baseline), len(fresh)))

    if show_all:
        # ★ 첫 실행은 «재는 것»이 아니라 «자를 재는 것»이다 — 하한을 정하려면 분포부터 본다.
        buckets = {}
        for f in found:
            buckets[f["chars"]] = buckets.get(f["chars"], 0) + 1
        # 하한을 정할 때 보는 것은 **하한 언저리**라 그 위는 한 줄로 접는다.
        edge = 2 * REASON_MIN_CHARS
        print("  주석 글자 수 분포(하한 %d · %d자까지만 펼친다):" % (REASON_MIN_CHARS, edge))
        for chars in sorted(c for c in buckets if c <= edge):
            print("    %3d자  %d개%s" % (chars, buckets[chars],
                                         "   ← 하한" if chars == REASON_MIN_CHARS else ""))
        far = sum(n for c, n in buckets.items() if c > edge)
        print("    %d자 초과  %d개" % (edge, far))
        show(ungrounded, "면제")

    if not fresh:
        print("  새로 생긴 근거 없는 상수 없음.")
        return 0

    print("  ★ 아래 상수에 **근거**를 적을 것 — 잰 값이면 무엇을 재서, 고른 값이면 무엇과 견줘.")
    show(fresh, "근거 없음")
    print("  (정말로 지금 못 적으면 `--accept` 로 빚에 올린다 — 그 실행은 diff 에 남는다.)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
