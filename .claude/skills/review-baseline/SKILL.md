---
name: review-baseline
description: Use before moving the review baseline (`--accept-review-rev` / `-head` / `-as-built`), clearing `changeNote`, touching `reviewHold`, or when the user signals they reviewed a chapter ("다 봤어", 화면 번호로 지적 나열). Also when the viewer/template changed (viewer-change-log) or when deciding what counts as a review change.
---

# 변경점 기준선 (2026-09-11 AGENTS.md 에서 옮김)

> ★ **언제 미나 — 사용자가 [발화 생략]고 한 지점까지만**(2026-08-29 사용자 판정). 아래 옛 문장
> 「배치를 커밋한 뒤 곧바로 돌린다 — 요청을 기다리지 않는다」는 이 판정으로 대체됐다. 화면 번호(`3/20`)로
> 지적을 나열한 것도 그 범위까지 봤다는 신호다. 확인 전에는 명령을 준비만 해 둔다.

## ★ 수정 배치를 반영하면 변경점 기준선도 함께 옮긴다 (신설 2026-08-01)

- **기준선은 언제나 「이번 배치 직전 상태」다.** 그래야 하이라이트가 이번에 고친 것만 가리킨다.
  사용자가 다음 검수를 '변경된 것만' 보는 방식으로 하므로, 어긋나면 검수가 못 돌아간다.
- **사용자가 확인했다고 한 지점까지 민다**(맨 위 2026-08-29 판정). 옛 판정「배치를 커밋한 뒤 곧바로 —
  요청을 기다리지 않는다」는 대체됐다. 미룬 이동은 인박스에 적어 두지 않으면 잊힌다.

  ```
  python tools/build_site.py --accept-review-rev=<배치 첫 커밋의 부모 sha> --accept-review-chapter=chNN
  ```

- `changeNote` 비우기는 같은 자리에서 `python tools/clear_change_notes.py --keep=<이번 배치 표시> --apply`.
  판정선은 「이번 배치의 것인가」 하나이고 `--keep` 표시로 가른다(규칙만 있고 코드가 없어 ch05 에
  2026-07-29 자 기록이 살아남았다 — 실측 47개 중 44개가 끝난 배치 것).
- **`--accept-review-head` 는 커밋(HEAD)을 읽는다 — 작업 트리가 아니다**(2026-08-07). 커밋 전에 돌리면
  그 배치가 통째로 남는다.
  - **판정은 목록이 아니라 `review.summary` 로 한다.** 목록이 `0 / 0` 이어도 요약이 0이 아니면 화면에는
    숫자가 뜬다(실사고: ch01 요약 `수정 1` 을 목록만 보고 0으로 읽었다).
  - 순서를 못 박는다: `commit.py` → `--accept-review-head`. `git status --short` 가 빈 것을 먼저 확인한다.
- **틀리는 두 방식:** ⑴ 수정한 뒤의 HEAD → 이번 수정이 하나도 안 보인다 ⑵ 너무 오래된 지점 →
  옛 변경까지 섞인다.
- **챕터를 반드시 한정한다**(`--accept-review-chapter=`). 안 그러면 아직 안 본 챕터의 검수 상태까지 날린다.
- **검수 안 한 챕터는 기준선을 「HEAD 로 유지」한다**(정정 2026-08-07 — 「만들지 않는다」면 전부가 새
  것으로 보인다).
  - ★ **2026-09-18 부터 기계가 한다** — 과목 `index.json` 의 `reviewSeen` 밖 장은 빌드가 HEAD 로 유지한다
    (사용자 *[발화 생략]*). 사용자가 어떤 장을 화면에서 지적하면
    **그 자리에서** `python tools/set_review_seen.py --subject "<과목>" --add chNN --why "<날짜 · 근거>" --apply`.
    잠금 `test_review_marks_only_on_seen_chapters`.
  - 원칙: 사용자가 아직 도달하지 않은 자리에는 변경점을 띄우지 않는다. 어차피 전부 읽어야 하기 때문이다.
  - 배치를 끝낼 때마다 이번 배치가 손댄 **모든** 미검수 챕터를 HEAD 로 민다.
  - **초기화는 배치 중간이 아니라 배치를 닫는 마지막 단계에서** 한다. 그 뒤에 또 고쳤으면 다시 민다
    (실사고 2026-08-07: 맞춘 뒤 또 고쳐 마크가 되살아났고 세 번 지적받았다).
