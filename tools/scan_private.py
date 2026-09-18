# -*- coding: utf-8 -*-
"""**남에게 그대로 넘기면 안 되는 것**이 남아 있는지 훑는다.

    python _modding/scripts/scan_private.py           # 공용에 올리는 것 + 문서
    python _modding/scripts/scan_private.py --all     # 리포 전체 (곡·캐시 제외)
    python _modding/scripts/scan_private.py <경로>     # 올리기 **전에** 그 파일만
    python tools/scan_private.py --tracked            # 저장소 공유 전 Git 추적 파일만

왜 (2026-08-12, 사용자):
*[발화 생략]*

## 한 파일이 두 곳에서 다 돈다

공용 폴더(`~/Documents/naru`)와 이 리포 양쪽에서 **같은 파일**로 돈다.
두 벌이 되면 반드시 어긋나기 때문이다. 그래서 자리에 따라 달라지는 것
(뿌리 위치 · 예외 대장 경로 · 건너뛸 폴더)은 **전부 탐색으로 정한다.**

## 무엇이 걸리나 (걸린다고 다 지우는 것은 아니다 — 아래 판정선을 볼 것)

  ⑴ **사람·계정** — 실명, 이메일, 계정 ID, 토큰·키, **개인 프로필/전적 URL**
  ⑵ **기계 경로** — `C:\\Users\\<계정>\\…` 처럼 그 PC 에서만 뜻이 있는 절대 경로,
     개인 드라이브(`G:/내 드라이브/…`)
  ⑶ **소속** — 학교·회사 이름
  ⑷ **배포 대상** — 사이트 ID, 도메인, 대시보드 링크

## 판정선 — 지울 것과 남길 것

  **지운다:** 위 넷. 경로는 `<프로젝트 루트>`·`~/Documents/naru` 같은 **자리표**로 바꾼다.
  **남긴다:** *무엇을 했나*, *무엇이 문제였나*(실사고·지적 원문), *어떻게 고쳤나*.
  **그게 이 폴더의 값어치 전부다** — 규칙만 있고 왜 열렸는지가 없으면
  다음 사람은 그 규칙을 무시한다.

  ★★ **사용자 원문은 두 부류다 — 한 덩어리로 다루지 않는다** (2026-08-12 개정).
    처음엔 *[발화 생략]* 라고만 적었는데, 그 한 줄이
    **기술적 지적과 개인 상태를 같이 통과시켰다.** 실측: 원장에 **피로·집중 저하·기기 중단을 말한 1인칭 문장**이
    원문 그대로 남아 있었다(그 예를 여기 다시 옮기지 않는다 — 옮기면 이 문서가 같은 것을 재생산한다).
    실명·계정이 없어 이 검사에 안 걸리지만, **프로젝트·날짜와 묶이면 사람이 그려진다.**

      · **기술적 판단·결함 지적** → **원문 그대로 남긴다.** 그게 *어디서 데었는지*의 근거이고
        이 폴더의 값어치 전부다. 규칙만 있고 왜 열렸는지가 없으면 다음 사람은 무시한다.
      · **개인 상태·생활 상황·이력**(피로·집중·건강·학적·거주·기기 사정) →
        **관찰 서술로 바꾼다.** 예: **검수 후반부의 태도를 1인칭으로 적은 문장** →
        *[발화 생략]*
        **교훈은 그대로 남고 인과는 오히려 또렷해진다** — 잃는 것이 없다.
      · **계정·경로·기관·연락처** → 위 넷대로 자리표.

    ★ **이 검사는 둘째 부류를 못 잡는다.** 정규식으로 가릴 수 있는 것이 아니다 —
      **사람이 읽고 판정하는 몫**이고, 이 문단이 그 판정선이다. 그러니 `0건` 을
      *[발화 생략]* 로 읽지 말 것(범위를 안 밝힌 0건은 「없다」가 아니다).
"""
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent          # 공용: 폴더뿌리 / XSanity: _modding
REPO = ROOT.parent                                     # XSanity 리포 뿌리 (공용에선 안 씀)

