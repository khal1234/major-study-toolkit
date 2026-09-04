# -*- coding: utf-8 -*-
"""세션 비용 — **효율과 감수를 나란히** 잰다 (읽기 전용 · 신설 2026-08-15).

    python tools/audit_session_cost.py                  # 이 프로젝트, 최근 세션 1개
    python tools/audit_session_cost.py --sessions=5
    python tools/audit_session_cost.py --project=<경로>  # 다른 프로젝트
    python tools/audit_session_cost.py --all            # 프로젝트별 한 줄씩

**왜 이 자인가** (2026-08-15 사용자 판정):

    *"2마리 토끼를 동시에 잡아야 하거든. 정확도와 효율성. 효율 지킨다고 감수 시스템 암것도
    안 만들었다가 했던 얘기 또 하고 또하면 에이전트 할바에 그냥 채팅으로 했을거고, 감수 시스템
    열나게 만든다고 효율 개판으로 만들면 일을 할려고 에이전트 하는게 아니라 일을 위한 일
    구경하려고 에이전트 돌리는 꼴"*

★★ **그래서 한 숫자로 합치지 않는다.** 「종합 점수」를 내면 **한쪽을 팔아 다른 쪽을 살 수
   있게 되고**, 그 순간 두 마리가 아니라 한 마리가 된다. 두 블록을 **같은 화면에 따로** 찍고,
   판정은 사람이 한다.
★ **고치지 않는다. 막지도 않는다** — 언제나 exit 0. `check_floor` 와 같은 규율이다:
   진단이 처방을 겸하면 «재 보니 다 돼 있다» 는 결론이 나올 수 없다.
★ **도메인을 모른다.** 프로젝트 이름·빌드 명령·과목을 하나도 안 박았다. 게이트는 **이름의
   일반 낱말**로만 센다(아래 `GATE_HINTS`) — 그래서 이 값은 **판정이 아니라 셈**이다.

**무엇을 재나.** 이 계통이 실측으로 이미 정해 둔 것을 따른다
(`규칙/CLAUDE.md` 「토큰 낭비 실측 목록」 · `도구/audit_tool_parallelism.py`):

  효율 ⑴ **도구 출력 크기** — *"비싼 것은 왕복 수가 아니라 도구 출력의 크기다"* 가 이 계통의
        실측 결론이라 **가장 먼저** 찍는다. 어느 도구·어느 명령이 컸는지까지 낸다.
      ⑵ **캐시 재생성 비율** — 재생성된 입력은 **문맥을 다시 사는 것**이다. 읽기(cache_read)는
        싸고 재생성은 비싸다.
      ⑶ **같은 파일 재읽기** — 이미 문맥에 있는 것을 다시 넣는 자리.
      ⑷ **묶음률** — `audit_tool_parallelism` 과 같은 정의. ★ **목표치로 쓰지 말 것**
        (의존이 있는 호출까지 묶게 된다).

  감수 ⑸ **편집 횟수**와 ⑹ **게이트 횟수**, 그리고 ⑺ **편집당 게이트.**
      ★ 이 셋이 없으면 효율 숫자는 **거짓말을 한다** — 아무것도 검증 안 하면 언제나 싸다.
        *"편집 30번에 게이트 0번"* 이 이 자가 잡으려는 바로 그 화면이다.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 「진행 중계」는 **여기서 안 센다 — 막는 자에게서 가져다 쓴다** (합침 2026-08-15) ──
#
# 전에는 이 파일이 같은 것을 자기 코드로 또 셌다. 둘 다 맞는 값을 내고 있었지만
# **판정선이 두 벌이면 갈린다** — 한쪽에서 「중계」의 뜻을 고치면 다른 쪽은 조용히 옛 뜻으로
# 남는다. 이 계통이 이미 같은 형태로 닫아 둔 부류다(`slash_fraction_spans` 를 검사와 처방
# 도구가, `check_answer_sentences` 를 빌드와 감사가 나눠 쓴다).
#
# ★ **없으면 「못 잰다」고 말한다 — 폴백으로 한 벌 더 두지 않는다.** 폴백은 이 폴더가
#   반복해 잡아 온 함정이고(*"폴백으로 하나만 넣어 두기"*), 여기서 두면 합친 것이 그대로
#   되돌아온다. 옆에 없다는 사실 자체가 **미러·도입이 안 돈다는 신호**다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from check_narration import Tally as NarrationTally
except ImportError:
    NarrationTally = None

ROOT = Path.home() / ".claude" / "projects"
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# ★ 일반 낱말만 쓴다 — 프로젝트 도구 이름을 박으면 그 프로젝트에서만 도는 자가 된다.
GATE_HINTS = ("test", "check", "audit", "verify", "lint", "build", "scan",
              "pytest", "regress", "게이트", "검사", "감사", "점검")
# ★ **훑기 명령은 뺀다.** `check_*` 를 grep 하는 것은 게이트를 «돌린» 것이 아니라 «찾은» 것이다.
INSPECT = ("grep", "rg", "cat", "head", "tail", "ls", "findstr", "sed", "awk",
           "less", "wc", "type", "select-string", "get-content")


GATE_LIST_NAMES = ("게이트-목록.txt", "gates.txt")


def gate_bases(cwd):
    """꼬리표를 **어디서 찾나.** `cwd` 와 **git 리포 뿌리** 둘 다에서 본다(각각 한 칸 아래까지).

    ★ 왜 `cwd` 만으로는 안 되나 (2026-08-15, 전공정리 실측 되먹임): 세션이 **워크트리 컨테이너**
      에서 열리면 리포 루트가 한 칸 아래라, 거기서 또 한 칸(`docs/`)이면 **두 칸이 되어 샌다.**
      그쪽은 파일을 리포 루트로 옮겨 닫았는데, 그러면 **각 프로젝트가 「어디 둬야 하는지」를
      외워야 한다** — 이 폴더가 없애려는 바로 그 형태다. 자 쪽에서 닫는 것이 맞다.
    ★ 답은 이 저장소에 이미 있다 — `adopt_ledger.project_key` 가 같은 물음(«이 리포의 뿌리가
      어디냐»)을 `git rev-parse --git-common-dir` 의 부모로 풀었다. **같은 질문에 답하는 자가
      둘이면 갈리므로** 같은 판정선을 쓴다. git 이 아니면 조용히 `cwd` 만 쓴다.
    """
    bases, seen = [], set()
    for cand in (Path(cwd), git_root(cwd)):
        if cand and cand.is_dir() and cand.resolve() not in seen:
            seen.add(cand.resolve())
            bases.append(cand)
    return bases


def git_root(cwd):
    """`git rev-parse --git-common-dir` 의 부모 — 워크트리든 본체든 같은 값이다."""
    try:
        r = __import__("subprocess").run(
            ["git", "-C", str(cwd), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    common = Path(r.stdout.strip())
    if not common.is_absolute():
        common = Path(cwd) / common
    return common.resolve().parent


def gate_tags(cwd):
    """`명령조각 | 사유` — **프로젝트가 선언한 게이트.** 있으면 이름 어림을 **대체**한다.

    ★★ **이 함수가 없는 채로 독스트링이 「있다」고 적고 있었다** (2026-08-15에 발견).
      「소비 안 되는 설정 키 = 거짓 설정」(`방지장치-설계.md`)의 문서판이다 — 읽는 사람은
      창구가 있는 줄 알고 파일을 만들지만 아무 일도 안 일어난다.
    ★ 왜 필요한가: 이름 어림은 **양쪽으로 틀린다.** 부풀리는 쪽은 이미 봤고(`zone_egg_scan
      --scan`), **깎는 쪽**도 실측으로 나왔다 — 이 계통의 **주 게이트인 `close_report.py` 는
      이름에 hint 낱말이 하나도 없어 한 번도 안 세어졌다.** 낱말을 더 넣는 것은 부풀림을
      키우므로, 답은 **그 프로젝트가 자기 게이트를 선언하는 것**이다(= 자료의 꼬리표).
    ★ 사유 없는 줄은 안 친다 — 이 폴더가 예외 대장에 쓰는 판정선과 같다.
    """
    out, seen = [], set()
    for base in gate_bases(cwd):
        for name in GATE_LIST_NAMES:
            for hit in sorted(base.glob(name)) + sorted(base.glob("*/" + name)):
                if not hit.is_file() or hit.resolve() in seen:
                    continue
                seen.add(hit.resolve())
                for raw in hit.read_text(encoding="utf-8",
                                         errors="replace").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    frag, sep, why = line.partition("|")
                    if sep and frag.strip() and why.strip():
                        out.append(frag.strip().lower())
    return out


def gate_signature(command, tags=None):
    """게이트로 **셀 후보**와 그 서명. `None` 이면 안 센다. **판정이 아니라 셈이다.**

    ★★ **이 저장소가 이미 이름 붙인 부류를 자가 그대로 밟았다** (2026-08-15, XSanity 되먹임).
      `변경일지.md` 2026-08-14 — *"분류의 근거는 이름이 아니라 **자료가 들고 있는 꼬리표**여야
      한다"* (리믹스 채널 사고: 제목에 「리믹스」가 든 아케이드 곡 2개가 들어오고 그 말이 없는
      28곡이 빠졌다). 첫 판이 이름 문자열로만 세서 XSanity 에서 이렇게 부풀었다:
      **`zone_egg_scan.py --scan` 48회**(화면 판독기다) · **`build_route.py` 7회**(자료 생성이다) ·
      **`check_*`·`audit_*` 를 grep 한 명령**까지.
    ★ 꼬리표가 없는 자리라 **완전히 고칠 수는 없다.** 대신 둘을 한다 —
      ⑴ **훑기 명령을 뺀다**(찾은 것과 돌린 것은 다르다) ⑵ 남은 것은 **무엇을 돌렸는지 서명을
      같이 찍는다.** 숫자만 내면 그 숫자가 도장이 되고, 서명을 보이면 사람이 눈으로 걷어낸다.
    ★ 프로젝트가 **`게이트-목록.txt`(`명령조각 | 사유`)** 를 두면 그것이 꼬리표가 되어
      이름 어림을 **대체**한다 — 선언한 것만 센다.
    """
    low = command.strip().lower()
    if not low:
        return None
    # ★★ **힙독 본문은 명령이 아니라 «자료» 다** (2026-08-15, 전공정리 되먹임으로 드러남).
    #   `cat >> NOTES.md <<'EOF' … 검사 … EOF` 를 통째로 훑으면 **문서 산문 속 낱말**이 게이트로
    #   세어진다 — 실측 서명에 `★` · `**9개**` · `검사` · `**반대로` 가 그대로 나왔다.
    #   커밋 메시지(`git commit -F - <<'MSG'`)도 같다. **이 부류를 세 번째로 밟았다** —
    #   「분류의 근거는 자료가 들고 있는 꼬리표」의 반대편, 즉 «자료를 명령으로 읽은» 자리다.
    cut = re.search(r"<<-?\s*['\"]?\w+", low)
    if cut:
        low = low[:cut.start()]
    if not low.strip():
        return None
    # ★ **조각을 하나씩 본다 — 통째로도, 한 조각만도 아니다.**
    #   `cd X && grep check_*` 는 머리가 `cd` 라 훑기 필터를 그냥 지나가고(첫 판이 실제로
    #   grep 을 게이트로 셌다), 그렇다고 «마지막 조각»만 보면 `python test.py | tail` 의
    #   마지막이 `tail` 이라 **진짜 게이트가 통째로 사라진다**(고치다 실제로 38→7 이 됐다).
    #   파이프는 **앞**이 명령이고 `&&` 는 **뒤**가 명령이라, 어느 한쪽을 고르면 반드시 틀린다.
    parts = [low]
    for sep in ("&&", ";", "|"):
        parts = [q.strip() for p in parts for q in p.split(sep)]
    for seg in parts:
        if not seg:
            continue
        head = seg.split()[0].lstrip("(&|;")
        if head in INSPECT:
            continue
        # 선언된 꼬리표가 있으면 **그것만** 본다 — 이름 어림은 그때 아예 안 쓴다.
        if not (any(t in seg for t in tags) if tags
                else any(h in seg for h in GATE_HINTS)):
            continue
        # 서명 = 실제로 돌린 스크립트. 사람이 이걸 보고 걷어낸다.
        for tok in seg.replace('"', " ").replace("'", " ").split():
            if tok.endswith((".py", ".ps1", ".sh", ".js")):
                return Path(tok).name
        # 변수 대입(`S="C:/…/floortest"`)이 머리면 그대로 찍지 않는다 — 홈 경로가 출력에 샌다.
        return Path(seg.split()[0].split("=")[-1].strip('"\'')).name[:40]
    return None


def slug(path):
    """`~/.claude/projects` 가 쓰는 폴더 이름. 경로 구분자를 `-` 로 바꾼 꼴이다."""
    s = str(Path(path).resolve())
    for ch in ("\\", "/", ":", "."):
        s = s.replace(ch, "-")
    return s


def find_dir(project):
    """세션 폴더를 **찾는다.** 슬러그 규칙이 판본마다 달라 정확 일치에 기대지 않는다."""
    want = slug(project)
    if (ROOT / want).is_dir():
        return ROOT / want
    tail = Path(project).resolve().name
    hits = [d for d in ROOT.iterdir() if d.is_dir() and d.name.endswith("-" + tail)]
    if len(hits) == 1:
        return hits[0]
    # ★ **슬러그로 짐작하는 것을 여기서 그만둔다** (2026-08-15, 같은 결함의 두 번째 자리).
    #   Claude Code 의 폴더 이름은 한글을 통째로 `-` 로 바꾼다 — `…Documents-편입` 이 아니라
    #   `…Documents---` 다. 그래서 한글 이름 프로젝트는 `--project` 로 **영영 못 찾는다.**
    #   표시 이름은 이미 기록 안의 `cwd` 로 고쳤는데 **찾는 쪽을 안 고쳐 반쪽만 닫혀 있었다.**
    #   짐작 대신 **기록이 들고 있는 사실**을 쓴다.
    target = str(Path(project).resolve()).lower()
    for d in ROOT.iterdir():
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]:
            try:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        cwd = (json.loads(line).get("cwd") or "") if line.strip() else ""
                        if cwd:
                            if str(Path(cwd)).lower() == target:
                                return d
                            break
            except (OSError, ValueError):
                continue
    return None


def real_name(path, folder):
    """폴더 슬러그가 아니라 **기록 안의 `cwd`** 로 이름을 짓는다.

    ★ 슬러그는 경로 구분자 말고 **한글도 통째로 `-` 가 되어**(`Documents-토익` → `Documents---`)
      토익과 편입이 **같은 이름으로 나온다.** 「프로젝트별」을 내걸고 프로젝트를 구별 못 하면
      그 표는 못 읽는다 — 첫 실행에서 실제로 그랬다. `cwd` 는 기록이 그대로 들고 있다.
    """
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                cwd = (json.loads(line).get("cwd") or "").strip() if line.strip() else ""
                if cwd:
                    parts = [p.rstrip(":\\/") for p in Path(cwd).parts
                             if p.strip(":\\/")]
                    return "/".join(parts[-2:]) if len(parts) > 1 else cwd
    except (OSError, ValueError):
        pass
    return folder.name if len(folder.name) <= 42 else "…" + folder.name[-41:]


TOK_KEYS = ("input_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens", "output_tokens")
PHASES = ("design", "execute", "verify")


def classify_phase(content, tags):
    """이번 응답(레코드) 하나가 설계·실행·검증 중 어디인가. 순수 함수.

    ★ **새 판정을 만들지 않는다** — 검증 여부는 이미 있는 `gate_signature`(`gates`
      집계가 쓰는 그 자)를 그대로 재사용한다. `도구/reuse-before-rebuild` Skill이
      겨냥하는 바로 그 습관이다 — 판정 로직을 두 벌 두지 않는다.
    """
    has_tool = False
    for block in content or []:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        has_tool = True
        if block.get("name") == "Bash":
            cmd = str((block.get("input") or {}).get("command", ""))
            if gate_signature(cmd, tags):
                return "verify"
    return "execute" if has_tool else "design"


def read(path, tags=None):
    """(효율, 감수) 두 묶음. **순수 함수에 가깝게** — 출력은 아래에서 따로 한다."""
    tok = Counter()
    phase_tok = {p: Counter() for p in PHASES}
    tools = Counter()          # 도구별 호출 수
    out_by = Counter()         # 도구별 결과 글자 수
    big = []                   # (글자수, 라벨)
    reads = Counter()          # 파일별 Read 횟수
    gates = Counter()
    edits = Counter()
    names = {}                 # tool_use_id → (도구, 라벨)
    per_msg = Counter()        # 응답 id → 그 응답의 도구 호출 수
    nar = NarrationTally() if NarrationTally else None   # 중계 — 판정은 저쪽 정본

    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if tags is None:
                # 꼬리표는 **그 세션이 선 자리**에서 읽는다. `cwd` 는 첫 레코드에 있고,
                # 도구 호출은 그 뒤에 오므로 첫 호출 전에 준비된다.
                cwd = (rec.get("cwd") or "").strip()
                if cwd:
                    try:
                        tags = gate_tags(cwd)
                    except OSError:
                        tags = []
            if nar is not None:
                nar.feed(rec)
            msg = rec.get("message") or {}
            use = msg.get("usage") or {}
            content = msg.get("content")
            phase = classify_phase(content if isinstance(content, list) else [], tags)
            for k in TOK_KEYS:
                v = use.get(k) or 0
                tok[k] += v
                phase_tok[phase][k] += v
            tok["thinking"] += (use.get("output_tokens_details") or {}).get(
                "thinking_tokens") or 0

            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind == "tool_use":
                    name = block.get("name", "?")
                    tools[name] += 1
                    per_msg[rec.get("requestId") or rec.get("uuid")] += 1
                    inp = block.get("input") or {}
                    label = (inp.get("file_path") or inp.get("command")
                             or inp.get("pattern") or "")
                    names[block.get("id")] = (name, str(label)[:60])
                    if name == "Read" and inp.get("file_path"):
                        reads[Path(str(inp["file_path"])).name] += 1
                    if name in EDIT_TOOLS:
                        edits[name] += 1
                    if name == "Bash":
                        sig = gate_signature(str(inp.get("command", "")), tags)
                        if sig:
                            gates[sig] += 1
                elif kind == "tool_result":
                    body = block.get("content")
                    if isinstance(body, list):
                        size = sum(len(str(b.get("text", ""))) for b in body
                                   if isinstance(b, dict))
                    else:
                        size = len(str(body or ""))
                    name, label = names.get(block.get("tool_use_id"), ("?", ""))
                    out_by[name] += size
                    big.append((size, "%s %s" % (name, label)))

    relay = Counter(nar.result()) if nar is not None else Counter()
    calls = sum(tools.values())
    grouped = sum(n for n in per_msg.values() if n >= 2)
    big.sort(reverse=True)
    return {
        "tok": tok, "phase_tok": phase_tok, "calls": calls, "trips": len(per_msg),
        "grouped": grouped,
        "out_by": out_by, "big": big[:3],
        "reread": {k: v for k, v in reads.items() if v >= 2},
        "edits": sum(edits.values()), "edit_kinds": edits, "tagged": bool(tags),
        "relay": relay, "narration": nar is not None,
        "gates": sum(gates.values()), "gate_kinds": gates,
    }


def phase_tokens(c):
    """단계 하나(Counter)의 **토큰 합**(TOK_KEYS 넷을 무가중 합산 — 달러 비용이 아니다).
    순수 함수 — `report()`·`record()` 둘 다 이걸 쓴다.

    ★ INC-NARU-001 (Codex 스테이지9 §3) — 예전 이름 `phase_cost` 는 이 값이 가격 차이를
      반영한 「비용」인 것처럼 읽혔다. 실제로는 4종 토큰 수를 그대로 더한 것뿐이다
      (`cache_read_input_tokens` 는 다른 셋보다 단가가 훨씬 싸다). **계산은 그대로 두고
      이름만 사실에 맞춘다** — 아래 문단은 왜 그 합산이 (달러가 아니어도) 여전히 쓸모
      있는지의 근거다.
    ★ `cache_read_input_tokens` 를 뺐더니 백분율이 1%대로 죽어서 무의미했다 — 이 계통
      세션의 실제 토큰 대부분이 캐시 읽기라서(「캐시 재생성」 절 참고), 그걸 빼면 단계
      비교 자체가 뜻을 잃는다. 넷 다 더한다.
    """
    return sum(c[k] for k in TOK_KEYS)


def merge(parts):
    out = None
    for p in parts:
        if out is None:
            out = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in p.items()}
            out["phase_tok"] = {ph: c.copy() for ph, c in p["phase_tok"].items()}
            continue
        for k in ("tok", "out_by", "gate_kinds", "edit_kinds", "relay"):
            out[k].update(p[k])
        for ph in PHASES:
            out["phase_tok"][ph].update(p["phase_tok"][ph])
        out["tagged"] = out.get("tagged") or p.get("tagged")
        out["narration"] = out.get("narration") and p.get("narration")
        for k in ("calls", "trips", "grouped", "edits", "gates"):
            out[k] += p[k]
        out["big"] = sorted(out["big"] + p["big"], reverse=True)[:3]
        for k, v in p["reread"].items():
            out["reread"][k] = out["reread"].get(k, 0) + v
    return out


def pct(a, b):
    return (100.0 * a / b) if b else 0.0


def report(name, r, files):
    tok = r["tok"]
    created = tok["cache_creation_input_tokens"]
    cached = tok["cache_read_input_tokens"]
    chars = sum(r["out_by"].values())
    print("[세션 비용] %s  (세션 %d개)" % (name, files))

    print("\n── 효율 " + "─" * 48)
    print("  도구 출력      %s자  ★ 이 계통의 실측 결론상 **가장 비싼 자리**" % f"{chars:,}")
    for size, label in r["big"]:
        print("     가장 큰 것  %9s자  %s" % (f"{size:,}", label))
    print("  캐시 재생성    %s tok  (읽기 %s tok · **재생성 %.1f%%** — 낮을수록 싸다)"
          % (f"{created:,}", f"{cached:,}", pct(created, created + cached)))
    print("  출력           %s tok  (그중 사고 %s tok)"
          % (f"{tok['output_tokens']:,}", f"{tok['thinking']:,}"))
    if r["reread"]:
        top = sorted(r["reread"].items(), key=lambda kv: -kv[1])[:3]
        print("  같은 파일 재읽기 %d종  %s"
              % (len(r["reread"]), " · ".join("%s ×%d" % (k, v) for k, v in top)))
    print("  묶음률         %.0f%%  (호출 %d / 왕복 %d)   ※ **목표치로 쓰지 말 것**"
          % (pct(r["grouped"], r["calls"]), r["calls"], r["trips"]))
    rl = r.get("relay") or {}
    if not r.get("narration", True):
        # ★ **못 잰 것을 0 으로 찍지 않는다** — 그러면 «규율을 지킨 세션» 과 구별이 안 된다.
        print("  진행 중계      —  (`check_narration.py` 가 옆에 없다. 판정선이 거기 있어"
              " 여기서 다시 세지 않는다 — 미러·도입을 확인할 것)")
    elif rl.get("n"):
        # ★ 중계는 **채널을 잘못 고른 말**이다 — 사용자가 읽어야 할 것이 아니라 자기 사고다.
        #   판정선은 `check_narration.Tally` 하나이고 여기는 **추세로만** 본다(막는 것은 저쪽).
        print("  진행 중계      %d회 · %s자  (최종 보고 %s자)   ※ **자기 사고는 채팅 채널이 아니다**"
              % (rl["n"], f"{rl['chars']:,}", f"{rl.get('final', 0):,}"))

    print("\n── 단계(추정) " + "─" * 44)
    print("  ※ 응답 하나를 설계(도구 호출 없음)·실행(도구 호출 있음)·검증(그 호출이 게이트로")
    print("     보임) 중 하나로 본다 — **행위 유추다, 사람이 실제로 계획을 세웠는지는 못 잰다**.")
    phase_total = sum(phase_tokens(c) for c in r["phase_tok"].values()) or 1
    for ph, label in (("design", "설계"), ("execute", "실행"), ("verify", "검증")):
        t = phase_tokens(r["phase_tok"][ph])
        print("  %-6s %10s tok  (%.0f%%)" % (label, f"{t:,}", pct(t, phase_total)))

    print("\n── 감수 " + "─" * 48)
    print("  편집           %d회  %s" % (r["edits"], dict(r["edit_kinds"]) or ""))
    # ★ 꼬리표로 셌으면 «후보» 라고 하면 안 된다 — 그건 자기 출력에 대한 거짓 진술이다.
    print("  %s  %d회   ※ %s" % (
        "게이트(선언됨)      " if r.get("tagged") else "검증으로 보이는 명령",
        r["gates"],
        "`게이트-목록.txt` 에 **선언된 것만** 셌다"
        if r.get("tagged") else
        "**이름으로 거른 후보**다 — 서명을 보고 걷어낸다. 선언하려면 `게이트-목록.txt`"))
    for sig, n in r["gate_kinds"].most_common(5):
        print("     %4d회  %s" % (n, sig))
    if r["edits"]:
        ratio = r["gates"] / float(r["edits"])
        mark = "  ← ★ 「고쳤다」를 증명한 적이 없다" if r["gates"] == 0 else ""
        print("  편집당        %.2f%s" % (ratio, mark))
    else:
        print("  편집당        —  (편집이 없어 잴 것이 없다)")

    print("\n  ※ ★ **낮다고 곧 나쁜 것이 아니다.** 게이트를 «배치 끝에 한 번» 돌리면 이 수는"
          " 낮게 나오는데, 그건 실행 규율 11 이 **요구하는** 형태다. 콘텐츠 세션에서 볼 때 값을"
          " 하고, 도구·배포 세션에서는 낮은 것이 정상이다 (2026-08-15 전공정리 되먹임).")
    print("  ※ **한 숫자로 합치지 않는다** — 합치면 한쪽을 팔아 다른 쪽을 살 수 있게 된다.")
    print("  ※ 이 도구는 **고치지 않고 막지도 않는다**(언제나 exit 0). 판정은 사람이 한다.")


def one_line(name, files):
    if not files:
        return None
    r = merge([read(p) for p in files])
    chars = sum(r["out_by"].values())
    created = r["tok"]["cache_creation_input_tokens"]
    cached = r["tok"]["cache_read_input_tokens"]
    ratio = ("%.2f" % (r["gates"] / float(r["edits"]))) if r["edits"] else "—"
    # ★ **묶음률을 같은 줄에 둔다** (2026-08-15). 이걸 빼 두었더니 첫 판독에서 «두 프로젝트가
    #   서로 반대로 비효율적» 이라는 것이 안 보였다 — 재생성만 보면 한쪽만 나쁜 것처럼 읽히는데,
    #   실제로는 한쪽은 **큰 출력**(재생성 8.6% · 묶음 49%)이고 다른 쪽은 **왕복**(0.8% · 6%)이라
    #   **처방이 정반대**다. 한 축만 찍으면 엉뚱한 처방을 내리게 된다.
    return ("  %-42s 출력 %9s자 · 재생성 %4.1f%% · 묶음 %3.0f%% · 편집 %3d · 게이트 %3d · 편집당 %s"
            % (name, f"{chars:,}", pct(created, created + cached),
               pct(r["grouped"], r["calls"]), r["edits"], r["gates"], ratio))


RECORD_NAME = "세션비용.csv"
RECORD_HEAD = [
    "# **생성물이다 — 손으로 고치지 않는다.** `도구/audit_session_cost.py --record` 가 다시 쓴다.",
    "# 각 프로젝트는 **자기 줄만** 본다 — 하는 일이 달라 **프로젝트끼리 비교하는 값이 아니다.**",
    "# 세션 하나당 한 줄이고 새것이 위다. 추세는 «자기 과거»와만 견준다.",
    "프로젝트,잰날,출력자,재생성퍼센트,묶음퍼센트,편집,게이트,편집당,설계퍼센트,실행퍼센트,검증퍼센트",
]


def sessions_by_project(limit):
    """세션 파일을 **폴더가 아니라 `cwd` 로 묶는다.** `{프로젝트: [새것부터 limit개]}`

    ★★ **폴더는 프로젝트가 아니다** (2026-08-15 실측, 편입 세션 되먹임으로 드러남).
      `~/.claude/projects` 의 폴더 이름은 한글을 통째로 `-` 로 바꾸므로 **토익과 편입이 둘 다
      `…Documents---` 가 되어 한 폴더를 함께 쓴다** — 실측으로 그 폴더에 두 프로젝트 세션이
      5개 섞여 있었다(편입·토익·편입·토익·편입).
    ★ 폴더로 묶으면 **이 자의 설계가 통째로 깨진다.** 「자기 과거와만 견준다」가 요점인데
      **남의 과거와 견주게 된다** — 첫 판은 «가장 새 파일의 cwd» 하나로 폴더 전체에 이름을
      붙여서, 편입 세션이 자기 기록에서 토익 행 5개를 봤다.
    ★ 이름을 `cwd` 로 고친 것은 **표시**였고, 이번은 **묶는 기준** 자체다 — 같은 뿌리에서
      두 번 새어 나온 셈이라 여기서 기준을 바꾼다.
    """
    groups = {}
    for d in ROOT.iterdir():
        if not d.is_dir():
            continue
        for f in d.glob("*.jsonl"):
            groups.setdefault(real_name(f, d), []).append(f)
    for name in groups:
        groups[name] = sorted(groups[name], key=lambda p: p.stat().st_mtime,
                              reverse=True)[:limit]
    return groups


def record(shared, limit):
    """프로젝트 × 최근 세션을 **한 파일로 남긴다** — 사람도 훅도 이걸 읽는다.

    ★ 왜 파일인가 (2026-08-15 사용자 판정): *"이런거 자체는 시스템으로 다 구현이 되어있으면서
      쟤네가 너쪽으로 올리고 그에 따라 계산된 후 먼가 남겨서 쟤네가 먼가 보고 그런식으로 갔음
      하는데 … 뭔가 이상하다 이게 맞나 싶을 때만 가끔씩 점검하러 오고만 싶고"*.
      **채팅이 전달 경로면 사람이 매번 껴야 한다.** 파일로 남겨야 훅이 읽는다.
    ★ **세션을 합치지 않고 한 줄씩** 남긴다. 합치면 «자기 과거와의 추세»를 못 본다 —
      그리고 이 계통은 목표치를 안 쓰기로 했으므로(`묶음률을 목표로 쓰지 말 것`)
      **추세가 유일하게 정당한 판정 근거**다.
    """
    out = list(RECORD_HEAD)
    for name, files in sorted(sessions_by_project(limit).items()):
        for f in files:
            r = read(f)
            if not r["calls"]:
                continue
            tok = r["tok"]
            created = tok["cache_creation_input_tokens"]
            day = __import__("time").strftime(
                "%Y-%m-%d", __import__("time").localtime(f.stat().st_mtime))
            ptot = sum(phase_tokens(c) for c in r["phase_tok"].values()) or 1
            out.append("%s,%s,%d,%.1f,%.0f,%d,%d,%s,%.0f,%.0f,%.0f" % (
                name.replace(",", " "), day, sum(r["out_by"].values()),
                pct(created, created + tok["cache_read_input_tokens"]),
                pct(r["grouped"], r["calls"]), r["edits"], r["gates"],
                ("%.2f" % (r["gates"] / float(r["edits"]))) if r["edits"] else "",
                pct(phase_tokens(r["phase_tok"]["design"]), ptot),
                pct(phase_tokens(r["phase_tok"]["execute"]), ptot),
                pct(phase_tokens(r["phase_tok"]["verify"]), ptot)))
    path = Path(shared) / "기록" / RECORD_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    # ★ **임시파일 + 원자적 교체.** 이 파일은 여러 프로젝트가 각자 다시 쓸 수 있는데,
    #   «줄 단위 병합»은 필요 없다 — 이건 프로젝트들이 나눠 채우는 대장이 아니라
    #   `~/.claude/projects` **한 소스를 옮겨 적은 파생물**이라 아무나 전체를 다시 만들 수 있고
    #   나중에 쓴 쪽이 늘 더 최신이다. 병합을 넣으면 **죽은 프로젝트의 낡은 줄이 영원히
    #   살아남아** «두 벌이 갈린다» 를 만든다. 남는 위험은 **찢어진 쓰기** 하나뿐이라 그것만 막는다.
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))
    print("[세션 비용] 기록했다 — %s (%d줄)" % (path, len(out) - len(RECORD_HEAD)))
    return 0


def main():
    limit, project = 1, os.getcwd()
    for flag in sys.argv[1:]:
        if flag.startswith("--sessions="):
            limit = int(flag.split("=", 1)[1])
        elif flag.startswith("--project="):
            project = flag.split("=", 1)[1]
    if not ROOT.is_dir():
        print("세션 기록 폴더가 없다: %s" % ROOT)
        return 0

    if "--record" in sys.argv[1:]:
        shared = Path(os.environ.get("CLAUDE_SHARED_SYSTEM")
                      or next((p for p in (Path.home() / "Documents" / "naru",
                                    Path.home() / "Documents" / "Claude")
                            if p.is_dir()), Path.home() / "Documents" / "naru"))
        if not shared.is_dir():
            print("공용 폴더를 못 찾았다: %s (CLAUDE_SHARED_SYSTEM 으로 지정 가능)" % shared)
            return 0
        return record(shared, max(limit, 5))

    if "--all" in sys.argv[1:]:
        print("[세션 비용] 프로젝트별 (최근 세션 %d개씩)\n" % limit)
        # ★ 폴더가 아니라 `cwd` 로 묶는다 — **폴더는 프로젝트가 아니다**(토익·편입이 한 폴더다).
        for name, files in sorted(sessions_by_project(limit).items()):
            line = one_line(name, files)
            if line:
                print(line)
        print("\n  ※ 프로젝트마다 하는 일이 달라 **서로 비교하지 말 것** — 같은 프로젝트의 추세로 본다.")
        return 0

    d = find_dir(project)
    if d is None:
        print("이 프로젝트의 세션 기록을 못 찾았다: %s" % project)
        print("  ※ `--all` 로 목록을 보거나 `--project=<경로>` 로 지목한다.")
        return 0
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    if not files:
        print("세션 기록이 없다: %s" % d)
        return 0
    report(d.name, merge([read(p) for p in files]), len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
