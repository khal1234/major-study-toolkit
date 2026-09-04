# 절/삽화 id 참조 감사 — 읽기 전용.
#
# 왜 고정 도구인가: 절 id를 바꿀 때마다 "어디가 깨지는가"를 heredoc으로 뒤지면
# 임의 코드 실행이라 매번 승인이 뜬다(실행 규율 2). 같은 감사를 또 쓸 것이므로 도구로 승격한다.
#
# 사용:
#   python tools/audit_refs.py              전 챕터
#   python tools/audit_refs.py ch02         한 챕터
#   python tools/audit_refs.py ch02 --ids sec-first-law,sec-efficiency   특정 id만
#
# 판정 구분이 핵심이다:
#   [정의]   그 id가 선언된 곳            → 이름을 바꾸면 여기부터 바꾼다
#   [기계]   빌드/뷰어가 따라가는 참조     → 안 바꾸면 실제로 깨진다
#   [산문]   문서의 설명 문장             → 이력 기록이므로 보통 그대로 둔다
#   [깨짐]   [[chNN:id]] 인데 정의가 없음  → 즉시 고칠 것

import json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # io.TextIOWrapper 금지(이중 래핑)

ROOT = "data"
LINK_RE = re.compile(r"\[\[([A-Za-z0-9_]+):([^\]|/]+)(?:/([^\]|]+))?\|")
# 값이 id를 담는 '기계가 따라가는' 필드
MACHINE_FIELDS = {"relatedSections", "sectionStart", "sectionEnd", "sectionRef",
                  "relatedSection", "anchor", "target", "sectionId"}


def walk(node, path, fn):
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, path + [k], fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, path + [f"[{i}]"], fn)
    elif isinstance(node, str):
        fn(node, path)


def collect_ids(chapter):
    """이 챕터가 정의하는 id — 절·유도·삽화."""
    ids = {}
    def visit(s, path):
        if path and path[-1] == "id":
            owner = ".".join(p for p in path[:-1] if not p.startswith("["))
            ids[s] = owner
    walk(chapter, [], visit)
    return ids


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only_ids = None
    for a in sys.argv[1:]:
        if a.startswith("--ids"):
            only_ids = set(a.split("=", 1)[1].split(",")) if "=" in a else None
    # ★ 과목이 없는 워크트리(컨테이너 루트 · 공통 정본 main)에서는 «해당 없음» 이다.
    #   빌드는 2026-08-16 에 이 부류를 닫았는데 이 감사만 남아 FileNotFoundError 로 죽었다 —
    #   죽으면 close_report 가 그 자리에서 멈춘다. 「없어서 안 돈 것」과 「돌아서 0건」은 다르다.
    if not os.path.isdir(ROOT):
        print("[참조 감사] 해당 없음 — 이 워크트리에는 data/ 가 없다(공통 정본)")
        return
    subjects = [d for d in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, d))]

    for subj in subjects:
        base = os.path.join(ROOT, subj)
        all_chapters = sorted(f for f in os.listdir(base) if re.fullmatch(r"ch\d+\.json", f))
        chapters = all_chapters
        if args:
            chapters = [f for f in chapters if f[:-5] in args]
        if not chapters:
            continue

        # 링크의 chNN 태그를 검증하려면 출력 대상을 한 챕터로 좁혀도 정의 인덱스는
        # 전 챕터를 유지해야 한다. 그렇지 않으면 정상 교차 링크를 깨짐으로 오판한다.
        definitions = {}      # chapter -> {id: owner path}
        for f in all_chapters:
            ch = json.load(open(os.path.join(base, f), encoding="utf-8"))
            definitions[f[:-5]] = collect_ids(ch)

        defined = {}          # 선택 챕터의 id -> (chapter, owner path)
        for f in chapters:
            for i, owner in definitions[f[:-5]].items():
                defined[i] = (f[:-5], owner)

        # 기본값은 절·삽화 id만 본다 — 빈칸·이해도체크 id까지 넣으면 146개가 쏟아져 신호가 묻힌다.
        # 전부 보려면 --all.
        want_all = "--all" in sys.argv
        def is_target(owner):
            return owner.endswith("theory.sections") or owner.endswith("diagrams") \
                or owner.endswith("derivation.formulas")
        targets = {i: v for i, v in defined.items()
                   if (only_ids and i in only_ids) or (not only_ids and (want_all or is_target(v[1])))}

        # 전 파일 스캔
        refs = collections.defaultdict(list)   # id -> [(kind, file, where, sample)]
        broken = []
        for name in sorted(os.listdir(base)):
            p = os.path.join(base, name)
            if name.endswith(".json"):
                try:
                    data = json.load(open(p, encoding="utf-8"))
                except Exception as e:
                    print(f"  [skip] {name}: {e}")
                    continue

                def visit(s, path, name=name):
                    where = ".".join(x for x in path if not x.startswith("["))
                    for ch_tag, sec, sub in LINK_RE.findall(s):
                        if ch_tag not in definitions or sec not in definitions[ch_tag]:
                            broken.append((name, where, f"[[{ch_tag}:{sec}]]"))
                    field = path[-1] if path else ""
                    for i in targets:
                        if i not in s:
                            continue
                        if field == "id":
                            kind = "정의"
                        elif field in MACHINE_FIELDS or any(x in MACHINE_FIELDS for x in path):
                            kind = "기계"
                        elif f":{i}|" in s or f"[[{i}" in s:
                            kind = "기계"
                        else:
                            kind = "산문"
                        refs[i].append((kind, name, where, s[:60]))
                walk(data, [], visit)
            elif name.endswith(".md"):
                text = open(p, encoding="utf-8").read()
                for i in targets:
                    n = text.count(i)
                    if n:
                        refs[i].append(("산문", name, f"(md ×{n})", ""))

        print("=" * 78)
        print(f"  {subj} — id 참조 감사 (대상 {len(targets)}개)")
        print("=" * 78)
        for i in sorted(targets):
            rows = refs[i]
            by = collections.Counter(r[0] for r in rows)
            print(f"\n-- {i}   [{targets[i][0]} / {targets[i][1]}]")
            print(f"   정의 {by['정의']} · 기계 {by['기계']} · 산문 {by['산문']}")
            for kind, f, where, sample in rows:
                if kind == "기계":
                    print(f"     [기계] {f} | {where}")
        if broken:
            print("\n" + "!" * 78)
            print(f"  깨진 링크 {len(broken)}건 — 정의되지 않은 id를 가리킨다")
            for f, where, s in broken:
                print(f"     {f} | {where} | {s}")
        else:
            print("\n  깨진 링크 0건")
        print("\n(읽기 전용 감사 — 파일을 쓰지 않았다)")


if __name__ == "__main__":
    main()
