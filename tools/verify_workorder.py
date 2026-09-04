# -*- coding: utf-8 -*-
"""워크오더 수용 게이트.

주의: **읽기 전용이 아니다.** 기본 동작에 `build_site.py --all`이 포함되므로 `site/**` 산출물을 쓴다.
데이터·문서는 읽기만 한다. 무승인 허용은 "프로젝트 내부의 고정 검증·빌드 절차"라서지
부작용이 없어서가 아니다 — `--no-build`나 프로젝트 밖 경로는 허용 대상이 아니다.

에이전트가 "완료했다"고 주장하기 **전에** 스스로 돌린다. exit 0 이 아니면 완료라고 쓰지 못한다.
사람이 파일을 하나씩 열어봐야만 잡히던 결함을 기계가 잡게 하는 것이 목적이다.

    python tools/verify_workorder.py data/열역학/xxx.workorder.md
    python tools/verify_workorder.py data/열역학/xxx.workorder.md --no-build

검사 항목
  1. `## 항목별 판정` 의 모든 항목에 `판정:` 이 있는가      (규칙 8을 건너뛰지 않았는가)
  2. 진행 기록이 "바꿨다"고 적은 파일이 **실제로** 바뀌었는가 (완료 기록 ≠ 반영 방지)
  3. 실제로 바뀌었는데 기록에 없는 파일이 있는가            (미신고 변경)
  3-B. JSON의 SVG 변경이 신고됐고 PNG 해시 증거+육안 선언이 있는가
  3-C. 브라우저 차단 시 대체 검증과 브라우저 전용 잔여를 분리했는가
  4. 노랑 구역 판단이 있었다면 `## 자율 판단 기록` 이 있는가
  5. 빌드 통과                                            (--no-build 로 생략)
  6. 회귀 테스트 통과
  7. `## 완료 기준` 에 적은 명령을 **실제로 돌려** exit 0 인가

왜 필요한가: 2번 유형(완료라고 적었는데 파일엔 없음)이 이 프로젝트에서 최소 3회 발생했고
(pascal-hydraulic-lift 2회, 축일 화살촉 1회), 매번 사람이 파일을 열어봐야만 발견됐다.

7번은 **XSanity 개조 프로젝트에서 역이식**했다(`_modding/scripts/verify_workorder.py`, 2026-08-06).
AGENTS.md 는 *"완료 기준은 산문이 아니라 exit 0 이어야 하는 명령으로 적는다"* 를 요구해 왔는데,
⑴ 그 절이 있는지 ⑵ 명령이 들어 있는지 ⑶ 그 명령이 실제로 통과하는지를 **아무도 안 봤다.**
즉 게이트가 *자기가 요구한 것* 을 검사하지 않았다. 산문으로만 적힌 완료 기준은 누구도 판정할 수
없으므로 `NO_CRITERIA` 는 경고가 아니라 **실패**다(경고로 열어 두면 경고 더미에 묻힌다).
"""
import hashlib
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 진행 기록에서 파일 경로로 인정할 확장자 (문장 속 백틱 단어와 구분하기 위함)
# 공백 허용(2026-07-27): 과목 폴더 "공학수학 1"처럼 디렉터리명에 공백이 있으면
# 어떤 표기로도 신고가 불가능했다 — 열역학(공백 없음)에서는 안 드러난 사각지대.
PATH_RE = re.compile(r"`([A-Za-z0-9_\-./가-힣 ]+\.(?:json|html|py|ps1|md|css|js))`")

errors = []
warnings = []


def claimed_paths(progress):
    """진행 기록에서 '변경했다'고 신고한 파일 경로 집합.

    - 백틱으로 감싼, 알려진 확장자의 경로만 인정한다(PATH_RE).
    - 워크오더 자신은 제외.
    - 공백 허용(과목 폴더 "공학수학 1")의 부작용 차단: `python tools/x.py` 같은
      백틱 명령의 첫 토큰이 인터프리터/명령이면 경로 신고가 아니다.
    """
    claimed = set(PATH_RE.findall(progress))
    claimed = {c for c in claimed if not c.endswith(".workorder.md")}
    return {c for c in claimed
            if c.split(" ", 1)[0] not in ("python", "py", "powershell", "git")}