# `~대` 로 끝나는 흔한 낱말 — 학교가 아니다(첫 실행에서 이것들이 오탐의 전부였다).
# ★ 프로젝트마다 말투가 달라 여기 다 못 담는다 — **예외 대장이 정본**이고 이건 시드일 뿐이다.
#   2026-08-14 에 셋을 더했다 — `.html` 을 훑기 시작하자 **오탐 16건이 전부 이 셋**이었다
#   (`무한대` 수학 · `지지대` 역학 · `분수대` 조판). 셋 다 프로젝트 데이터가 아니라
#   **한국어 기술 문서의 일반 낱말**이라 예외 대장이 아니라 여기가 자리다 —
#   대장에 넣으면 같은 낱말을 프로젝트마다 다시 적게 된다.
#   2026-08-14 (같은 날, 기계재료) — `지렛대` 하나를 더했다. **발행 표면 게이트를 켜자마자
#   걸린 유일한 1건**이고(`scan_private site` · `site/기계재료/ch10.html`) 이것도 프로젝트
#   이름이 아니라 **용어**다 — 상태도의 «지렛대 규칙(lever rule)». 상태도를 다루는 과목은
#   전부 이 낱말을 쓰므로 예외 대장이 아니라 여기가 자리다(바로 위 판정과 같다).
#   2026-08-14 (같은 날, 열역학) — `예컨대`·`전망대` 둘. 같은 게이트를 켜자 뜬 것이고
#   («예컨대» 는 어느 산문에나 나오고 «전망대» 는 일반 명사다) 판정은 위 셋과 같다.
#   2026-08-25 (공용 폴더) — `토큰대` 하나. 「2만 토큰대」의 **수량 범위**이고 위 넷과 같은
#   부류다(프로젝트 데이터가 아니라 한국어 일반 낱말이라 예외 대장이 아니라 여기가 자리다).
# ★ **학교 쪽을 목록으로 두는 것이 「학교가 아닌 것」쪽보다 낫다** (2026-09-07).
#   `NOT_A_SCHOOL` 은 **한국어 기술 용어가 늘어나는 만큼** 자란다(열전대·작업대·원뿔대·
#   시험대·버팀대·운반대·시간대·불감대·급확대·실습대·단자대·주축대 … 끝이 없다).
#   반대로 **대학 약칭의 어간은 닫힌 집합**이다 — 나라 안 대학 수만큼이고 새로 안 생긴다.
#   그래서 신고 조건을 «어간이 이 목록에 있거나 · 소속 맥락 낱말이 곁에 있거나» 로 둔다.
#   ☐ 못 잡는 것: 목록에 없는 학교의 약칭이 맥락 낱말 없이 홀로 나오는 줄. 완전형
#     (`대학교`·`대학`)은 무조건 잡으므로 그쪽으로 새는 것은 여전히 걸린다.
#   ★ `고대`·`연대`·`교대`·`체대`·`현대` 는 **넣지 않는다** — 아래 `NOT_A_SCHOOL` 이
#     이미 일반 낱말로 판정한 것들이라, 넣으면 그 판정을 뒤집어 오탐이 쏟아진다.
SCHOOL_STEMS = "|".join((
    "경북", "서울", "연세", "한양", "성균", "부산", "전남", "전북", "충남", "충북",
    "경희", "중앙", "동국", "건국", "홍익", "아주", "인하", "단국", "숭실", "세종",
    "국민", "광운", "명지", "상명", "가천", "영남", "계명", "대구", "울산", "창원",
    "강원", "제주", "공주", "순천", "조선", "원광", "동아", "경남", "한성", "삼육",
))

NOT_A_SCHOOL = {"사각지대", "반존대", "정반대", "절대", "상대", "반대", "시대", "세대",
                "기대", "확대", "축소대", "최대", "고대", "현대", "교대", "연대", "체대",
                "무한대", "지지대", "분수대", "지렛대", "예컨대", "전망대",
                "토큰대"}

