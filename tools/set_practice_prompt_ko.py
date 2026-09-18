"""예제·연습(`practice`) 문항의 영문 지문을 사람이 옮긴 한글 지문으로 갈아 끼운다.

재는 것: 없다 — **번역은 사람이 하고 이 도구는 적는 일만 한다.** 후보는
`audit_convention_drift.py --check=practice-prompt-language` 가 낸다.

하는 일(문항 하나마다, 그 문항 객체의 텍스트 범위 안에서만):
  ⑴ `prompt` 를 준 한글로 ⑵ `promptLanguage` 를 `"ko"` 로(없으면 끼운다)
  ⑶ `ramp` 를 2 이하로 — 기존 키를 고친다(새 키를 끼우면 중복 키가 되고 뒤 값이 이긴다, 2026-09-18 함정 ①)
  ⑷ `glossary` 를 지운다 — 영문 낱말 풀이라 한글 지문에서는 C59 「낱말이 지문에 없다」로 걸린다(함정 ②)
  ⑸ `changeNote` 를 부류 문구로 덮는다(없으면 끼운다).
  파일을 다시 직렬화하지 않는다 — 포맷을 정규화하면 diff 가 불어난다(`clear_expected_echo.py` 와 같은 이유).
  쓰기 전에 결과 JSON 의 그 문항이 「원래 문항 + 위 다섯」과 같은지 대조한다.

못 보는 것: 번역이 맞는가 · 존댓말(C23 은 빌드가 본다) · 장의 `lintWaivers` 사유에 남은 「영문 지문」
  같은 낡은 문구(함정 ④ — 후보만 찍는다) · `problem-originality-verdicts.json` 의 낡은 부분 차용
  판정(함정 ⑤ — close_report 가 막는다).

쓰는 법:
  python tools/set_practice_prompt_ko.py "data/<과목>/chNN.json" --map <번역.json>          (셈만)
  python tools/set_practice_prompt_ko.py "data/<과목>/chNN.json" --map <번역.json> --apply
  <번역.json> = {"<문항id>": "<한글 지문>", …}
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from buildlib.checks_content import RAMP_SPEC, prompt_shape   # noqa: E402

NOTE = ("지적(2026-09-18, 부류 «예제·연습 지문은 한글») 지문을 한글로 옮겼습니다 — "
        "영문 지문은 「05 문제」 탭에만 둡니다.")
RAMP_MAX = 2   # 자(practice-prompt-language)가 요구하는 「ramp 1~2」의 윗끝


def object_spans(text):
    """문자열을 건너뛰며 `{…}` 의 (시작, 끝) 을 전부 낸다."""
    spans, stack, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif c == "{":
            stack.append(i)
        elif c == "}":
            spans.append((stack.pop(), i + 1))
        i += 1
    return spans


def value_end(text, i):
    """`i` 에서 시작하는 JSON 값의 끝(배타)."""
    depth = 0
    while True:
        c = text[i]
        if c == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            if depth == 0:
                return i + 1
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                return i + 1
        elif depth == 0 and c in ",\n":
            return i
        i += 1


def top_key(span, key):
    """문항 객체 바로 아래 층의 `"key":` 위치(없으면 None)."""
    depth, i, found = 0, 0, None
    while i < len(span):
        c = span[i]
        if c == '"':
            j = i + 1
            while span[j] != '"':
                j += 2 if span[j] == "\\" else 1
            if depth == 1 and span[i:j + 1] == '"' + key + '"' and span[j + 1:].lstrip().startswith(":"):
                if found is not None:
                    raise ValueError("키가 두 번 있다: " + key)
                found = i
            i = j + 1
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        i += 1
    return found


def set_value(span, key, new_json, before="prompt"):
    k = top_key(span, key)
    if k is None:
        p = top_key(span, before)
        line_start = span.rfind("\n", 0, p) + 1
        indent = span[line_start:p]
        insert = '"%s": %s' % (key, new_json)
        insert += (",\n" + indent) if indent.strip() == "" else ", "
        return span[:p] + insert + span[p:]
    v = span.index(":", k + len(key) + 2) + 1
    while span[v] in " \t":
        v += 1
    return span[:v] + new_json + span[value_end(span, v):]


def drop_key(span, key):
    k = top_key(span, key)
    if k is None:
        return span
    v = span.index(":", k + len(key) + 2) + 1
    while span[v] in " \t\r\n":
        v += 1
    e = value_end(span, v)
    m = re.match(r"\s*,\s*", span[e:])
    if m:                                  # 뒤에 키가 더 있다 — 다음 키 앞까지 지운다
        return span[:k] + span[e + m.end():]
    m = re.search(r",\s*$", span[:k])      # 마지막 키 — 앞 쉼표부터 지운다
    return span[:m.start()] + span[e:]


def main():
    ap = argparse.ArgumentParser(description="예제·연습 지문을 한글로 갈아 끼운다(번역은 사람이 한다)")
    ap.add_argument("chapter", help="data/<과목>/chNN.json")
    ap.add_argument("--map", help='{"<문항id>": "<한글 지문>"} JSON 파일')
    ap.add_argument("--list", action="store_true", help="아직 한글이 아닌 예제·연습 지문을 id 와 함께 찍는다")
    ap.add_argument("--apply", action="store_true", help="실제로 쓴다(없으면 셈만)")
    args = ap.parse_args()

    if not os.path.exists(args.chapter):
        sys.exit("파일이 없다: " + args.chapter)
    if args.list:
        # 번역할 원문을 읽는 자리 — Grep 은 긴 줄을 생략해 지문이 잘린다(2026-09-18 실측).
        with open(args.chapter, encoding="utf-8") as fh:
            ch = json.load(fh)
        for it in ch.get("practice") or []:
            if isinstance(it, dict) and it.get("promptLanguage") != "ko" and isinstance(it.get("prompt"), str):
                if len(re.findall(r"[가-힣]", it["prompt"])) < len(it["prompt"]) // 5:
                    print("== %s ramp=%s%s\n%s" % (it.get("id"), it.get("ramp"),
                                                   " glossary" if "glossary" in it else "", it["prompt"]))
        return 0
    if not args.map:
        sys.exit("--map 이나 --list 중 하나가 필요하다")
    with open(args.map, encoding="utf-8") as fh:
        want = json.load(fh)
    with open(args.chapter, encoding="utf-8", newline="") as fh:
        out = fh.read()
    items = {it.get("id"): it for it in json.loads(out).get("practice") or [] if isinstance(it, dict)}

    done, missing, expect = [], [], {}
    for pid, ko in want.items():
        if pid not in items:
            missing.append(pid)
            continue
        target = [s for s in object_spans(out)
                  if top_key(out[s[0]:s[1]], "id") is not None
                  and json.loads(out[s[0]:s[1]]).get("id") == pid
                  and "prompt" in json.loads(out[s[0]:s[1]])]
        if len(target) != 1:
            sys.exit("문항을 한 자리로 못 집었다: %s (%d곳)" % (pid, len(target)))
        a, b = target[0]
        span = out[a:b]
        span = set_value(span, "changeNote", json.dumps(NOTE, ensure_ascii=False))
        span = set_value(span, "promptLanguage", '"ko"')
        span = set_value(span, "prompt", json.dumps(ko, ensure_ascii=False))
        old = items[pid]
        if isinstance(old.get("ramp"), int) and old["ramp"] > RAMP_MAX:
            span = set_value(span, "ramp", str(RAMP_MAX))
        span = drop_key(span, "glossary")
        out = out[:a] + span + out[b:]
        new = dict(old, prompt=ko, promptLanguage="ko", changeNote=NOTE)
        if isinstance(old.get("ramp"), int):
            new["ramp"] = min(old["ramp"], RAMP_MAX)
        new.pop("glossary", None)
        expect[pid] = new
        done.append("%s (ramp %s→%s%s)" % (pid, old.get("ramp"), new.get("ramp"),
                                           " · glossary 지움" if "glossary" in old else ""))

    got = {it.get("id"): it for it in json.loads(out).get("practice") or [] if isinstance(it, dict)}
    for pid, new in expect.items():
        if got[pid] != new:
            sys.exit("대조 실패 — 치환 결과가 기대와 다르다: " + pid)
    # ★ 한글 칸(ramp 1·2)의 문장·글자 상한을 쓰기 전에 잰다 — 영문 원서 지문을 그대로 옮기면
    #   5~7문장이 되어 C54 에 걸렸다(2026-09-18 기계공작법 ch10~12, 8문항). 자는 빌드와 같은 것을 쓴다.
    over = []
    for pid, new in expect.items():
        spec = RAMP_SPEC.get(new.get("ramp"))
        if not spec:
            continue
        _, sentences, chars = prompt_shape(new["prompt"])
        if sentences > spec["sentences"] or chars > spec["chars"]:
            over.append("%s — ramp %s 상한 %d문장·%d자인데 %d문장·%d자"
                        % (pid, new["ramp"], spec["sentences"], spec["chars"], sentences, chars))
    for o in over:
        print("  [상한 초과]", o)
    if over:
        sys.exit("상한을 넘는 지문이 있어 쓰지 않았다 — 묻는 것만 남기고 줄여서 다시 준다")

    for d in done:
        print("  [옮김]", d)
    for m in missing:
        print("  [못 찾음]", m)
    stale = re.findall(r'"[^"\n]*(?:영문|영어)[^"\n]*"', json.dumps(json.loads(out).get("lintWaivers"), ensure_ascii=False))
    for s in stale:
        print("  [lintWaivers 사유 확인]", s[:160])
    print("합계 — 옮김 %d · 못 찾음 %d (%s)" % (len(done), len(missing), os.path.basename(args.chapter)))
    if not args.apply:
        print("※ --apply 를 주면 실제로 쓴다")
        return 1 if missing else 0
    if done:
        with open(args.chapter, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