def git(*args):
    out = subprocess.run(["git", "-c", "core.quotepath=false"] + list(args), cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout.strip()


def section(text, title):
    """'## title' 부터 다음 '## ' 직전까지."""
    m = re.search(r"^##\s+" + re.escape(title) + r"\s*$", text, re.M)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# ---- 완료 기준 실행에 쓰는 것들 (7번 항목) ----
# 표제가 `## 완료 기준 (전부 명령으로 판정)` 처럼 꼬리를 달고 있는 워크오더가 실재하므로
# section() 의 정확 일치로는 못 찾는다 — 여기만 접두 일치를 쓴다.
CRITERIA_SEC = re.compile(r"^##\s+완료\s*기준.*$", re.M)
FENCE_RE = re.compile(r"```(?:bash|sh|console|powershell)?\n(.*?)```", re.S)
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
ENV_PREFIX = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S*)\s+")


def strip_comment(line):
    """따옴표 **밖**의 `#` 부터를 주석으로 떼어낸다.

    완료 기준은 `python tools/x.py    # exit 0 이어야 한다` 처럼 설명을 달아 적는다.
    그대로 넘기면 argparse 가 `unrecognized arguments` 로 죽어서 **스크립트는 멀쩡한데
    게이트만 실패하는** 가짜 실패가 난다. 단 `python -c "... '#' ..."` 의 `#` 은 명령의 일부다.
    """
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return line[:i].strip()
    return line.strip()


def criteria_commands(text):
    """`## 완료 기준` 에서 실행 가능한 명령만 뽑는다. 절이 없으면 None.

    두 표기를 모두 받는다 — 이 리포의 실제 관례는 **백틱 불릿**이고
    (`- \\`python tools/build_site.py --all\\` exit 0`), 펜스(```bash)도 쓰인다.
    한쪽만 받으면 기존 77개 워크오더가 통째로 `NO_CRITERIA` 가 된다(실측).
    """
    m = CRITERIA_SEC.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    body = rest[: nxt.start()] if nxt else rest

    candidates = []
    for block in FENCE_RE.findall(body):
        candidates += block.splitlines()
    candidates += BACKTICK_RE.findall(FENCE_RE.sub("", body))

    cmds = []
    for raw in candidates:
        cmd = strip_comment(raw)
        if not cmd:
            continue
        # 환경변수 접두(`PYTHONIOENCODING=utf-8 python …`)를 벗겨 낸 뒤 첫 토큰을 본다.
        # 산문·파일 경로·필드 이름이 백틱에 들어 있는 경우가 훨씬 많으므로 화이트리스트로 좁힌다.
        probe = ENV_PREFIX.sub("", cmd, count=1)
        if probe.split(" ", 1)[0] not in ("python", "py"):
            continue
        if cmd not in cmds:
            cmds.append(cmd)
    return cmds