# ★ `~대` 는 낱말 꼬리만이 아니라 **종결어미**로도 온다 — `지웠대`·`먹었대`·`갔대`.
#   낱말이 아니라 **활용형**이라 위 시드에 넣으면 끝이 없다(어간마다 새 줄이 생긴다).
#   2026-08-25 (공용 폴더) 열림: `지웠대` 를 시드로 처리하려다 열었다. 그 1건을 인박스에
#   **오탐 목록으로 인용하자 2건이 됐다** — 시드 방식은 인용 한 번에 다시 자란다.
#   그래서 부류로 막는다: **받침이 `ㅆ` 인 음절 + `대`**. 한글 음절은
#   `0xAC00 + (초성*21 + 중성)*28 + 종성` 이고 `ㅆ` 의 종성 번호가 20 이다.
#   ★ **학교 이름은 이 꼴이 될 수 없다** — `경북대`·`충남대`·`부경대` 는 앞 음절 받침이
#     `ㄱ·ㅁ·ㅇ` 이다. 그래서 이 면제는 진짜 학교를 못 보게 만들지 않는다(아래 양성 대조군).
#   ☐ **못 보는 것**: `-ㄴ대`(`간대`)·`-는대` 꼴은 안 뺀다 — 이 저장소에서 아직 안 걸렸고,
#     안 걸린 것을 미리 빼면 그만큼 진짜를 놓친다. 걸리면 그때 사유와 함께 넓힌다.
def _is_verb_ending(s):
    """`았/었/였 + 대` 꼴의 종결어미인가 — 학교 이름이 아니다."""
    if len(s) < 2 or not s.endswith("대"):
        return False
    prev = s[-2]
    return "가" <= prev <= "힣" and (ord(prev) - 0xAC00) % 28 == 20
# ★★ `.html`·`.js`·`.css`·`.svg` 는 2026-08-14 에 더했다 — **산출물이 웹 페이지인 프로젝트에서
#   이 검사가 통째로 헛돌고 있었다.** 실측: `scan_private site/고체역학` 이 13개를 전부 건너뛰고
#   *[발화 생략]* 를 찍었다. 그 폴더는 **배포하는 자리**다.
#   ☞ 빌드가 템플릿을 문자열로 읽어 자리표만 치우므로 템플릿의 **개발 주석이 발행 페이지에
#     그대로 실린다**(ch11.html 217줄) — 정확히 이 검사가 봐야 할 부류인데 못 보고 있었다.
#   `.yml`·`.yaml`·`.toml`·`.ini`·`.cfg` 는 설정에 배포 대상·계정이 자주 적혀 같이 넣는다.
SUFFIXES = (".md", ".py", ".ps1", ".txt", ".json", ".csv", ".vbs",
            ".html", ".htm", ".js", ".css", ".svg",
            ".yml", ".yaml", ".toml", ".ini", ".cfg")

# 확장자가 없어도 **이름이 곧 형식**인 텍스트 파일. `LICENSE` 가 안 훑기고 있었다.
TEXT_NAMES = {"LICENSE", "NOTICE", "AUTHORS", "CITATION", "CODEOWNERS"}

# ★ 훑지 않을 폴더. XSanity 는 `Songs/` 만 5,000파일이라 안 빼면 몇 분씩 걸린다.
#   공용 폴더에는 이런 이름이 없으므로 그쪽에서는 아무것도 안 걸린다 — 같은 파일이 양쪽에서 돈다.
# ★ `아티팩트-백업`(공용 폴더) — 2026-09-11 실측. 그 폴더는 **이미 공개된** dcinside 갤러리
#   게시물의 백업이라, 대학 이름·배포 도메인이 그 게시물의 소재이지 소속·비밀이 아니다.
#   이 검사가 겨눈 것은 «공개 전» 표면이다 — 이미 공개된 것의 백업은 그 반대다.
#   문자열을 예외 대장에 하나씩 적으면 다음 달 게시물의 새 대학 이름마다 또 걸린다.
SKIP_DIRS = {"__pycache__", ".git", "Songs", "Cache", "Themes", "NoteSkins",
             "_retired", "Save", "node_modules", ".venv", "아티팩트-백업"}

# 예외 대장은 프로젝트마다 자리가 다르다 — **찾아서** 쓴다(경로를 코드에 박지 않는다).
LEDGER_NAMES = ("개인정보-예외.txt", "private_allow.txt")

# 이 표식이 있는 줄은 건너뛴다 — 검사의 테스트 픽스처용.
# 문자열을 쪼개 두는 이유: 이 파일 자신이 자기 표식에 걸리지 않게(그리고 검색으로 찾히게).
FIXTURE = "scan-private" + ":fixture"

