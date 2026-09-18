# site/fonts — 이 자료가 싣고 다니는 글꼴

여기 있는 `.woff2` 는 **원본 글꼴의 부분집합**이다. 화면에 실제로 나오는 글자만 남겼다.

## 왜 싣는가

뷰어 CSS 는 읽는 자리에 명조를, 나머지에 산세리프를 선언한다. 그런데 **선언한 것과 그려지는
것은 다르다** — 2026-08-13 브라우저 실측에서 이 기기에는 `Nanum Myeongjo` 도 `Noto Serif KR`
도 **설치돼 있지 않았고**(폭이 «없는 글꼴»과 정확히 같았다) 시스템 폴백이 본문을 그리고 있었다.
즉 **독자 기기마다 다른 글꼴로 보였다.** 조판을 재는 자들(`checks_svg.run_width` 등)이 전제한
글꼴도 아니다. 글꼴을 함께 실으면 그 두 문제가 같이 닫힌다.

## 무엇을 실었나

| 파일 | 원본 | 굵기 | 쓰는 자리 |
|---|---|---|---|
| `JeongriSans-Regular.woff2` | Pretendard v1.3.9 Regular | 400 | **본문 전부** |
| `JeongriSans-SemiBold.woff2` | Pretendard v1.3.9 SemiBold | 600 | 작은 한글 라벨 보정 |
| `JeongriSans-Bold.woff2` | Pretendard v1.3.9 Bold | 700 | 강조·제목 |
| `JeongriSerif-Bold.woff2` | 나눔명조 Bold | 700 | **19px 이상만** — 표지·공식 이름·번호 |

## ★★ 명조는 19px 이상에서만 쓴다 (실측 2026-08-13)

사용자 지적 *[발화 생략]* 를 재서 나온 규칙이다.
잉크 중 **진한 픽셀 비율**(높을수록 또렷 · 한글 9자 평균, 브라우저 캔버스 실측):

| 명조 13px | 15.5px | 17px | **19px** | 22px | 28px | 산세리프 15.5px |
|---|---|---|---|---|---|---|
| 24.9 | 28.4 | 30.9 | **36.0** | 36.3 | 42.6 | **32.7** |

- **19px 부터 산세리프를 넘고 그 아래에서는 진다.** 특히 `를` 은 39 vs 69 로 갈린다 —
  ㄹ 은 가로획이 셋이라 1px 밑으로 떨어지면 회색으로 뭉친다.
- **글꼴을 바꿔서 될 일이 아니었다** — Noto Serif KR 을 굵기 400·500·600 으로 뽑아 같은 자로
  재니 15.1 / 22.6 / 28.6 으로 **더 나빴다.** 명조의 얇은 가로획은 설계이고, 15.5px 화면
  격자에서는 어느 명조든 같은 자리에서 무너진다.
- 그래서 **세리프는 굵은 것 하나만** 싣는다 — 19px 이상 자리가 전부 `font-weight:700` 이라
  400 은 아무도 안 쓴다(실측 확인 후 뺐다).

원본 출처 — Pretendard: `github.com/orioncactus/pretendard` v1.3.9 공식 릴리스 ·
나눔명조: `github.com/google/fonts/ofl/nanummyeongjo`(NAVER Corporation).

## 저작권 — 왜 이름이 다른가

원본 둘 다 **SIL Open Font License 1.1** 이다(전문은 이 폴더의 `OFL-*.txt`).
그 라이선스는 자체 호스팅·재배포를 허용하지만 **예약 이름(Reserved Font Name)** 조항이 붙는다.

> OFL FAQ: *[발화 생략]*

- Pretendard 의 예약 이름: `Pretendard` · `Source` · `Inter` · `M PLUS 1`
- 나눔글꼴의 예약 이름: `NanumMyeongjo` · `Nanum` 계열

**부분집합은 «수정본»이므로 원래 이름을 쓸 수 없다.** 그래서 `Jeongri Sans`·`Jeongri Serif`
로 이름을 바꿨고, 글꼴 안의 이름표(nameID 1·2·4·6·16·17)에도 같은 이름을 박았다 —
한 곳만 바꾸면 브라우저와 OS 가 서로 다른 이름으로 본다.