def run_criterion(cmd, timeout=1800):
    """완료 기준 한 줄을 실제로 돌린다. (exit code, 마지막 출력 줄)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    while True:
        m = ENV_PREFIX.match(cmd)
        if not m:
            break
        env[m.group(1)] = m.group(2)
        cmd = cmd[m.end():]
    proc = subprocess.run(cmd, shell=True, cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)
    tail = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
    return proc.returncode, (tail[-1][:110] if tail else "")


def _iter_diagrams(node):
    if isinstance(node, dict):
        for d in node.get("diagrams") or []:
            if isinstance(d, dict) and d.get("id") and d.get("svg"):
                yield d
        for v in node.values():
            yield from _iter_diagrams(v)
    elif isinstance(node, list):
        for v in node:
            yield from _iter_diagrams(v)


def render_review_declared(progress, figure_id):
    """진행 기록에 `렌더 검수: <figure-id> / 육안 수용` 선언이 있는가.

    다른 삽화의 선언이 이 삽화를 대신 인정하지 않도록 id를 정확히 건다(\\b 경계).
    """
    if not progress:
        return False
    return bool(re.search(r"렌더 검수:\s*" + re.escape(figure_id) + r"\b[^\n]*육안 수용", progress))


SPEC_KEYS = ("학습 목적", "형상", "구도", "라벨", "삽입 위치")


def figure_spec_missing(text, figure_ids):
    """사양 없이 손댄 삽화 id 목록. **형상 타당성 대신 사양의 존재를 강제한다.**

    판정: 워크오더 어딘가에 그 삽화 id가 나오고, 그 근처(같은 문서의 `사양`/`spec`
    표제가 붙은 블록)에서 `SPEC_KEYS` 중 **2개 이상**이 언급되면 사양이 있는 것으로 본다.
    id만 나열한 표는 통과시키지 않는 것이 목적이다.
    """
    spec_blocks = re.findall(r"^#{2,4}[^\n]*(?:사양|spec)[^\n]*\n(.*?)(?=^#{1,4}\s|\Z)",
                             text, re.M | re.S | re.I)
    pool = "\n".join(spec_blocks)
    missing = []
    for figure_id in figure_ids:
        block = pool if re.search(re.escape(figure_id), pool) else ""
        if not block:
            missing.append(figure_id)
            continue
        if sum(1 for key in SPEC_KEYS if key in block) < 2:
            missing.append(figure_id)
    return missing


def browser_block_mentioned(progress):
    """Whether progress records a browser/local-page access failure or visual omission."""
    if not progress:
        return False
    return bool(re.search(
        r"(?:브라우저|localhost)[^\n]*(?:차단|정책|접근\s*불가|사용\s*불가|열지\s*못|"
        r"보지\s*못|못\s*봄|미검증)",
        progress,
    ))


def browser_block_record_issues(progress):
    """A browser-policy block must be split into fallback proof and browser-only residue.

    Opened 2026-07-24: repeated workorders used one broad "localhost blocked" line,
    even when SVG geometry had a complete PNG proof or static contracts had regression
    tests. That wording erased the distinction between verified and genuinely unverified.
    """
    if not browser_block_mentioned(progress):
        return []
    issues = []
    if not re.search(r"대체 검증:\s*\S", progress):
        issues.append("브라우저 차단 기록에 `대체 검증:`이 없음 — PNG·정적 검사로 확인한 범위를 분리할 것")
    if not re.search(r"브라우저 전용 잔여:\s*\S", progress):
        issues.append("브라우저 차단 기록에 `브라우저 전용 잔여:`가 없음 — 실제 DOM만 가능한 항목만 남길 것")
    return issues


def changed_svg_figures(base, changed):
    """(chapter, figure_id, 현재 SVG 해시) — 기준 커밋 대비 svg가 바뀐 삽화만.

    삽화를 고치면 해시가 바뀌고, 옛 렌더 증거는 자동으로 무효가 된다
    (다시 렌더해 눈으로 보게 강제한다). render_figure_review.py가 만드는 증거와 짝이다.
    """
    figures = []
    for path in sorted(p for p in changed if p.startswith("data/") and p.endswith(".json")):
        full = os.path.join(ROOT, path)
        if not os.path.isfile(full):
            continue
        try:
            current = json.load(open(full, encoding="utf-8"))
            prior_raw = git("show", f"{base}:{path}")
            prior = json.loads(prior_raw) if prior_raw else {}
        except (OSError, json.JSONDecodeError):
            continue
        before = {d["id"]: d["svg"] for d in _iter_diagrams(prior)}
        for d in _iter_diagrams(current):
            if before.get(d["id"]) != d["svg"]:
                figures.append((path, d["id"],
                                hashlib.sha256(d["svg"].encode("utf-8")).hexdigest()))
    return figures


def partition_svg_figures(svg_figures, claimed):
    """변경 SVG를 신고/미신고로 나눈다.

    열린 날: 2026-07-26 — 3-B를 신고 파일에만 적용한 뒤, SVG를 바꾸고 파일을
    신고하지 않으면 WARN만 남고 렌더 증거 게이트를 통째로 건너뛸 수 있었다.
    병렬 워크오더 오탐을 막는 기존 범위 축소는 유지하되 미신고 SVG만 ERROR로 올린다.
    """
    normalized = {item.replace("\\", "/") for item in claimed}
    declared, undisclosed = [], []
    for figure in svg_figures:
        path = figure[0]
        target = declared if any(path == item or path.endswith(item)
                                 for item in normalized) else undisclosed
        target.append(figure)
    return declared, undisclosed


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_build = "--no-build" not in sys.argv
    if not args:
        print("사용법: python tools/verify_workorder.py <workorder.md> [--no-build]")
        return 2
    wo_path = args[0]
    if not os.path.isfile(wo_path):
        print(f"[FAIL] 워크오더를 찾을 수 없음: {wo_path}")
        return 2
    text = open(wo_path, encoding="utf-8").read()
    print(f"검증 대상: {wo_path}\n")

    # ---- 1. 항목별 판정 ----
    verdicts = section(text, "항목별 판정")
    if verdicts is None:
        errors.append("`## 항목별 판정` 절이 없다 — 규칙 8(분류·입장 표명)을 건너뛴 것")
    else:
        items = [l for l in verdicts.splitlines() if re.match(r"^\s*\d+\.", l)]
        if not items:
            errors.append("`## 항목별 판정` 파싱 결과 0건 — 각 항목을 `1. ... 판정:` 형식으로 작성할 것")
            print("   파싱 실패 원인: 번호 목록(`1.`) 형식의 항목을 찾지 못함")
        missing = [l.strip()[:60] for l in items if "판정:" not in l]
        print(f"1. 항목별 판정: {len(items)}건 중 판정 누락 {len(missing)}건")
        for l in missing:
            errors.append("판정 누락 — " + l)

        # ---- 1-B. 전부 수용이면 경고 (규칙 8의 '반박 0 = 경고 신호'를 기계화) ----
        # 열린 날: 2026-07-26 / 무엇이 새어나갔는지: 규칙 8은 "배치 끝에 결함·설계판단·반박을
        # 세어 보고하고, 설계 판단이 있는데 반박 0이면 경고 신호"라고 요구하는데, 그 카운트를
        # 내지 않아도 아무것도 막지 않았다. 실제로 여러 배치에서 카운트가 통째로 생략됐고
        # 판정이 전부 '수용'으로 흘렀다(사용자 지적: "반박에 대한 힘이 많이 줄은 것 같다").
        # 문서에만 있고 기계가 안 보는 규칙은 잊으면 그대로 통과한다 — 그래서 여기서 센다.
        # 굵게(**조건부**)로 적는 것이 이 리포의 실제 관례다 — 별표를 건너뛰지 않으면
        # 전부 0으로 세어 게이트가 조용히 무력해진다(2026-07-26 첫 실행에서 실측).
        design = [l for l in items if re.search(r"판정:\s*\**\s*(수용\(설계|조건부)", l)]
        pushback = [l for l in items if re.search(r"판정:\s*\**\s*(반박|조건부|수용\(축소)", l)]
        print(f"1-B. 분류: 항목 {len(items)} · 설계판단 {len(design)} · 반박/조건부 {len(pushback)}")
        if design and not pushback:
            warnings.append(
                "설계 판단이 " + str(len(design)) + "건인데 반박·조건부가 0건 — 규칙 8의 경고 신호다. "
                "정말 전부 타당했다면 왜 그런지 한 줄씩 근거를 남길 것(받아적기 모드 점검)")

    # ---- 기준 커밋 ----
    base_sec = section(text, "기준 커밋")
    base = None
    if base_sec:
        m = re.search(r"\b([0-9a-f]{7,40})\b", base_sec)
        if m:
            base = m.group(1)
    if not base:
        warnings.append("`## 기준 커밋` 이 없어 HEAD~1 기준으로 비교한다 (여러 커밋에 걸친 작업이면 부정확)")
        base = "HEAD~1"

    changed = set(filter(None, git("diff", "--name-only", base).splitlines()))
    # -uall: 미추적 파일을 개별로 나열한다. 기본 --porcelain은 새 디렉터리를 'tools/buildlib/'처럼
    # 접어서 보고하므로, 그 안의 신규 파일이 전부 "변경 없음"으로 오판된다(2026-07-21 실제 오탐).
    changed |= {l[3:].strip().strip('"')
                for l in git("status", "--porcelain", "-uall").splitlines() if l[3:].strip()}
    changed = {c for c in changed if c}

    # ---- 2·3. 주장한 변경 vs 실제 변경 ----
    progress = section(text, "진행 기록")
    if progress is None:
        errors.append("`## 진행 기록` 절이 없다")
        claimed = set()
    else:
        claimed = claimed_paths(progress)

    if progress is not None and not claimed:
        print("   파싱 실패 원인: 진행 기록에서 백틱으로 감싼 파일 경로를 찾지 못함")

    print(f"2. 주장한 변경 파일 {len(claimed)}건 / 기준({base}) 이후 실제 변경 {len(changed)}건")
    if not claimed and changed:
        errors.append("진행 기록의 주장 변경 파일이 0건인데 실제 변경이 있음 — 경로를 백틱으로 기록할 것")
    for c in sorted(claimed):
        norm = c.replace("\\", "/")
        if not os.path.isfile(os.path.join(ROOT, norm)):
            errors.append(f"기록된 파일이 존재하지 않음 — {c}")
        elif not any(norm == ch or ch.endswith(norm) for ch in changed):
            errors.append(f"'바꿨다'고 기록했으나 실제 변경이 없음 — {c}")

    interesting = {c for c in changed
                   if c.startswith(("data/", "site/", "tools/")) and not c.endswith(".workorder.md")}
    undisclosed = {c for c in interesting
                   if not any(c == cl or c.endswith(cl.replace("\\", "/")) for cl in claimed)}
    print(f"3. 미신고 변경 {len(undisclosed)}건")
    for u in sorted(undisclosed):
        warnings.append(f"변경됐으나 진행 기록에 없음 — {u}")

    # ---- 3-B. SVG 래스터 증거 게이트 ----
    # 삽화 SVG를 바꿨으면 render_figure_review.py로 PNG+해시 증거를 만들고 실제 이미지를
    # 눈으로 봐야 한다(AGENTS 검증 절차). 증거(현재 SVG 해시와 일치) + 진행 기록의
    # `렌더 검수: <id> / 육안 수용` 선언이 둘 다 있어야 한다. localhost가 막혀도 이 경로를 쓴다.
    # 신고 SVG에만 증거를 요구해 병렬 워크오더 오탐을 막는다. 단 SVG를 고치고
    # 파일을 신고하지 않아 3-B 전체를 건너뛰는 경로는 ERROR로 닫는다.
    all_svg_figures = changed_svg_figures(base, changed)
    svg_figures, undisclosed_svg_figures = partition_svg_figures(all_svg_figures, claimed)
    print(f"3-B. SVG 래스터 증거: 변경 삽화 {len(svg_figures)}건")
    for chapter, figure_id, _svg_hash in undisclosed_svg_figures:
        errors.append(f"미신고 SVG 변경 — {chapter}:{figure_id} "
                      "(진행 기록에 챕터 JSON을 신고하고 렌더 증거를 남길 것)")
    for chapter, figure_id, svg_hash in svg_figures:
        stem = os.path.splitext(os.path.basename(chapter))[0]
        proof_json = os.path.join(ROOT, "review-artifacts", "figure-review", stem,
                                  figure_id + ".json")
        proof_ok = False
        try:
            proof = json.load(open(proof_json, encoding="utf-8"))
            png_path = os.path.join(os.path.dirname(proof_json), proof.get("png", ""))
            proof_ok = (proof.get("figure_id") == figure_id
                        and proof.get("svg_sha256") == svg_hash
                        and os.path.isfile(png_path))
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        declared = render_review_declared(progress, figure_id)
        if not proof_ok:
            errors.append(f"SVG 래스터 증거 없음/현재 SVG와 불일치 — {chapter}:{figure_id} "
                          "(render_figure_review.py로 다시 렌더할 것)")
        if not declared:
            errors.append(f"진행 기록에 `렌더 검수: {figure_id} / 육안 수용` 선언 없음 — {chapter}")

    # ---- 3-D. 삽화 사양 게이트 ----
    # 변경된 삽화마다 워크오더 본문에 **형상 사양**이 있어야 한다.
    # 열린 날 2026-07-24 — 사용자가 문풀·연습문제 삽화 9건을 한 번에 반려했다:
    # "물체가 왜 경사면 위에 없는데", "카트는 어디갔어", "저거 정말 fan이라 생각해?".
    # 새어나간 이유: 분업 정책은 *Claude가 사양을 주고 Codex가 좌표를 구현한다*인데
    # 실제로는 삽화 id와 한 줄 제목만 넘겼다. Codex는 형상을 **추측**했고, 그 추측이
    # 물리적으로 타당한지 판정하는 사람이 없었다. 형상 타당성은 기계가 볼 수 없으므로
    # **사양이 존재하는지**를 기계가 대신 강제한다. 사양이 있으면 반려 기준이 생긴다.
    spec_missing = figure_spec_missing(text, [fid for _c, fid, _h in svg_figures])
    print(f"3-D. 삽화 형상 사양: 대상 {len(svg_figures)}건 / 누락 {len(spec_missing)}건")
    for figure_id in spec_missing:
        errors.append(f"삽화 형상 사양 없음 — {figure_id} "
                      "(워크오더에 `### 사양` 아래로 학습 목적·형상·라벨·삽입 위치를 적을 것. "
                      "id와 제목만으로는 Codex가 형상을 추측하게 되고 반려 기준도 생기지 않는다)")

    # ---- 3-C. 브라우저 차단 범위 분리 ----
    block_issues = browser_block_record_issues(progress)
    print(f"3-C. 브라우저 차단 분류: {'해당 없음' if not browser_block_mentioned(progress) else ('통과' if not block_issues else '실패')}")
    errors.extend(block_issues)

    # ---- 4. 자율 판단 기록 ----
    auto = section(text, "자율 판단 기록")
    yellow_hint = re.search(r"판정:\s*(수용\(설계|조건부)", text)
    print(f"4. 자율 판단 기록: {'있음' if auto and auto.strip() else '없음'}")
    if yellow_hint and not (auto and auto.strip()):
        errors.append("설계·조건부 판정이 있는데 `## 자율 판단 기록` 이 비어 있다 "
                      "— 무엇을 왜 그렇게 정했는지 한 줄씩 남길 것")

    # ---- 5. 빌드 ----
    if do_build:
        r = subprocess.run([sys.executable, "tools/build_site.py", "--all"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        print(f"5. 빌드: {'통과' if ok else '실패'}")
        if not ok:
            errors.append("빌드 실패 — " + (r.stdout or r.stderr).strip().splitlines()[-1][:120])
    else:
        print("5. 빌드: 생략(--no-build)")

    # ---- 6. 회귀 테스트 ----
    # 빌드 통과는 '오늘 데이터가 깨끗하다'는 뜻일 뿐, 검사가 과거 결함을 여전히 잡는지는
    # 말해주지 않는다. 같은 겹침 결함이 3회 열린 원인이 정확히 이것이었다(2026-07-22).
    _tc = os.path.join(ROOT, "tools", "test_checks.py")
    if not os.path.isfile(_tc):
        print("6. 회귀 테스트: [skip] test_checks.py는 이 공개판에 포함되지 않음(원 프로젝트 전용 회귀 이력)")
    else:
        r = subprocess.run([sys.executable, "tools/test_checks.py"],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        print(f"6. 회귀 테스트: {'통과' if ok else '실패'}")
        if not ok:
            errors.append("회귀 테스트 실패 — 검사가 과거 결함을 더 이상 잡지 못한다: "
                          + (r.stdout or r.stderr).strip().splitlines()[-1][:120])

    # ---- 7. 완료 기준을 실제로 돌린다 ----
    # ★ `> 상태: 종결` 로 이 항목을 건너뛰던 길을 **같은 날 되돌렸다** (2026-08-08).
    #   넣은 이유는 *끝난 워크오더를 다시 돌릴 때 완료 기준이 무의미하다* 였는데, 그 전제가
    #   사라졌다 — **끝난 워크오더는 다시 돌리지 않는다**(AGENTS 「워크오더 수용 게이트」).
    #   전제가 사라진 뒤에도 남으면 그건 **완료 직전에 한 줄 적어 게이트를 끄는 길**이다.
    #   ★ 경고로 남기는 안(동역학 제안)보다 **제거**가 낫다 — 이 리포는 *"경고는 close 를 막지
    #   않고 경고 더미에 묻힌다"* 를 여러 번 적었고, strict 승격 체계가 생긴 이유가 그것이다.
    #   선언 자체는 사람이 읽는 표시로 남겨도 된다. 다만 **게이트에는 아무 힘이 없다.**
    cmds = criteria_commands(text)
    if cmds is None:
        errors.append("`## 완료 기준` 절이 없다 — 무엇이 통과이면 끝인지 아무도 판정할 수 없다")
    elif not cmds:
        errors.append("`## 완료 기준` 에 실행 가능한 명령이 없다(산문뿐) — "
                      "`python tools/...` 처럼 **exit 0 으로 판정되는 명령**으로 적을 것")
    else:
        ran = skipped = 0
        for cmd in cmds:
            # 자기 호출: 지금 돌고 있는 것이 그것이다. 그대로 실행하면 무한 재귀다.
            if "verify_workorder.py" in cmd:
                skipped += 1
                continue
            # 5·6 이 이미 돌린 것을 또 돌리지 않는다 (같은 판정을 두 번 세면 시간만 든다)
            if ("test_checks.py" in cmd) or (do_build and "build_site.py" in cmd):
                skipped += 1
                continue
            code, tail = run_criterion(cmd)
            ran += 1
            print(f"   [{'PASS' if code == 0 else 'FAIL'}] exit={code}  {cmd}")
            if tail:
                print(f"          {tail}")
            if code != 0:
                errors.append(f"완료 기준 실패(exit {code}) — {cmd}")
        print(f"7. 완료 기준: {len(cmds)}개 중 실행 {ran} · 생략 {skipped}"
              f"(자기 호출·5·6 중복)")

    print()
    for w in warnings:
        print("  [WARN] " + w)
    for e in errors:
        print("  [FAIL] " + e)

    if errors:
        print(f"\n✗ 수용 불가 — {len(errors)}건. 고친 뒤 다시 돌릴 것. '완료'라고 쓰지 말 것.")
        return 1
    print(f"\n✓ 수용 가능 (경고 {len(warnings)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