# (이름, 정규식, 처방) — 이름은 보고에 그대로 찍힌다.
RULES = [
    # 앞 경계를 안 두면 `noreply@…` 의 `o` 부터 다시 물어 제외가 무력해진다(첫 실행에서 그랬다).
    ("이메일", re.compile(r"(?<![\w.+-])[\w.+-]+@(?!anthropic\.com)[\w-]+\.[\w.]+"), "지운다"),
    # 이미 자리표로 바꾼 것(`C:\\Users\\<사용자>`·`%USERNAME%`·`$USER`)은 **고친 결과**다.
    # 이걸 계속 신고하면 고쳐도 0 이 안 되고, 0 이 안 되는 게이트는 곧 무시된다.
    # ★ 드라이브 문자는 **선택**이다. `settings.json` 처럼 `/Users/<계정>/…` 로 적는 자리가
    #   있어서 `C:` 를 요구하면 그대로 새어나간다 (공용 폴더에서 실제로 5건 있었다).
    #   ★ 구분자가 **두 개**일 수 있다 — JSON·파이썬 문자열 안에서는 `C:\\\\Users\\\\…` 로
    #     이스케이프된다. `[\\\\/]` 하나만 보면 그런 줄은 통째로 새어나간다
    #     (공용 `훅/settings.json` 의 `additionalDirectories` 가 실제로 안 걸렸다).
    ("사용자 홈 경로",
     re.compile(r"(?:[A-Za-z]:)?[\\/]{1,2}Users[\\/]{1,2}(?![<%$])[^\\/\s'\"]+"),
     "`<홈>` 또는 `~` 로"),
    ("개인 드라이브", re.compile(r"[A-Za-z]:[\\/](?:내 드라이브|My Drive)"), "`<백업 위치>` 로"),
    # ★ 2026-08-12 XSanity 에서 추가 — **개인 전적·프로필 URL.**
    #   `5keyddr…/player/41` 이 안 걸려서 그대로 공용에 올라갈 뻔했다. 사이트 이름이 아니라
    #   **`프로필류 경로 + 숫자/아이디`** 꼴을 잡는다 — 사이트를 코드에 박지 않기 위해서다.
    #   ★ **호스트를 요구한다.** 처음엔 `/(player|user|…)/<id>` 만 봤더니
    #     `/Users/Administrator` 같은 **파일 경로**를 계정 URL 로 오인했다(공용에서 5건).
    #     경로는 위 「사용자 홈 경로」가 볼 일이다 — 규칙끼리 겹치면 이름이 거짓말을 한다.
    ("개인 계정 URL",
     re.compile(r"(?:https?://|(?<![\w.])[\w-]+(?:\.[\w-]+){1,3}(?::\d+)?)"
                r"/(?:player|profile|users?|members?|mypage)/[\w.-]{1,32}\b", re.I),
     "`<내 아이디>` 로"),
    # ★ `~대` 는 낱말 꼬리로도 흔해서(`사각지대`·`반존대`·`정반대`) 그대로 잡으면 **오탐이 절반**이다
    #   (첫 실행 실측 50건 중 23건). 그래서 ⑴ `대학교`·`대학` 은 그대로 잡고
    #   ⑵ `~대` 단독은 **아래 낱말이 아닐 때만** 신고한다.
    # ★★ **`~대` 단독은 「소속 맥락 낱말」이 곁에 있을 때만 신고한다** (좁힘 2026-09-07).
    #   경위 — 평탄화로 `site/` 에 21과목이 함께 오자 발행 표면에서 **18건 중 16건이 오탐**이
    #   됐다: 열전대·작업대·원뿔대·시험대·버팀대·운반대·시간대·불감대·급확대·실습대·단자대·
    #   주축대·들이대. 전부 **한국어 공학 용어의 꼬리**다. 시드 목록(`NOT_A_SCHOOL`)에 열넷을
    #   더하는 것은 이 파일이 이미 «인용 한 번에 다시 자란다» 고 판정한 방식이라 안 쓴다.
    #   → 부류로 막는다: 학교 약칭은 **거의 언제나 소속 맥락 낱말과 함께** 나온다.
    #   `대학교`·`대학`·`고등학교` 완전형은 그대로 무조건 잡는다(맥락이 필요 없다).
    #   ☐ 못 잡는 것: 맥락 낱말 없이 약칭만 있는 줄(«경북대 도서관»). 완전형이 아니면
    #     사람이 봐야 한다 — 이 한계를 지우지 않는다.
    ("학교·회사", re.compile(
        r"[가-힣]{2,4}(?:대학교|대학(?![가-힣])|고등학교)"
        r"|(?<![가-힣])(?:" + SCHOOL_STEMS + r")대(?![가-힣])"
        r"|(?<![가-힣])[가-힣]{2}대(?![가-힣])"
        r"(?=.{0,14}?(?:대학|학교|학부|학과|캠퍼스|재학|졸업|입학|학번|수업|강의|교수|LMS))"),
     "지우거나 일반화"),
    # 값이 아니라 **변수 이름**(`SiteId`·`site_id`)은 비밀이 아니다 — 실제 값이 붙었을 때만 잡는다.
    ("배포 대상", re.compile(r"(?:netlify|vercel|github)\.(?:app|com|io)"
                          r"|site[_-]?id\s*[:=]\s*['\"]?[\w-]{8,}", re.I), "자리표로"),
    ("토큰·키", re.compile(r"(?:token|api[_-]?key|secret)\s*[:=]\s*['\"]?[\w-]{12,}", re.I),
     "즉시 지운다"),
]


