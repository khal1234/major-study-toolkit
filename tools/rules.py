# -*- coding: utf-8 -*-
"""**규칙 한 벌로 장을 잰다** — 규칙 등록부(`docs/규칙-등록부.json`) × 장 × 판정 (열린 날 2026-09-18).

    python tools/rules.py status [--only=<과목>,…]          # 장마다 「아직 판정 안 된 것」 수
    python tools/rules.py show "data/<과목>/chNN.json"       # 그 장의 미판정 목록
    python tools/rules.py verdict "data/<과목>/chNN.json" --rule <id> [--item <항목>] --say "고침: …|해당없음: …" --apply
    python tools/rules.py gate "data/<과목>/chNN.json" …    # HEAD 보다 미판정이 늘었으면 exit 1

재는 것: 장마다 미판정 = ⑴ machine 규칙의 후보 중 판정이 안 붙은 항목 ⑵ render·read 규칙 중 그 장에
`*` 판정이 없는 규칙. 판정은 `data/<과목>/rules-verdicts.json`(`{chNN: {규칙: {항목|*: 문장}}}`).
문턱: gate 는 HEAD 의 같은 장보다 미판정이 **하나라도 늘면** 막는다 — 새 장은 HEAD 가 0 이라 전부 판정해야 들어간다.
못 보는 것: 판정 문장이 맞는지(「해당없음」이 정말 해당 없는지)는 사람 몫이다. machine 규칙의 자가 못 보는 결함도 못 본다.
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
REGISTRY = os.path.join(ROOT, "docs", "규칙-등록부.json")
VERDICT_PREFIXES = ("고침:", "해당없음:")


def load_registry():
    with open(REGISTRY, encoding="utf-8") as fh:
        return json.load(fh)


def verdicts_path(subject_dir):
    return os.path.join(subject_dir, "rules-verdicts.json")


def load_verdicts(subject_dir):
    path = verdicts_path(subject_dir)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# 삽화 안 위·아래 빈 띠의 목표 9px — 2026-09-09 전전 사용자 [발화 생략]에
# `fix_figure_vertical_balance --margin=9` 로 눌러 받아들여진 값. 허용 +6 은 세로 균형 자의 BALANCE_TOL_PX 와 같은 눈금.
MARGIN_TARGET_PX = 9
import audit_figure_balance as _fb  # noqa: E402
MARGIN_TOL_PX = _fb.BALANCE_TOL_PX


def _margin_hits(chapter, chname):
    import audit_figure_balance as fb
    hits = []
    for diagram in fb.iter_diagrams(chapter):
        svg = diagram.get("svg") or ""
        vb = fb._viewbox(svg) if svg else None
        if not vb:
            continue
        top, bottom = fb._content_extent(svg, vb)
        if top is None:
            continue
        pad_top, pad_bottom = top - vb[1], (vb[1] + vb[3]) - bottom
        if max(pad_top, pad_bottom) > MARGIN_TARGET_PX + MARGIN_TOL_PX:
            hits.append((chname, diagram.get("id") or "?", "위 %.1f / 아래 %.1f — 목표 %d"
                         % (pad_top, pad_bottom, MARGIN_TARGET_PX)))
    return hits


def _balance_hits(chapter, chname):
    import audit_figure_balance as fb
    hits = []
    for diagram in fb.iter_diagrams(chapter):
        svg = diagram.get("svg") or ""
        vb = fb._viewbox(svg) if svg else None
        if not vb:
            continue
        top, bottom = fb._content_extent(svg, vb)
        if top is None:
            continue
        diff = ((vb[1] + vb[3]) - bottom) - (top - vb[1])
        if abs(diff) > fb.BALANCE_TOL_PX:
            hits.append((chname, diagram.get("id") or "?", "위·아래 여백 차이 %+.1f" % diff))
    return hits


SKIP_KEYS = {"svg", "sourceRef", "changeNote", "rationale", "id", "anchorText"}


def _regex_hits(chapter, chname, pattern):
    """독자에게 보이는 글 필드에서 패턴을 찾는다 — 항목은 가장 가까운 id. 저자 전용 필드·SVG 는 안 본다."""
    rx = re.compile(pattern, re.M)
    hits = []

    def walk(node, owner):
        if isinstance(node, dict):
            owner = node.get("id") or owner
            for k, v in node.items():
                if k not in SKIP_KEYS:
                    walk(v, owner)
        elif isinstance(node, list):
            for v in node:
                walk(v, owner)
        elif isinstance(node, str):
            m = rx.search(node)
            if m:
                hits.append((chname, owner, "«%s»" % m.group(0).strip()[:40]))

    walk(chapter, chname)
    seen, out = set(), []
    for h in hits:
        if h[1] not in seen:
            seen.add(h[1])
            out.append(h)
    return out


def machine_hits(rule, chapter, chname, subject_dir):
    """machine 규칙 하나의 후보 — [(항목, 사유)]."""
    kind, _, key = (rule.get("measure") or "").partition(":")
    if kind == "drift":
        import audit_convention_drift as drift
        drift.CURRENT_FOLDER[:] = [subject_dir]
        rows = drift.CHECKS[key](chapter, chname)
    elif kind == "balance" and key == "vertical":
        rows = _balance_hits(chapter, chname)
    elif kind == "balance" and key == "margin":
        rows = _margin_hits(chapter, chname)
    elif kind == "regex":
        rows = _regex_hits(chapter, chname, key)
    else:
        raise SystemExit("모르는 measure: %s (규칙 %s)" % (rule.get("measure"), rule["id"]))
    return [(str(item), why) for _ch, item, why in rows]


def open_items(chapter, chname, subject_dir, registry=None, verdicts=None):
    """미판정 목록 — [(규칙 id, 항목, 사유)]. render·read 는 항목 `*` 하나."""
    registry = registry or load_registry()
    verdicts = load_verdicts(subject_dir) if verdicts is None else verdicts
    done = verdicts.get(chname) or {}
    out = []
    for rule in registry["rules"]:
        judged = done.get(rule["id"]) or {}
        if rule["how"] == "machine":
            for item, why in machine_hits(rule, chapter, chname, subject_dir):
                if item not in judged and "*" not in judged:
                    out.append((rule["id"], item, why))
        elif "*" not in judged:
            out.append((rule["id"], "*", rule["what"]))
    return out


def chapter_at_head(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    r = subprocess.run(["git", "-c", "core.quotepath=false", "show", "HEAD:" + rel], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        return None


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _chname(path):
    return os.path.splitext(os.path.basename(path))[0]


def cmd_status(only):
    import audit_content
    registry = load_registry()
    print("규칙 등록부 판 %d · 규칙 %d개" % (registry["version"], len(registry["rules"])))
    seen = 0
    for folder in audit_content.subject_dirs():
        subject = os.path.basename(folder)
        if only and subject not in only:
            continue
        verdicts = load_verdicts(folder)
        rows = []
        for name in sorted(n for n in os.listdir(folder) if re.fullmatch(r"ch\d{2}\.json", n)):
            ch = _load(os.path.join(folder, name))
            if ch.get("placeholder") is True:
                continue
            seen += 1
            items = open_items(ch, name[:-5], folder, registry, verdicts)
            m = sum(1 for r, *_ in items if _how(registry, r) == "machine")
            rows.append("%s 미판정 %d (machine %d · render/read %d)" % (name[:-5], len(items), m, len(items) - m))
        print("-- %s --" % subject)
        for row in rows:
            print("   " + row)
    print("훑은 장 %d개" % seen)
    return 0 if seen else 1


def _how(registry, rule_id):
    return next(r["how"] for r in registry["rules"] if r["id"] == rule_id)


def cmd_show(path):
    folder = os.path.dirname(os.path.abspath(path))
    items = open_items(_load(path), _chname(path), folder)
    for rule, item, why in items:
        print("%-28s %-36s %s" % (rule, item, why))
    print("미판정 %d건" % len(items))
    return 0


def cmd_verdict(path, rule_id, item, say, apply):
    if not say.startswith(VERDICT_PREFIXES):
        raise SystemExit("--say 는 「고침: …」 또는 「해당없음: …」로 시작한다")
    registry = load_registry()
    if not any(r["id"] == rule_id for r in registry["rules"]):
        raise SystemExit("등록부에 없는 규칙: " + rule_id)
    folder = os.path.dirname(os.path.abspath(path))
    verdicts = load_verdicts(folder)
    verdicts.setdefault(_chname(path), {}).setdefault(rule_id, {})[item or "*"] = say
    print(("반영" if apply else "미리보기") + " — %s %s %s ← %s" % (_chname(path), rule_id, item or "*", say))
    if apply:
        with open(verdicts_path(folder), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(verdicts, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
    return 0


def cmd_verdicts_from(path, src, apply):
    """한 줄 = `규칙|항목(*)|고침: … 또는 해당없음: …` — 장 하나의 판정을 한 번에."""
    worst = 0
    with open(src, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rule_id, item, say = (p.strip() for p in line.split("|", 2))
            worst = max(worst, cmd_verdict(path, rule_id, None if item == "*" else item, say, apply))
    return worst


def cmd_gate(paths):
    registry = load_registry()
    worst = 0
    for path in paths:
        folder = os.path.dirname(os.path.abspath(path))
        name = _chname(path)
        verdicts = load_verdicts(folder)
        now = open_items(_load(path), name, folder, registry, verdicts)
        head_ch = chapter_at_head(path)
        before = open_items(head_ch, name, folder, registry, verdicts) if head_ch else []
        # (규칙, 항목) 으로 견준다 — 사유 문장(「3번 나온다」→「2번」)이 바뀐 것은 늘어난 것이 아니다
        before_keys = {(r, i) for r, i, _w in before}
        grew = [row for row in now if (row[0], row[1]) not in before_keys]
        if grew:
            worst = 1
            print("[막음] %s — 미판정이 늘었다 %d → %d" % (os.path.relpath(path, ROOT), len(before), len(now)))
            for rule, item, why in sorted(grew)[:20]:
                print("   %s %s — %s" % (rule, item, why))
            print("   푸는 법: 고치거나 python tools/rules.py verdict … --say \"해당없음: <사유>\" --apply")
        else:
            print("[통과] %s — 미판정 %d (HEAD %d)" % (os.path.relpath(path, ROOT), len(now), len(before)))
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description="규칙 등록부로 장을 잰다")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p.add_argument("--only")
    p = sub.add_parser("show")
    p.add_argument("chapter")
    p = sub.add_parser("verdict")
    p.add_argument("chapter")
    p.add_argument("--rule", required=True)
    p.add_argument("--item")
    p.add_argument("--say", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("verdicts")
    p.add_argument("chapter")
    p.add_argument("--from", dest="src", required=True)
    p.add_argument("--apply", action="store_true")
    p = sub.add_parser("gate")
    p.add_argument("chapters", nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "verdicts":
        return cmd_verdicts_from(args.chapter, args.src, args.apply)
    if args.cmd == "status":
        return cmd_status({s.strip() for s in args.only.split(",")} if args.only else None)
    if args.cmd == "show":
        return cmd_show(args.chapter)
    if args.cmd == "verdict":
        return cmd_verdict(args.chapter, args.rule, args.item, args.say, args.apply)
    return cmd_gate(args.chapters)


if __name__ == "__main__":
    raise SystemExit(main())