- **사용자가 [발화 생략]라고 하면 `index.json` 의 `reviewHold` 에 적는다**(2026-08-13).
  보류를 채팅에만 두면 진다 — 다음 세션은 파일을 읽지 지난 채팅을 읽지 않는다(실사고: 인박스에 남은
  「마지막에 기준선 이동」을 실행해 수정 84항목 표시가 사라졌고 복구에 `--accept-review-rev` 6회).
  - 선언: `"reviewHold": {"at": …, "why": "<사용자 말 그대로>[발화 생략]baseline": "<sha>"}`.
    있으면 `--accept-review`·`-head`·`-rev` 세 경로 전부 빌드가 거부한다(exit 1).
  - 푸는 길은 우회 플래그가 아니라 그 키를 지우는 것이다 — 지운 사실이 커밋 diff 에 남는다.
    잠금 `test_checks.py::test_review_hold_blocks_baseline_move`.
- **「다 봤어」의 기준은 시각이 아니라 커밋이다**(2026-08-13). 시각의 HEAD 로 잡으면 직전에 들어온
  커밋이 마크 없이 화면에 반영돼 그대로 사라진다.
  - 기본 명령:
    `python tools/build_site.py --all --quiet --accept-review-as-built --accept-review-chapter=chNN` —
    기준선을 **사용자가 마지막으로 본 화면의 빌드 sha** 로 잡는다(`.review-snapshot/chNN.built.json`).
  - 빌드 sha 와 밀려는 sha 사이에 그 챕터 커밋이 있으면 빌드가 목록을 찍고 거부한다. 승인은
    `--accept-review-user-saw=<sha,…>` 로 명시한다.
  - **커밋 전에는 못 민다** — 미커밋 변경이 섞인 화면은 플래그로 못 푼다(커밋 → 빌드 → 민다).
  - 판정은 `buildlib/review.unacknowledged_swallows`, 잠금 `test_baseline_move_cannot_swallow_unseen_commits`.
  - `build_review.py` 의 거부 목록은 **접두**로 본다 — 열거는 빠뜨려도 통과되고 접두는 빠뜨릴 것이 없다.
- **뷰어를 고쳤으면 `docs/viewer-change-log.txt` 에 한 줄 적는다**(2026-08-23). 변경점 판정의 입력은
  챕터 JSON 뿐이라 **뷰어·템플릿·CSS 변경은 검수 동선에서 통째로 사라진다.** 기계는 「판본이
  바뀌었나」만 판정하고(수락 기록의 `viewerRev`) 「무엇이」는 그 파일이 정본이다 —
  적힌 줄이 검수 배너로 뜬다. 잠금 `test_viewer_change_reaches_the_reviewer`.
- **변경점 판정은 이진이다 — 독자가 화면에서 알아볼 수 있는 변화만 센다**(2026-08-13).
  - 중간 등급을 만들지 않는다. 「표기만」은 판정을 미루는 이름이었고 요약 25 vs 화면 4 로 무너졌다.
    볼 것이 아니면 빌드가 표시를 아예 안 만들고, 요약·목록·화면이 그 하나의 판정만 읽는다.
  - 삽화 판정선: 글자·크기·색이 다르면 센다 / 좌표만 다르고 최대 이동 ≤ 10 화면 실효 px 면 안 센다 /
    그보다 크면 형상 변경이라 센다.
  - 저자 전용 필드(`changeNote`·`sourceRef`·`rationale`)만 바뀐 것은 변경이 아니다 — 안 빼면 사유를 지운
    자국이 다음 배치의 변경점이 된다.
  - 모르는 필드·속성은 **세는 쪽이 기본값**이다. 화이트리스트로 짜면 새 내용 필드가 조용히 사라진다.
  - 마크를 붙이는 자리와 사유를 붙이는 자리는 한 함수여야 한다(`reviewNote()` 호출부가 넷뿐이라 이론
    절·유도 카드·문풀이 화면에 안 떴고 같은 지적이 네 번 반복됐다).
  - 판정을 옮길 때는 그 판정을 잠그던 회귀 조항도 함께 옮긴다(`review-hide-drill` CSS 실례 — 13곳이
    '목록엔 있는데 안 칠해진' 상태였다).
  - 잠금 `test_review_change_is_binary` · `test_review_drill_fold_label`.