def find_ledger(root):
    """예외 대장을 **찾는다.** 공용은 `기록/`, XSanity 는 `out/` 에 둔다."""
    for base in (root if root.is_dir() else root.parent, ROOT):
        for name in LEDGER_NAMES:
            for hit in list(base.glob(name)) + list(base.glob("*/" + name)):
                if hit.is_file():
                    return hit
    return None


def load_allow(root):
    """{걸린 문자열}. **사유가 없는 줄은 예외로 치지 않는다.**

    ★ 예외 창구가 없으면 이 검사는 **영영 exit 1** 이 되고, 늘 실패하는 게이트는
      곧 무시된다(경보 피로). 그렇다고 무조건 통과시키면 검사가 장식이 된다 —
      그래서 `문자열 | 사유` 형식으로 **판정을 적게** 만든다.
    """
    ledger = find_ledger(root)
    allow = set()
    if not ledger:
        return allow
    for line in ledger.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        text, _, why = line.partition("|")
        if text.strip() and why.strip():
            allow.add(text.strip())
    return allow


def _is_text(path, explicit):
    """훑을 값어치가 있는 텍스트인가.

    확장자 필터는 **폴더를 훑을 때** 잡음을 줄이려는 것이지 지목한 파일을 건너뛰라는
    뜻이 아니다(`.githooks/pre-commit` 선례). 그래서 `explicit` 이면 무조건 참.
    """
    if explicit:
        return True
    if path.suffix.lower() in SUFFIXES or path.name in TEXT_NAMES:
        return True
    # `launch.json.example` 처럼 **알려진 확장자 뒤에 꼬리표**가 붙은 것
    return Path(path.stem).suffix.lower() in SUFFIXES


def partition(root):
    """(훑을 것, 건너뛴 것) — **읽는 쪽과 세는 쪽이 같은 함수를 쓴다.**

    열린 날 2026-08-12. 옛 판본은 훑는 루프와 `scanned_files()` 가 **각자** 조건을 적어
    `실제로 읽은 파일 46개` 라고 찍고 정작 45개를 읽었다(자기 자신을 루프에서만 건너뛰었다).
    한 개 차이가 사소해 보이지만 이 도구의 출력 전체가 *[발화 생략]* 를
    말하는 것이라, **세는 수가 틀리면 그 문장이 통째로 거짓말이 된다.**
    같은 이유로 **건너뛴 것도 돌려준다** — 안 훑은 파일을 말하지 않는 `0건` 은
    이 폴더가 스스로 금지한 「범위를 안 밝힌 0건」이다.
    """
    explicit = root.is_file()
    if explicit:
        paths = [root]
    else:
        paths = [p for p in sorted(root.rglob("*"))
                 if p.is_file()
                 and not SKIP_DIRS.intersection(p.relative_to(root).parts)]
    read, skipped = [], []
    for p in paths:
        if p.name == "scan_private.py":
            continue                    # 자기 자신 — 규칙 정규식이 전부 자기에게 걸린다
        (read if _is_text(p, explicit) else skipped).append(p)
    return read, skipped