★ **이름을 바꾸는 것은 출처를 감추는 것이 아니다.** 그 조항의 목적은 *원본과 헷갈리지 않게
하라*는 것이고, 출처는 위 표와 `OFL-*.txt` 가 밝힌다. 원본을 쓰고 싶은 사람은 그 이름으로
공식 배포처에서 받으면 된다.

## 다시 만들 때

```
python tools/font_subset.py corpus                       # 지금 쓰는 글자를 센다
python tools/font_subset.py build --src=<원본> --as="Jeongri Serif" --style=Bold
```

★★ **부분집합은 «오늘 내용»에 묶여 있다.** 새 낱말이 들어오면 그 글자만 두부가 된다.
그래서 빌드가 **말뭉치에 없는 글자**를 세어 알린다 — 그 경고가 뜨면 여기를 다시 만든다.
원본 글꼴 파일은 리포에 두지 않는다(수 MB짜리 넷이다). 아래 주소에서 다시 받는다.

### ★★ 다시 만드는 데 사용자 허가를 묻지 않는다 (판정 2026-09-08)

사용자 원문:

> *[발화 생략]*
> *[발화 생략]*

- **묻지 않고 받아서 다시 만든다.** 바깥 다운로드이지만 ⑴ 글꼴 종류와 판(v1.3.9)은 이미
  정해져 있고 ⑵ 하는 일이 **같은 글꼴에서 빠진 글자만 채우는 것**이라 새로 정할 판단이 없다.
- 그전에는 빌드가 두부 글자를 경고해도 「사용자 승인이 필요한 바깥 다운로드」로 보고
  미완으로 남겼다 — 2026-09-08 새벽에 그 상태로 세 번(뮤·퓰 · 껐·픈 · 잣·쥔) 넘겼다.
  **경고가 뜨면 그 자리에서 다시 만든다.**
- 바뀌는 것이면 여전히 묻는다: **다른 글꼴로 갈아타기 · 판 올리기 · 라이선스가 다른 것**.

### 원본을 어디서 받나 (2026-08-13 실측 — 이 주소로 넷 다 받았다)

**받은 파일은 스크래치패드에 둔다.** 리포에 커밋하지 않는다(넷 합쳐 7.8 MB 이고, 실어야 할
것은 부분집합 넷 964 KB 뿐이다 — 이 차이가 부분집합을 쓰는 이유 그대로다).

```
curl -sL -o <스크래치패드>/Pretendard-Regular.otf  https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static/Pretendard-Regular.otf
curl -sL -o <스크래치패드>/Pretendard-SemiBold.otf https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static/Pretendard-SemiBold.otf
curl -sL -o <스크래치패드>/Pretendard-Bold.otf     https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/packages/pretendard/dist/public/static/Pretendard-Bold.otf
curl -sL -o <스크래치패드>/NanumMyeongjo-Bold.ttf  https://raw.githubusercontent.com/google/fonts/main/ofl/nanummyeongjo/NanumMyeongjo-Bold.ttf
```

그다음 네 얼굴을 뽑는다 — `--style` 값이 곧 산출물 이름이 된다.

```
python tools/font_subset.py build --src=<...>/Pretendard-Regular.otf  --as="Jeongri Sans"  --style=Regular
python tools/font_subset.py build --src=<...>/Pretendard-SemiBold.otf --as="Jeongri Sans"  --style=SemiBold
python tools/font_subset.py build --src=<...>/Pretendard-Bold.otf     --as="Jeongri Sans"  --style=Bold
python tools/font_subset.py build --src=<...>/NanumMyeongjo-Bold.ttf  --as="Jeongri Serif" --style=Bold
```

★ **이 기기에 설치된 Pretendard 를 쓰지 않는다.** `C:\Windows\Fonts` 에 있긴 하지만
⑴ 리포 밖이라 읽기 허용 범위가 아니고(AGENTS 규칙 9) ⑵ 더 큰 이유는 **버전을 모른다**는 것이다 —
부분집합은 조판을 재는 자들의 전제라, 원본이 v1.3.9 가 아니면 그 자들이 다른 글꼴을 재게 된다.

★ 실측 크기(말뭉치 **1,054자** 기준): 산세 191.7~194.0 KB · 명조 619.0 KB.
말뭉치 수는 내용이 늘면 함께 는다 — `corpus.json` 이 그때의 값을 갖는다.
