"""병합 충돌 블록을 양쪽 다 살려 푼다 — ours 뒤에 theirs (인박스·큐·인계처럼 덧붙이기만 하는 문서 전용).

재는 것: 파일 안 `<<<<<<<`/`=======`/`>>>>>>>` 블록 수(0이면 손댈 것 없음).
문턱: 없음 — 판정은 사람이 한다(클라우드 갈래 병합 규약 「충돌은 양쪽 살림」, 2026-09-24 인계).
못 보는 것: 같은 줄을 서로 다르게 고친 의미 충돌(둘 다 남아 중복 줄이 된다) · 장 JSON 같은 구조 파일(거기엔 쓰지 말 것).

    python tools/merge_keep_both.py <경로…>
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def keep_both(text, prefer=None):
    """prefer 가 None 이면 양쪽, "ours"/"theirs" 면 그쪽만 남긴다(JSON 은 한쪽만 — 양쪽이면 키가 겹쳐 깨진다)."""
    out, state, blocks = [], None, 0
    for line in text.split("\n"):
        if line.startswith("<<<<<<< "):
            state, blocks = "ours", blocks + 1
            continue
        if line.startswith("=======") and state == "ours":
            state = "theirs"
            continue
        if line.startswith(">>>>>>> ") and state == "theirs":
            state = None
            continue
        if state is None or prefer is None or state == prefer:
            out.append(line)
    return "\n".join(out), blocks


def main(argv):
    prefer = None
    if argv and argv[0].startswith("--prefer="):
        prefer = argv[0].split("=", 1)[1]
        if prefer not in ("ours", "theirs"):
            sys.exit("--prefer 는 ours 또는 theirs")
        argv = argv[1:]
    if not argv:
        sys.exit("경로를 하나 이상 준다")
    for path in argv:
        if path.endswith(".json") and prefer is None:
            print(f"{path}: JSON 은 양쪽 살림 대상 아님 — --prefer=ours|theirs 로 한쪽을 고른다")
            continue
        with open(path, encoding="utf-8") as fh:
            merged, blocks = keep_both(fh.read(), prefer)
        if blocks:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(merged)
        print(f"{path}: 충돌 블록 {blocks} — {prefer or '양쪽'} 살림")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
