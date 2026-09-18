# -*- coding: utf-8 -*-
"""콘텐츠 감사 (읽기 전용).

빌드 검사로 못 만드는 것 — 판단이 필요해 사람이 봐야 하는 것들 — 을 리포트로 뽑는다.
빌드가 막을 수 있는 규칙은 build_site.py로 승격하고, 여기엔 남기지 않는다.

    python tools/audit_content.py          # 요약
    python tools/audit_content.py --all    # 전체 상세

절대 파일을 쓰지 않는다. 인자로 받은 경로도 열지 않는다 (감사 대상은 리포지토리 고정).
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildlib.checks_content import PROBLEM_DIFFICULTIES, resolve_anchor_text  # noqa: E402
from buildlib.textutil import _plain_math_text  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# `sys.exit("SUBJECT=…")` 로 한글 오류를 내게 됐으므로 stderr 도 함께 연다 (2026-09-07).
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def subject_dirs(base=None):
    """`data/` 아래 chNN.json 을 가진 과목 폴더 **전부**. 순수에 가깝게 — 경로만 돌려준다."""
    base = base or os.path.join(ROOT, "data")
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        subject = os.path.join(base, name)
        if not os.path.isdir(subject) or name.startswith("."):
            continue
        if any(re.fullmatch(r"ch\d{2}\.json", f) for f in os.listdir(subject)):
            out.append(subject)
    return out


def only_matches(only, dirs):
    """`--only` 필터에 맞는 과목 폴더. 순수 함수 — 필터가 없으면 전부."""
    if not only:
        return list(dirs)
    return [d for d in dirs if only in os.path.basename(d)]


def reject_unmatched_only(only, dirs, out=None):
    """`--only` 가 **아무 과목과도 안 맞으면** 그 사실을 찍고 True 를 낸다.

    ★ **조용한 0건을 막는 자리다** (열린 날 2026-09-09, 사용자 *[발화 생략]*).
      과목 이름을 오타 내면 순회 대상이 0 개가 되고, 그러면 감사가 「합계 — 0건」을 찍으며
      **정상 종료한다.** 화면에서 「진짜 0건」과 구별되지 않으므로, 오타 하나로 그 감사가
      통째로 죽은 채 「다 됐다」로 읽힌다. 재는 자는 `tools/audit_sweep_reach.py`.

    ★ **「대상이 아닌 과목」과 다르다.** 선언이 있어야 도는 도구가 선언 없는 과목에서 0 건을
      내는 것은 정상이고 exit 0 이어야 한다(AGENTS 「알려진 함정」). 여기서 막는 것은
      **어느 과목과도 안 맞는 이름**, 곧 오타뿐이다.
    """
    if not only or only_matches(only, dirs):
        return False
    (out or sys.stdout).write(
        "[대상 없음] `--only=%s` 에 맞는 과목 폴더가 없다 — 이름을 확인할 것\n"
        "   ※ 0 건이 아니라 **한 과목도 안 봤다**는 뜻이다\n" % only)
    return True


def discover_data_dir():
    """이 실행이 다룰 과목 데이터 폴더. **환경변수 `SUBJECT` 가 정본이고, 없으면 첫 과목이다.**

    열린 날 2026-07-26 — `data/열역학`으로 **하드코딩**돼 있어 math 워크트리에서 import 시점에
    죽었다. 그때 전제는 «과목 = 브랜치 = 워크트리라 data/ 아래 과목 폴더는 하나뿐» 이었다.

    ★★ **2026-09-07 평탄화로 그 전제가 깨졌다.** 21과목이 한 트리에 있는데 이 함수는 여전히
      **첫 폴더 하나**(`계측공학`)를 돌려준다 — 그래서 `audit_content` 를 쓰는 `fix_*`·감사
      전부가 **한 과목만 보고 「0건」을 찍었다.** 0건이 아니라 **스무 과목을 한 번도 안 본
      것**인데 출력이 통과와 같았다(AGENTS 「폴백으로 하나만 넣어 두기」 그 자체다).
      → 부르는 쪽이 `SUBJECT` 로 과목을 **지목**하고, 전 과목 순회는
      `python tools/for_each_subject.py <도구> [인자…]` 가 맡는다. 이 자는 과목 이름을
      모르는 채로 남는다.
    """
    base = os.path.join(ROOT, "data")
    want = (os.environ.get("SUBJECT") or "").strip()
    if want:
        picked = os.path.join(base, want)
        if os.path.isdir(picked):
            return picked
        sys.exit("SUBJECT='%s' 인데 그런 과목 폴더가 없다 — data/ 아래 이름 그대로 줄 것" % want)
    subjects = subject_dirs(base)
    return subjects[0] if subjects else base


DATA = discover_data_dir()


def chapter_file(arg):
    """`--chapter` 인자를 장 파일 경로로 푼다 — 경로(`data/<과목>/chNN.json`)면 그대로 쓴다.

    이름뿐(`chNN.json`)이면 `SUBJECT` 가 있거나 과목이 하나일 때만 받는다. 막는 것: 평탄화 뒤 이름만 주면
    `DATA` 폴백(첫 과목)의 같은 이름 장을 조용히 고치거나 「없는 챕터」로 죽던 것(2026-09-14 set_change_notes).
    """
    if os.path.dirname(arg):
        return os.path.abspath(arg) if os.path.isfile(arg) else os.path.join(ROOT, arg)
    if not (os.environ.get("SUBJECT") or "").strip() and len(subject_dirs()) > 1:
        sys.exit("--chapter=%s 로는 과목을 모른다 — data/<과목>/%s 경로로 주거나 SUBJECT=<과목> 을 줄 것"
                 % (arg, arg))
    return os.path.join(DATA, arg)


def discover_chapters():
    """존재하는 chNN.json을 실제로 훑어 감사 대상을 정한다.

    열린 날 2026-07-26 — 이 목록이 `("ch01","ch02","ch03")`으로 **하드코딩**돼 있었다.
    그래서 ch04를 만들자 감사가 그 챕터를 **조용히 건너뛰었고**, `--originality`의
    Moran·1:1 감시가 새 챕터에는 한 번도 돌지 않았다. 빌드는 index.json의 status로
    대상을 정하는데 감사만 별도 하드코딩이라, 챕터가 늘 때마다 사람이 여기를 고쳐야 했다.
    (규칙 11: 순회 범위를 확인하지 않은 '0건'은 '없다'가 아니라 '거기까지는 없다'이다.)

    status와 무관하게 파일이 있으면 감사한다 — 제작 중(todo)일수록 감사가 더 필요하다.

    ★★ **과목이 없는 워크트리가 있다 — 그게 정상이다 (2026-08-15).** 공통 정본인 `main` 은
    `data/` 자체가 없다(과목 데이터는 각 갈래 고유다). 그런데 여기서 `os.listdir` 이 그대로
    터져 **이 모듈을 import 하는 `test_checks.py` 가 통째로 무너졌다** — 실측: main 에서
    실패 96건 중 **92건이 이 한 줄**이었다. 즉 공통을 고치고도 **그 자리에서 회귀를 못 돌렸다.**
    「대상이 아닌 과목은 실패가 아니다」(AGENTS 알려진 함정)를 여기에도 적용한다.
    """
    if not os.path.isdir(DATA):
        return ()
    found = []
    for name in sorted(os.listdir(DATA)):
        if re.fullmatch(r"ch\d{2}\.json", name):
            found.append(name[:-5])
    return tuple(found)


CHAPTERS = discover_chapters()
COLLS = ("theory", "derivation", "practice", "problems")

VERBOSE = "--all" in sys.argv


def load(ch):
    with open(os.path.join(DATA, ch + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def groups(d):
    return {
        "theory": d["theory"]["sections"],
        "derivation": d["derivation"]["formulas"],
        "practice": d.get("practice") or [],
        "problems": d.get("problems") or [],
    }


def head(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- 1. 검사 사각지대
def audit_scope(chapters):
    """컬렉션별 필드 분포. 여러 컬렉션에 사는 필드는 검사도 전 컬렉션을 돌아야 한다.

    2026-07-21: comprehensionChecks가 theory·derivation에 있는데 검사는 theory만 돌아
    ch02 유도 11건이 그대로 통과한 사고가 있었다. 그 사각지대를 기계로 다시 찾는다.
    """
    head("1. 검사 사각지대 — 컬렉션별 필드 분포")
    fields = defaultdict(lambda: defaultdict(int))
    for ch, d in chapters.items():
        for coll, items in groups(d).items():
            for it in items:
                for k in it:
                    fields[coll][k] += 1

    shared = []
    for f in sorted({k for c in fields for k in fields[c]}):
        where = [c for c in COLLS if fields[c].get(f)]
        if len(where) > 1:
            shared.append((f, where))

    print(f"{'field':24}" + "".join(f"{c:>12}" for c in COLLS))
    print("-" * 72)
    for f in sorted({k for c in fields for k in fields[c]}):
        if not VERBOSE and not any(f == s[0] for s in shared):
            continue
        print(f"{f:24}" + "".join(f"{fields[c].get(f, 0):>12}" for c in COLLS))

    print("\n[공유 필드 — build_site.py의 해당 검사가 이 컬렉션을 전부 도는지 확인할 것]")
    for f, where in shared:
        print(f"  {f:24} → {', '.join(where)}")


# ---------------------------------------------------------------- 2. 유효숫자
NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?=\s*(?:×|[A-Za-zμ°]|$|\s|,|\)))")


def sig_digits(tok):
    t = tok.lstrip("0").replace(".", "")
    t = t.rstrip("0") if "." in tok else t
    return len(t) if t else 1


def step_text(step):
    """풀이 한 단계를 검사용 문자열로 편다 (순수 함수 — 테스트 대상).

    열린 날 2026-07-28. **감사가 크래시했다** — `TypeError: expected string … got 'dict'`.
    뷰어의 `renderStep` 은 진작부터 두 형태를 받는다: 문자열이면 설명만, `{text, equations}`
    면 설명 아래에 식을 독립 줄로 그린다(가로 나열 지적의 해법으로 도입된 형태다).
    그런데 이 감사는 **문자열만** 가정한 채로 남아 있었다.

    새어나간 구조: 스키마가 넓어질 때 *렌더러*만 고치고 *감사*는 따라오지 않았다. 그리고
    기존 과목 데이터가 마침 문자열만 쓰고 있어서 **아무도 눈치채지 못했다** — 새 과목이
    새 형태를 쓰는 순간 감사가 죽는다. 실제로 기계재료 ch01 에서 그렇게 났다.
    """
    if isinstance(step, dict):
        return " ".join([str(step.get("text") or "")] + [str(e) for e in step.get("equations") or []])
    return str(step)


def audit_sigfig(chapters):
    """최종답과 풀이 중간값의 유효숫자 현황.

    확정 규칙: 최종답은 선두 1이면 4자리, 그 외 3자리.
    풀이 중간값 규칙은 미확정 — 현황을 보고 정한다.
    """
    head("2. 유효숫자 — 최종답 vs 풀이 중간값")
    for ch, d in chapters.items():
        rows = []
        for q in d.get("problems") or []:
            ans = str(q.get("answer", ""))
            ans_digits = [sig_digits(m.group(1)) for m in NUM.finditer(ans)]
            mid = []
            for step in q.get("solutionOutline") or []:
                for m in NUM.finditer(step_text(step)):
                    tok = m.group(1)
                    if "." in tok:                      # 정수 계수는 유효숫자 논의 밖
                        mid.append((tok, sig_digits(tok)))
            over = [t for t, n in mid if n >= 4]
            if over or VERBOSE:
                rows.append((q["id"], ans, ans_digits, over[:6]))
        print(f"\n-- {ch}: 풀이 중간값이 4자리 이상인 문항 {len(rows)}건")
        for qid, ans, ad, over in rows:
            print(f"   {qid:12} 답 {ans[:34]:36} 답자릿수{ad} 중간값4+ {over}")


# ---------------------------------------------------------------- 3. 풀이 표기
SYMBOLIC = re.compile(r"^[A-Za-zΔΣρμγηα-ω_{}\\^\s·×/()+\-]+$")


def step_lines(step):
    """풀이 한 단계를 **줄 단위**로 편다 — 설명 1줄 + 식 n줄.

    `step_text` 는 검사용으로 한 줄에 이어 붙이지만(유효숫자·문자열 검색용),
    '한 단계에 기호식이 있었나'를 보는 검사는 **줄을 섞으면 판정이 뒤집힌다** —
    설명 문장의 문자가 식의 좌변으로 오인되기 때문이다.
    """
    if isinstance(step, dict):
        return [str(step.get("text") or "")] + [str(e) for e in step.get("equations") or []]
    return [str(step)]


def audit_notation(chapters):
    """풀이 표기: 기호식 → 숫자 대입 → 최종값 순서를 지키는가.

    'W = (420)(3.73) = 1567 N' 처럼 기호식 없이 바로 대입한 단계를 찾는다.
    (기대: 'W = mg = (420)(3.73) = 1567 N')
    """
    head("3. 풀이 표기 — 기호식 없이 바로 숫자 대입한 단계")
    for ch, d in chapters.items():
        hits = []
        for q in d.get("problems") or []:
            for i, step in enumerate(q.get("solutionOutline") or []):
                # ★ 순회 범위 (2026-07-29). 종전에는 `step` 을 문자열로만 보고 `"=" not in step`
                # 으로 걸렀는데, 스키마가 `{text, equations}` 로 넓어진 뒤 그 표현은 **dict 의
                # 키**("text"/"equations")를 검사하게 되어 **모든 단계를 건너뛰었다.**
                # 크래시가 아니라 조용한 0건이라 '결함이 없다'로 읽혔다 — ch02 를 전부
                # 객체로 옮긴 직후 85건이 0건이 된 것으로 드러났다(AGENTS 규칙 11).
                # 이제 설명·식 줄을 각각 한 단계로 본다.
                for line in step_lines(step):
                    if "=" not in line:
                        continue
                    lhs, _, rest = line.partition("=")
                    if not re.search(r"[A-Za-zΔρσγη]", lhs):
                        continue
                    first_rhs = rest.split("=")[0].strip()
                    if not first_rhs or not re.search(r"\d", first_rhs):
                        continue
                    # 첫 우변에 숫자가 있는데 그 앞에 기호식 단계가 없으면 대입부터 시작한 것
                    if not SYMBOLIC.match(first_rhs):
                        hits.append((q["id"], i + 1, line.strip()[:88]))
        print(f"\n-- {ch}: {len(hits)}건")
        for qid, i, s in (hits if VERBOSE else hits[:12]):
            print(f"   {qid:12} [{i}] {s}")
        if not VERBOSE and len(hits) > 12:
            print(f"   ... 외 {len(hits) - 12}건 (--all 로 전체)")


# ---------------------------------------------------------------- 4. 가운데점
def audit_middot(chapters):
    """SVG 라벨의 ' · ' 용법 분류.

    곱셈·결합(1 kg · 1 m/s²)과 병렬 나열은 유지, 용어-설명 연결은 콜론이 맞다.
    자동 판별이 안 되므로 목록만 뽑고 판정은 사람이 한다.
    """
    head("4. 가운데점 ' · ' 사용처 (판정은 사람이)")
    pat = re.compile(r">([^<>]{0,30} · [^<>]{0,34})<")
    for ch, d in chapters.items():
        raw = json.dumps(d, ensure_ascii=False)
        uniq = sorted({m.group(1).strip() for m in pat.finditer(raw)})
        print(f"\n-- {ch}: {len(uniq)}종")
        for u in (uniq if VERBOSE else uniq[:14]):
            print("   ", u)
        if not VERBOSE and len(uniq) > 14:
            print(f"    ... 외 {len(uniq) - 14}종")


# ---------------------------------------------------------------- 5. 한영 병기
def audit_terms(chapters):
    """이론 본문의 '한글(english)' 병기 용어 — 이전 장 딥링크 후보."""
    head("5. 한영 병기 용어 (이전 장 링크 후보)")
    pat = re.compile(r"([가-힣][가-힣\s·]{0,12})\(([a-z][a-z\s\-]{2,30})\)")
    for ch, d in chapters.items():
        found = defaultdict(list)
        for s in d["theory"]["sections"]:
            for m in pat.finditer(s.get("content", "")):
                found[s["id"]].append(f"{m.group(1).strip()}({m.group(2).strip()})")
        total = sum(len(v) for v in found.values())
        print(f"\n-- {ch}: {total}건")
        for sid, terms in list(found.items())[: None if VERBOSE else 4]:
            print(f"   {sid}: {', '.join(terms[:8])}")


# ---------------------------------------------------------------- 5a. Originality guardrails
def theory_textbook_refs(sections):
    """이론 절의 sourceRef에서 교재 절 번호(§N-M·§N.M)를 등장 순서대로 뽑는다.

    열린 날 2026-07-24 — 이 표식을 `section['content']`에서 찾고 있었다. 본문은 학생이
    읽는 글이라 교재 절 번호가 들어갈 일이 없어 세 챕터 모두 0건이었고, 규칙 12의
    1:1 감시는 **한 번도 작동한 적이 없다.** 표식이 실제로 사는 곳은 sourceRef다.

    확장 2026-07-26 — 하이픈(Cengel §2-1)만 인식해, 점 표기(Kreyszig §2.1)를 쓰는
    공학수학에서는 이 감시가 **다시 한 번도 작동한 적이 없었다.** 두 표기를 모두 뽑는다.
    '무엇이 기준 교재인가'는 여기서 정하지 않는다 — chNN.textbook-map.md 표에 실린
    형식이 정하고, follows_textbook_order가 지도에 없는 표식(예: thermo의 Moran §2.1)을
    비교 전에 떨군다.

    ★ 확장 2026-08-02 — **세 번째 같은 부류.** 이번에는 `§` 기호가 전제였다.
    동역학 sourceRef 는 `Hibbeler 12.7 (교재 p.73-76)` 라 절 기호를 쓰지 않는데,
    정규식이 `§` 를 **필수**로 요구해 표식 0건 → 감사가 `[unverified]` 만 찍고 있었다.
    (사용자 지적으로 드러났다: *[발화 생략]* — 감사가 돌았다면 그 사실이 진작 신고됐어야 한다.)

    **그래서 `§` 를 선택으로 바꾸되 쪽 번호는 뺀다.** `§` 만 지우면 `(pp.2-8)`·`(교재 p.73-76)`
    의 쪽 범위가 절 번호로 먹힌다(회귀 테스트가 이 부작용을 즉시 잡았다).
    `(?<![\\w.])` — **앞 글자가 낱말 문자나 점이면 시작하지 않는다.** `p.` 하나만 막으면
    엔진이 한 글자 밀어 `3-76` 을 잡으므로(실제로 그렇게 나왔다) 경계로 막아야 한다.
    남는 잡음은 **호출부가 지도 표의 절 번호 집합과 교차**시켜 떨군다 —
    즉 무엇이 절 번호인지는 이 함수가 아니라 그 과목의 `chNN.textbook-map.md` 가 정한다.
    공통 코드가 과목의 표기 습관을 전제하지 않는 형태다
    (AGENTS 「공통 도구에 과목별 사실을 박지 않는다」).
    """
    out = []
    for section in sections:
        out.extend(re.findall(r"(?<![\w.])(?:§\s*)?(\d+[-.]\d+)",
                              str(section.get("sourceRef", ""))))
    return list(dict.fromkeys(out))


def follows_textbook_order(section_order, textbook_order):
    """인용 순서가 교재 순서와 같은가.

    전체 목록과의 완전 일치를 요구하면 한 절만 건너뛰어도 '다르다'가 되어 감시가
    무력해진다. **인용된 절만 남긴 교재 순서**와 비교해야 진짜 1:1을 잡는다.

    확장 2026-07-26 — 지도(textbook_order)에 없는 표식은 비교 전에 떨군다. 부교재
    표기(thermo의 Moran §2.1)가 기준 교재의 순서 판정을 오염시키지 않게 하는 안전판이다.
    """
    listed = [x for x in section_order if x in set(textbook_order)]
    cited = set(listed)
    return bool(listed) and listed == [x for x in textbook_order if x in cited]


_MAP_ROW = re.compile(r"^\|\s*(§\s*)?(\d+[-.]\d+)\s*\|", re.M)


def textbook_map_order(map_text):
    """chNN.textbook-map.md 절 표의 첫 칸에서 교재 절 번호를 표 순서대로 뽑는다(하이픈·점 겸용).

    ★ 확장 2026-08-02 (같은 날 2차) — **같은 부류의 네 번째다. 이번엔 두 정규식이 서로 반대를
    요구하고 있었다.** 같은 날 오전에 `theory_textbook_refs` 는 `§` 를 **선택**으로 바꿨는데
    (동역학 sourceRef 가 `Hibbeler 12.7` 이라 절 기호가 없었다), 지도 쪽인 이 함수는 `§` 를
    여전히 **금지**하고 있었다. 고체역학 지도는 절 표가 `| §1.1 |` 형식이라 **한 줄도 안 읽혔다.**

    결과가 두 갈래로 나빴다 (2026-08-02 solids 실측):
      · ch01 — 지도가 비어 `[unverified]` 만 찍혔다. **1:1 감시가 한 번도 안 돈 것**이다.
      · ch02 — 절 표는 못 읽고 같은 파일의 **예제 표**(`| 2-1 |`)를 절 표로 오인했다.
        그래서 sourceRef 의 **식 번호**(`Eq. 2-1~2-4`)와 대조해 `1:1 — 2-1 → 2-4` 라는
        **가짜 판정**을 냈다. 조용한 미실행보다 나쁘다 — 통과처럼 보이는 오보다.

    그래서 `§` 를 선택으로 받되, **`§` 를 쓰는 지도에서는 `§` 붙은 행만 절 표로 본다.**
    한 파일에 절 표와 예제 표가 함께 있고 예제 번호가 `2-1` 처럼 절 번호와 같은 모양이라,
    표식이 있으면 그것이 곧 '어느 표가 절 표인가'의 답이다. 표식이 없는 지도(동역학)는
    종전대로 맨 숫자를 쓴다 — 공통 코드가 과목의 표기 습관을 전제하지 않는 형태다.
    """
    rows = _MAP_ROW.findall(map_text)
    marked = [num for mark, num in rows if mark]
    return list(dict.fromkeys(marked or [num for _mark, num in rows]))


def overview_exempt(data):
    """개요 장(chapterNumber 0)은 대응 교재 챕터가 없다 — 지도·1:1 감시 면제 (2026-07-26)."""
    return data.get("chapterNumber") == 0


def moran_applies(index_data):
    """Moran 반영 감시(규칙 12⑸)는 Moran을 실제 교재로 쓰는 과목에만 적용한다 (2026-07-26).

    공학수학의 교재는 Kreyszig + 유튜브 부교재라 'Moran 0건'은 결함이 아니라 상수였다 —
    영구 거짓 경보는 진짜 경보를 덮는다. index.json의 교재 필드로 판정한다.
    """
    blob = " ".join(str(index_data.get(k, "")) for k in ("baseTextbook", "supplementTextbook"))
    return "Moran" in blob


def load_index():
    try:
        with open(os.path.join(DATA, "index.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        return {}


# 지도 문서에 유지 근거가 적혔는지 보는 표제 (2026-08-02). AGENTS 규칙 12⑴ 이 정본이다.
ORDER_VERDICT_RE = re.compile(r"^#{2,}\s*순서 판정", re.M)


def audit_originality(chapters):
    """Report two intentional review signals; this never rewrites content."""
    head("5a. 독자성 감시 — 교재 절 순서와 Moran sourceRef 반영")
    watch_moran = moran_applies(load_index())
    if not watch_moran:
        print("(Moran 감시 비활성 — index.json 교재 필드에 Moran이 없는 과목)")
    for ch, data in chapters.items():
        map_path = os.path.join(DATA, ch + ".textbook-map.md")
        sections = data.get("theory", {}).get("sections") or []
        missing_source = [section.get("id", "?") for section in sections
                          if not str(section.get("sourceRef", "")).strip()]
        moran_hits = sum(bool(re.search(r"\bMoran\b", str(section.get("sourceRef", "")), re.I))
                         for section in sections)
        print(f"\n-- {ch}: theory sections {len(sections)}, "
              f"Moran-in-sourceRef {moran_hits}, sourceRef-missing {len(missing_source)}")
        if missing_source:
            print("   [미기입] sourceRef: " + ", ".join(missing_source))
        if overview_exempt(data):
            print("   [n/a] 개요 장(chapterNumber 0) — 대응 교재 챕터가 없어 지도·1:1 감시 면제")
            continue
        if not os.path.isfile(map_path):
            print("   [blind spot] textbook map missing; 1:1 order cannot be assessed")
            continue
        map_text = open(map_path, encoding="utf-8").read()
        textbook_order = textbook_map_order(map_text)
        section_order = [x for x in theory_textbook_refs(sections) if x in set(textbook_order)]
        if follows_textbook_order(section_order, textbook_order):
            # ★ 2026-08-02 — `[blind spot]` 은 **판정을 요구하는 신호**이지 결함 선고가 아니다.
            #   규칙 12⑴ 의 목적은 본문이 교재를 닮는 것을 막는 것이지 순서를 흔드는 것이 아니고,
            #   순서를 바꾸면 학습이 나빠지는 장이 실제로 있다(사용자 결정 2026-08-02).
            #   게다가 이 지표는 **순서 바꾸기만** 잰다 — 쪼개기·합치기·신설로 독자성을 확보한
            #   챕터도 1:1 로 신고된다(고체역학 ch01·ch02 가 그 형태다).
            #   그래서 유지 근거가 지도 문서에 적혀 있으면 닫힌 것으로 본다.
            recorded = ORDER_VERDICT_RE.search(map_text)
            print("   " + ("[판정 기록됨]" if recorded else "[판정 필요]")
                  + " 인용 순서가 교재와 1:1 — " + " → ".join(section_order))
            if not recorded:
                print("      → 절을 흔들기 전에 AGENTS 규칙 12⑴ 의 표로 쪼개기·합치기·신설을 "
                      "이미 했는지 셀 것. 유지가 옳으면 " + ch + ".textbook-map.md 에 "
                      "'## 순서 판정' 절을 두고 근거를 적으면 이 줄이 닫힌다")
        elif not section_order:
            print("   [unverified] no textbook-section markers in theory sourceRef")
        else:
            print("   [ok] theory citation order differs from textbook order")
        if not watch_moran:
            continue
        if moran_hits == 0 and not missing_source:
            print("   [blind spot] Moran is absent from theory sourceRef")
        elif moran_hits == 0:
            print("   [unverified] Moran source cannot be assessed until sourceRef is filled")


# ---------------------------------------------------------------- 6. 규칙 도달성
IMPERATIVE = re.compile(r"(하지 말 것|금지|반드시|해야 한다|지킬 것|말아야|필수)")


def audit_rule_reach():
    """작업 중 지켜야 할 규칙이 '작업 중에 읽히는 문서'에 있는가.

    AGENTS.md만이 두 에이전트가 작업 중 읽는 문서다.
    CLAUDE.md는 Claude 전용, docs/는 셋업·복붙용이라 Codex에 도달하지 않는다.
    2026-07-21: 배치 실행 규율을 docs/codex-setup.md에 넣어 Codex가 못 본 사고가 있었다.
    """
    head("6. 규칙 도달성 — 작업 규칙이 엉뚱한 문서에 있는가")
    targets = [
        ("CLAUDE.md", "Claude 전용 — Codex에 도달하지 않음"),
        (os.path.join("docs", "codex-setup.md"), "셋업 시점 문서 — 작업 중 읽지 않음"),
        (os.path.join("docs", "handoff-prompts.md"), "사용자 복붙용 — 에이전트가 읽지 않음"),
    ]
    total = 0
    for rel, why in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        body = open(path, encoding="utf-8").read()
        body = re.sub(r"```.*?```", "", body, flags=re.S)   # 복붙 코드블록은 제외
        hits = [l.strip() for l in body.splitlines()
                if IMPERATIVE.search(l) and not l.strip().startswith(">")]
        total += len(hits)
        print(f"\n-- {rel} ({why}): 명령형 문장 {len(hits)}건")
        for h in (hits if VERBOSE else hits[:5]):
            print("   ", h[:96])
        if not VERBOSE and len(hits) > 5:
            print(f"    ... 외 {len(hits) - 5}건")
    print(f"\n총 {total}건. 각각 판정할 것 — "
          "작업 중 지켜야 하면 CLAUDE.md로 옮기고, 셋업/복붙 전용이면 그대로 둔다.")


# ---------------------------------------------------------------- 7. 삽화 배치 지도
def figure_anchor_index(paragraphs, figure):
    """삽화가 붙는 단락 번호(1-based). **anchorText가 정본이고 afterParagraph는 보조다.**

    열린 날 2026-07-24 — 이 감사가 `afterParagraph`만 읽어서, `anchorText`로 묶은 삽화를
    '앵커 없음'으로 세고 유령 글밀도 경고를 냈다(ch01 `sec-properties`·`sec-state-postulate`
    2건). 빌드(`checks_content`)는 anchorText를 풀어 쓰므로 **빌드는 통과하는데 감사만
    경고하는** 상태였고, 그 차이를 근거로 Codex에 불필요한 작업을 낼 뻔했다.
    빌드와 같은 해석기(`resolve_anchor_text`)를 쓰는 것이 핵심이다 — 규칙을 두 번 구현하면
    두 곳이 어긋난다.
    """
    anchor = figure.get("anchorText")
    if anchor:
        idx, _why = resolve_anchor_text(paragraphs, anchor)
        if idx is not None:
            return idx
    return figure.get("afterParagraph")


def audit_figure_placement(chapters, only=None):
    """절별로 '단락 → 그 뒤에 오는 삽화'를 펼쳐 본다.

    2026-07-22 사고: ch02 이론을 재편하면서 본문 단락은 옮겼는데 삽화의 afterParagraph는
    그대로 둬서, 질량유량 삽화가 1단락 뒤에, 거시/미시 삽화가 화학에너지 단락 뒤에 붙었다.
    앵커가 '범위 안'이기만 하면 빌드는 통과하므로 기계는 이걸 못 잡는다. 사람이 보라고 펼친다.

        python tools/audit_content.py --figures
    """
    head("7. 삽화 배치 지도 — 단락과 삽화가 실제로 짝이 맞는가")
    for ch, data in chapters.items():
        if only and ch != only:
            continue
        for section in data["theory"]["sections"]:
            paras = re.split(r"\n{2,}", section["content"])
            by_anchor = defaultdict(list)
            for fig in section.get("diagrams") or []:
                by_anchor[figure_anchor_index(paras, fig)].append(fig)
            # 복습 전제 카드도 빌드에서는 앵커로 센다(checks_content의 anchored 집합).
            # 2026-07-24: 여기서 빠뜨려 ch02 sec-start-from-mechanics에 없는 9단락 공백을
            # 보고했다 — anchorText 누락과 같은 부류(감사가 빌드보다 적게 본다).
            for pre in section.get("reviewPrerequisites") or []:
                by_anchor[figure_anchor_index(paras, pre)].append(
                    {"id": pre.get("id", "복습 전제"), "title": "(복습 전제 카드)"})
            print(f"\n-- {ch} {section['id']} ({len(paras)}단락, "
                  f"삽화 {len(section.get('diagrams') or [])}건)")
            gap = 0
            worst = 0
            for i, para in enumerate(paras, 1):
                text = re.sub(r"\s+", " ", para).strip()
                mark = " " if i not in by_anchor else "*"
                print(f"   {mark}{i:>3} | {text[:66]}")
                if i in by_anchor:
                    for fig in by_anchor[i]:
                        print(f"        └─ [{fig.get('id')}] {str(fig.get('title',''))[:60]}")
                    gap = 0
                else:
                    gap += 1
                    worst = max(worst, gap)
            if worst >= DENSITY_LIMIT:
                print(f"   [글 밀도] 삽화 없이 이어지는 최장 구간 {worst}단락 "
                      f"(한계 {DENSITY_LIMIT})")


DENSITY_LIMIT = 6


# 난이도 어휘는 **빌드와 같은 등록부에서 가져온다**(뷰어 diffLabel ↔ 빌드 검사 ↔ 이 감사).
#
# 열린 날 2026-07-26 — 세 곳이 각자 어휘를 들고 있다 표류했고, thermo·math **두 과목이
# 각자 이 결함을 발견해 반대 어휘로 고치는** 2차 사고까지 났다(merge 충돌). 이 감사만 어휘가
# 어긋나면 변별 문제를 '난이도 미표기'로 신고하고 **'변별 0건'이라고 오보**한다 — 실제로 그
# 오보가 세션 인계 메모에까지 실렸다. 하드코딩을 지우는 것이 유일한 방지책이므로,
# 목표 비중도 이름이 아니라 **등록부의 순서**로 쓴다(어휘가 바뀌어도 따라온다).
DIFFICULTY_TIERS = PROBLEM_DIFFICULTIES
DISCRIMINATING = DIFFICULTY_TIERS[-1]
DIFFICULTY_TARGET = {DIFFICULTY_TIERS[0]: 0.30, DIFFICULTY_TIERS[1]: 0.50, DISCRIMINATING: 0.20}


def difficulty_mix(problems):
    """연습문제의 난이도 분포를 (개수 dict, 비율 dict)로 돌려준다."""
    counts = {tier: 0 for tier in DIFFICULTY_TIERS}
    for p in problems or []:
        tier = p.get("difficulty")
        if tier in counts:
            counts[tier] += 1
    total = sum(counts.values())
    ratios = {t: (counts[t] / total if total else 0.0) for t in DIFFICULTY_TIERS}
    return counts, ratios


def audit_difficulty(chapters, tolerance=0.12):
    """난이도 비중이 AGENTS의 30/50/20에서 벗어나면 보고한다 (2026-07-26 신설).

    왜 필요한가: 사람이 '적당히 쉬운 것 몇 개, 어려운 것 몇 개'로 만들면 쉬운 쪽으로 쏠린다.
    실측 2026-07-26 — ch01 연습 9문제 중 advanced 0건, ch02 10문제 중 1건이었다.
    기준을 문서에만 두면 다음 챕터에서 또 쏠리므로 여기서 센다.
    """
    head("6. 연습문제 난이도 분포 (목표 30/50/20 ± " + str(int(tolerance * 100)) + "%p)")
    for ch, d in chapters.items():
        problems = d.get("problems") or []
        if not problems:
            print(f"  {ch}: 연습문제 없음 — 건너뜀")
            continue
        counts, ratios = difficulty_mix(problems)
        total = sum(counts.values())
        line = " · ".join(f"{t} {counts[t]}({ratios[t]*100:.0f}%)" for t in DIFFICULTY_TIERS)
        off = [t for t in DIFFICULTY_TIERS if abs(ratios[t] - DIFFICULTY_TARGET[t]) > tolerance]
        mark = "  [벗어남: " + ", ".join(off) + "]" if off else ""
        print(f"  {ch}: 총 {total} — {line}{mark}")
        if counts[DISCRIMINATING] == 0:
            print(f"      ⚠ 변별({DISCRIMINATING}) 0건 — 방법 선택·함정·역방향을 묻는 축 C 문제가 없다")
        unlabeled = [p.get("id") for p in problems if p.get("difficulty") not in DIFFICULTY_TIERS]
        if unlabeled:
            print(f"      ⚠ 난이도 미표기: {unlabeled}")


# ------------------------------------------------- 7. 이해도 점검 답 길이
# 상한 근거 (열린 날 2026-07-29). 사용자 지적:
#   *[발화 생략]*
# 품질 계약 §2는 '완결된 문장'만 요구하고 **길이를 말하지 않았다.** 그래서 성실하게 쓸수록
# 길어졌고, 복습용 장치가 서술형 답안이 됐다. 용도에서 상한을 역산해 못 박는다.
CHECK_ANSWER_MAX = {"recall": 60, "connect": 160, "explain": 200}


def visible_answer_len(ans):
    """**독자가 화면에서 읽는 글자 수**. 마크업은 세지 않는다 (열린 날 2026-08-08).

    **무엇이 새어나갔나.** 이 자는 `len(ans)` 를 그대로 썼다 — 즉 `\\(T = \\frac{1}{2}mv^{2}\\)`
    를 **25자**로 센다. 화면에는 `T = 1/2 mv²` 로 8자쯤 나오는데도 그렇다. 그래서 수식이 든
    답은 **글이 짧아도 상한을 넘고**, 수식이 없는 답만 실제 길이로 평가됐다. 상한의 근거가
    *[발화 생략]* 인데 **읽히지 않는 것을 세고 있었으므로 재는 대상이 어긋난 것**이다.

    실측(2026-08-08 동역학): 신고 6건 중 **3건이 이 오탐**이었다 — `cc-f-angular-recall` 은
    67자로 신고됐지만 화면 글자는 34자다(수식 마크업 39자 중 33자가 안 보인다).
    자를 안 고치고 데이터를 줄이면 **멀쩡한 답에서 설명을 덜어내게 된다**(라벨 여백 자
    391건 중 91건이 오탐이던 선례와 같은 부류 — `test_label_gap_respects_container`).

    완화가 아니다. 상한값 60·160·200 은 그대로이고, **세는 대상만** 마크업에서 화면 글자로
    바꾼다. 렌더 근사는 뷰어 `renderMath` 를 본뜬 `_plain_math_text` 를 그대로 쓴다 —
    여기서 따로 만들면 두 벌이 되어 갈라진다.

    잠금: `test_checks.py::test_check_answer_length_counts_visible_chars`.
    """
    text = str(ans or "")
    text = re.sub(r"\\\((.*?)\\\)", lambda m: _plain_math_text(m.group(1)), text, flags=re.S)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)      # 굵게 표시는 글자가 아니다
    return len(re.sub(r"\s+", " ", text).strip())


def audit_check_length(chapters):
    head("7. 이해도 점검 답 길이 (용도 대비 과다)")
    print(f"상한: " + " · ".join(f"{k} {v}자" for k, v in CHECK_ANSWER_MAX.items())
          + "  (마크업 제외 · 화면에 보이는 글자로 센다)")
    total = 0
    for ch, d in chapters.items():
        rows = []
        for coll, items in groups(d).items():
            for it in items:
                for c in it.get("comprehensionChecks") or []:
                    stage = c.get("stage") or "?"
                    ans = (c.get("answer") or "").strip()
                    cap = CHECK_ANSWER_MAX.get(stage)
                    shown = visible_answer_len(ans)
                    if cap and shown > cap:
                        rows.append((c.get("id") or "?", stage, shown, len(ans), cap, ans[:46]))
        if not rows:
            continue
        print(f"\n-- {ch}: 상한 초과 {len(rows)}건")
        for cid, stage, n, raw, cap, head_txt in sorted(rows, key=lambda r: -r[2]):
            print(f"   {cid:22} {stage:8} {n:4}자 (상한 {cap} · 원문 {raw}자)  {head_txt}…")
        total += len(rows)
    print(f"\n총 {total}건")
    return total


def main():
    chapters = {ch: load(ch) for ch in CHAPTERS}
    if "--checks" in sys.argv:
        audit_check_length(chapters)
        print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")
        return
    if "--difficulty" in sys.argv:
        audit_difficulty(chapters)
        print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")
        return
    if "--figures" in sys.argv:
        only = next((a for a in sys.argv[1:] if a in CHAPTERS), None)
        audit_figure_placement(chapters, only)
        print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")
        return
    # 독자성 개편은 §5a를 반복해 돌리게 된다. 전체 출력(250줄)을 매번 다시 읽으면
    # 문맥만 태우므로 그 절만 뽑는 길을 둔다(2026-07-24 ch01 개편 중 신설).
    if "--originality" in sys.argv:
        audit_originality(chapters)
        print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")
        return
    audit_scope(chapters)
    audit_sigfig(chapters)
    audit_notation(chapters)
    audit_middot(chapters)
    audit_terms(chapters)
    audit_originality(chapters)
    audit_difficulty(chapters)
    audit_check_length(chapters)
    audit_rule_reach()
    print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")


if __name__ == "__main__":
    main()