def tracked_partition(root):
    """Git 추적 파일만 `(읽을 것, 건너뛸 것)`로. 저장소 공유 표면의 분모다."""
    r = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root),
                        "ls-files", "-z"], capture_output=True)
    if r.returncode != 0:
        return [], []
    paths = [root / p for p in r.stdout.decode("utf-8", errors="replace").split("\0") if p]
    read, skipped = [], []
    for path in paths:
        if not path.is_file() or path.name == "scan_private.py":
            continue
        (read if _is_text(path, False) else skipped).append(path)
    return read, skipped


def scan_paths(paths, allow):
    """주어진 텍스트 파일 목록의 개인정보 후보. `scan`과 `--tracked`가 함께 쓴다."""
    hits = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            # ★ 검사의 **테스트 픽스처**는 본질적으로 규칙에 걸려야 하는 문자열이다.
            #   예외 대장에 넣으면 파일과 대장이 갈라지고, 그 파일을 공용에 올릴 때
            #   대장은 안 따라간다. 그래서 **표식을 그 줄에 붙인다** — 픽스처와 면제가
            #   같은 줄에 있으니 갈라질 자리가 없다.
            if FIXTURE in line:
                continue
            for name, pattern, fix in RULES:
                m = pattern.search(line)
                if (m and m.group(0) not in NOT_A_SCHOOL
                        and not _is_verb_ending(m.group(0))
                        and m.group(0) not in allow):
                    hits.append((path, lineno, name, fix, m.group(0)[:48]))
                    break
    return hits


def scan(root, allow=None):
    """[(파일, 줄번호, 규칙, 처방, 미리보기)]. 순수 함수 — 테스트가 직접 부른다."""
    allow = load_allow(root) if allow is None else allow
    return scan_paths(partition(root)[0], allow)


COMPOUND_FALSE_POSITIVES = {"버팀대", "받침대", "시험대", "고지대", "승강대", "운반대", "실습대"}
TRACKED_CATEGORIES = ("사용자 절대경로", "소속 식별자", "테스트 시료", "한국어 합성어 오탐", "기타 민감값")


def tracked_category(path, rule, sample):
    """추적 저장소 후보를 공유 전 판정 부류로 가른다. 순수 함수 — 테스트 대상."""
    if sample in COMPOUND_FALSE_POSITIVES:
        return "한국어 합성어 오탐"
    if path.name == "test_checks.py" or "example.invalid" in sample or "example.com" in sample:
        return "테스트 시료"
    if rule == "사용자 홈 경로":
        return "사용자 절대경로"
    if rule == "학교·회사":
        return "소속 식별자"
    return "기타 민감값"


def manifest_sources():
    """공용으로 **실제로 올라가는** 원본들. 목록은 매니페스트가 말한다 (규칙 4c).

    ★ 기본 범위를 이걸로 잡는 이유: 이 검사의 목적은 *[발화 생략]* 이고,
      넘어가는 것은 매니페스트에 적힌 것뿐이다. 리포 전체를 기본으로 잡았더니
      **공용에 안 올라가는 로컬 스크립트의 경로까지** 신고해서, 고칠 수도 없고
      고칠 이유도 없는 11건이 계속 떴다. **늘 실패하는 게이트는 곧 무시된다.**
      (리포 전체를 보고 싶으면 `--all`)
    """
    import csv
    mf = ROOT / "shared_system.csv"
    if not mf.is_file():
        return []
    lines = [ln for ln in mf.read_text(encoding="utf-8-sig").splitlines()
             if not ln.lstrip().startswith("#")]
    out = []
    for r in csv.DictReader(lines):
        src = (r.get("원본") or "").strip()
        if src and (REPO / src).exists():
            out.append(REPO / src)
    return out


def targets_of(argv):
    """무엇을 훑을지."""
    args = [a for a in argv if not a.startswith("-")]
    if args:
        return [Path(args[0]).resolve()], f"지정 경로 {args[0]}"
    if "--all" in argv:
        return [ROOT if ROOT.name != "_modding" else REPO], "리포 전체 (곡·캐시 제외)"
    # 공용 폴더에서 돌 때는 `ROOT` 가 그 폴더 자신이라 그대로 전부 훑는다.
    if ROOT.name != "_modding":
        return [ROOT], "공용 폴더 전체"
    picks = manifest_sources()
    return picks, f"공용으로 올라가는 원본 {len(picks)}건 (shared_system.csv)"


def scanned_files(root):
    """실제로 읽은 파일 수 — 「0건」이 *깨끗해서* 인지 *안 훑어서* 인지 구별하려고 센다."""
    return len(partition(root)[0])


def selftest():
    """★ 붙임 2026-08-25 — 이 자는 **막는 자인데 대조군이 없었다.**

    「0건」을 내는 자라 특히 위험하다 — 자가 못 보면 **깨끗한 것과 겉모습이 같다**
    (공용 「규칙/증거의-정직.md」 ⑴). 그래서 **양성 대조군**이 핵심이다.
    """
    import tempfile
    bad = 0

    def chk(desc, cond, got=""):
        nonlocal bad
        bad += 0 if cond else 1
        print("  %s %-46s %s" % ("OK  " if cond else "**틀림**", desc, got))

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        # ★ 미끼는 **이 자가 실제로 보는 것**이어야 한다 (2026-08-25). 처음엔 전화번호를
        #   심었다가 «양성인데 0건» 이 나왔는데, **틀린 것은 자가 아니라 내 미끼였다** —
        #   이 자의 규칙은 이메일·홈 경로·개인 드라이브·프로필 URL 넷이고 전화번호는 없다.
        #   ☐ 그 사실 자체가 이 자의 한계다: **전화번호는 안 걸린다.**
        (root / "a.md").write_text("문의는 hong@example.com 으로\n", encoding="utf-8")
        hits = scan(root, allow=set())
        chk("★ 양성 — 심어 둔 것을 실제로 잡는다 (이게 없으면 0건이 「없다」인지 모른다)",
            len(hits) >= 1, "%d건" % len(hits))

        (root / "b.md").write_text("아무것도 없다\n", encoding="utf-8")
        only_b = scan(root / "b.md", allow=set())
        chk("음성 — 깨끗한 파일은 0건", only_b == [], str(only_b))

        # ★★ `~대` 면제는 **진짜를 가릴 수 있는 종류**의 면제라, 넓히는 줄과 같은 자리에
        #   **양성 대조군**이 같이 서야 한다. 음성만 두면 「오탐 0건」과 「아무것도 안 본다」가
        #   겉모습이 같아진다 (공용 「규칙/증거의-정직.md」 ⑴). 2026-08-25 붙임.
        (root / "c.md").write_text("경북대 산학협력단\n", encoding="utf-8")
        hit_c = scan(root / "c.md", allow=set())
        chk("★ 양성 — 어미 면제를 붙여도 **진짜 학교 이름은 그대로 잡는다**",
            len(hit_c) == 1 and hit_c[0][4] == "경북대", str(hit_c))

        (root / "d.md").write_text("그 줄은 지웠대\n먹었대\n2만 토큰대\n", encoding="utf-8")
        hit_d = scan(root / "d.md", allow=set())
        chk("음성 — `지웠대`·`먹었대`(어미)와 `토큰대`(낱말)는 안 잡는다",
            hit_d == [], str(hit_d))

        read, skipped = partition(root)
        chk("훑은 것과 건너뛴 것을 **둘 다** 돌려준다 (범위 안 밝힌 0건 금지)",
            isinstance(read, list) and isinstance(skipped, list),
            "읽음 %d · 건너뜀 %d" % (len(read), len(skipped)))

        led = root / "기록"
        led.mkdir()
        (led / "개인정보-예외.txt").write_text(
            "# 주석\n010-1234-5678 | 시료라 예외\n사유없음\n", encoding="utf-8")
        allow = load_allow(root)
        chk("★ **사유 없는 줄은 예외로 안 친다**", allow == {"010-1234-5678"}, str(allow))

    print()
    print("  ※ ☐ 이 자가 **못 보는 것**: 규칙에 없는 형태의 개인정보는 안 걸린다.")
    print("     「0건」은 «없다» 가 아니라 **«이 규칙들로는 없다»** 이다.")
    print("[자기 검정] %s" % ("전부 통과" if not bad else "**%d건 틀림**" % bad))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        print("[자기 검정] 개인정보 스캔")
        return selftest()
    tracked_mode = "--tracked" in sys.argv
    if tracked_mode:
        positional = [a for a in sys.argv[1:] if not a.startswith("-")]
        repo = Path(positional[0]).resolve() if positional else Path.cwd().resolve()
        roots, what = [repo], "Git 추적 파일 (저장소 공유 표면)"
    else:
        roots, what = targets_of(sys.argv[1:])
    hits = []
    n_files = 0
    skipped = []
    if tracked_mode:
        read, skipped = tracked_partition(roots[0])
        hits = scan_paths(read, load_allow(roots[0]))
        n_files = len(read)
    else:
        for r in roots:
            hits += scan(r)
            read, skip = partition(r)
            n_files += len(read)
            skipped += skip
    # ★ 순회 범위를 안 밝힌 `0건` 은 「없다」가 아니라 「거기까지는 없다」이다.
    print(f"scan_private — 순회 범위: {what}  · 실제로 읽은 파일 {n_files}개")
    if skipped:
        # 안 훑은 것을 **이름으로** 말한다. 수만 말하면 무엇이 빠졌는지 알 수 없다.
        print("  훑지 않음 %d개(텍스트로 안 보이는 확장자 — 사람이 볼 것): %s"
              % (len(skipped), " · ".join(p.name for p in skipped)))
    ledger = find_ledger(roots[0]) if roots else None
    print(f"  예외 대장: {ledger if ledger else '없음 (사유 없는 줄은 예외로 안 친다)'}")

    by_file = {}
    for path, lineno, name, fix, sample in hits:
        by_file.setdefault(path, []).append((lineno, name, fix, sample))
    for path in sorted(by_file):
        try:
            shown = path.relative_to(REPO)
        except ValueError:
            shown = path
        print("\n=== %s ===" % shown)
        for lineno, name, fix, sample in by_file[path][:12]:
            category = ("[%s] " % tracked_category(path, name, sample)) if tracked_mode else ""
            print("  %5d  %s%-12s %-16s %s" % (lineno, category, name, fix, sample))
        if len(by_file[path]) > 12:
            print("  … 그 파일에 %d건 더" % (len(by_file[path]) - 12))
    # ★★ **한 글자도 안 읽고 「넘겨도 된다」를 찍지 않는다** (2026-08-14, 실사고).
    #   `.html` 이 확장자 목록에 없어 산출물 폴더 13개를 전부 건너뛰고도 마지막 줄이
    #   *[발화 생략]* 였다. 범위는 위에 정직하게 찍혀 있었지만
    #   **읽는 사람은 마지막 줄을 판정으로 읽는다** — 그 한 줄이 범위 고지를 덮었다.
    #   「범위를 안 밝힌 0건」(규칙 11)의 변종이다: 밝히기는 했는데 **결론이 그걸 무시했다.**
    verdict = ""
    actionable = hits
    if tracked_mode:
        counts = {name: 0 for name in TRACKED_CATEGORIES}
        for path, _lineno, name, _fix, sample in hits:
            counts[tracked_category(path, name, sample)] += 1
        print("\n분류 — " + " · ".join("%s %d건" % (name, counts[name]) for name in TRACKED_CATEGORIES))
        actionable = [h for h in hits if tracked_category(h[0], h[2], h[4])
                      not in ("테스트 시료", "한국어 합성어 오탐")]
        print("저장소 공유 차단 후보 %d건 (테스트 시료·한국어 합성어 오탐은 분리)" % len(actionable))
    if not hits:
        verdict = ("  — 그대로 넘겨도 되는 상태다" if n_files
                   else "  — ★ 그런데 **읽은 파일이 0개다.** 통과가 아니라 «훑지 않았다»이다")
    print("\n%d건 / 파일 %d개%s" % (len(hits), len(by_file), verdict))
    # ★ **실패로 끝낸다** — 올리기 전에 도는 검사라 조용히 통과하면 뜻이 없다.
    #   읽은 것이 0개인데 대상이 있었으면 그것도 실패다(위 주석).
    return 1 if actionable or (skipped and not n_files) else 0


if __name__ == "__main__":
    raise SystemExit(main())
