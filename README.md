# 전공정리 빌드가이드

경북대 기계공학과 학생이 자기 전공 과목 학습 자료를 데이터(JSON)+단일 뷰어 템플릿으로 만든
파이프라인에서, **콘텐츠(과목 데이터)를 뺀 「만드는 방식」만** 옮겨 둔 참고용 저장소입니다.
이 저장소만으로는 사이트가 빌드되지 않습니다 — data/<과목>/chNN.json이 없기 때문입니다.
새 프로젝트를 시작할 때 참고할 뼈대로 쓰기 위한 것입니다.

## ⚠ 권한 설정을 그대로 켜지 마세요

`.claude/settings.json`은 **보수적 기본값**입니다 — 읽기 전용 명령 몇 개만 자동 승인되고,
나머지(파일 편집·스크립트 실행 등)는 매번 확인을 거칩니다. 원작자가 실제로 쓰던 폭넓은
자동 승인 설정(`defaultMode: auto` + Bash·Edit·Write 대량 허용)은 `.claude/settings.auto-example.json`에
**예시로만** 분리해 뒀습니다 — 그대로 활성화되지 않고, 켜려면 그 파일의 `permissions` 내용을
`settings.json`에 직접 옮겨야 합니다. 옮기는 순간부터 승인 없이 실행되는 범위가 넓어진다는
뜻이니, 자기 프로젝트·위험 감수 수준을 보고 골라서 가져가세요. 통째로 복붙하지 않기를 권합니다.

## 무엇이 들어 있나

- AGENTS.md — 작업 규칙 전문(콘텐츠 무단 창작 금지·독자성·삽화 표준·실행 규율 등). 이 저장소의
  핵심 문서입니다. 여기 있는 다른 모든 것은 이 문서가 설명하는 방식을 뒷받침하는 도구입니다.
- .claude/hooks/ — Claude Code가 매 도구 호출마다 스스로를 검사·차단하는 훅(가드).
  guard_bash.py·guard_write.py가 핵심 — 쓰기 경계·승인 배치·거부 규칙을 코드로 강제합니다.
- .claude/settings.json — 위 훅을 실제로 배선하는 설정(보수적 기본값). 개인 경로는 <…>로
  지워 뒀으니 자기 프로젝트에 맞게 채워야 합니다. 폭넓은 자동 승인 예시는
  .claude/settings.auto-example.json에 따로 있습니다(위 경고 참고).
- .claude/skills/ — 이 방식 특유의 판단 습관(내부 링크 앵커 단위, SVG 검사기 사각지대,
  교재 서술과 닮음 판정, 단위-기호 표기 충돌).
- tools/ — 빌드(build_site.py)·검사(audit_*.py)·수정(fix_*.py)·삽화 생성 조각
  (svg_dimension.py·svg_arc_arrow.py·svg_fraction.py·svg_exp_curve.py·svg_fan.py)·
  버전관리 도우미(commit.py·sync_common.py)가 전부 여기 있습니다. 도구 하나하나가 왜
  있는지는 AGENTS.md의 「도구 등록부」 절이 설명합니다.
- tools/test_checks.py — **starter 회귀 스위트**(아래 참고). AGENTS.md가 말하는
  「close = 재현 케이스 + 고친 형태가 통과하는 케이스가 이 파일에 들어간 상태」를 이
  저장소에서도 실제로 실행 가능하게 남긴 최소 예시입니다.
- site/template/ — 전 과목이 공유하는 유일한 뷰어 HTML 템플릿.
- docs/ — 삽화 규격·콘텐츠 표기 규약 등 「정본」이지만 매 세션 싣기엔 긴 문서. 원본 저장소의
  방대한 작업 로그·개인 원장(피드백 원장·세션 비용 기록 등)은 개인정보라 이 저장소에는
  빼 뒀습니다.

## ⚠ 검사기는 파이프라인을 태워야 작동합니다 — 저절로 잡아 주지 않습니다

`checks_content.py`·`checks_svg.py`의 검사(예: 수식 안 슬래시 분수 `math_slash_fraction_issues`)는
**`data/<과목>/chNN.json` → `python tools/build_site.py`** 경로를 실제로 지날 때만 작동합니다.
독립 HTML이나 이 파이프라인 밖에서 만든 콘텐츠는 이 검사들을 한 번도 거치지 않은 것과
같습니다 — "시스템에 검사기가 있다"는 것과 "이 콘텐츠가 검사받았다"는 것은 다른 말입니다.
새 콘텐츠를 만들 때마다 반드시 이 경로를 태우세요.

## 어떻게 시작하나

1. AGENTS.md를 읽습니다 — 원칙(무단 창작 금지·독자성·실행 규율)이 먼저입니다.
2. 위 권한 설정 경고를 읽고 `.claude/settings.json`의 <…> 자리를 자기 경로로 채웁니다.
3. .claude/SUBJECT.md.template를 복사해 첫 과목의 .claude/SUBJECT.md를 만듭니다.
4. data/<과목>/chNN.json 콘텐츠를 채우고 python tools/build_site.py로 빌드합니다(위 경고 참고
   — 이 경로를 태우지 않은 콘텐츠는 검사받지 않은 것입니다).
5. 결함을 하나 고칠 때마다 `tools/test_checks.py`에 같은 모양(결함 재현 + 고친 형태 통과)의
   케이스를 추가해 나갑니다 — 그래야 그 결함이 "close"됩니다(AGENTS.md 「close의 정의」).

## 뺀 것

- 실제 과목 데이터(data/)·빌드 산출물(site/<과목>/).
- 개인 원장·세션 로그·특정 과목 삽화 사양(docs/ 대부분)·수치 검산기(verify_*_answer.py,
  과목마다 정답이 박혀 있어 콘텐츠에 가깝습니다)·호스팅 배포 스크립트(Vercel 종속,
  deploy_all.py·build_home.py 포함).
- 원 프로젝트의 실제 회귀 테스트(25,000여 줄, 그 프로젝트 고유의 작업 이력) —
  대신 같은 패턴을 보여주는 **starter판 tools/test_checks.py**(4개 케이스)를 새로 만들어
  넣었습니다. 처음엔 아예 뺐다가, "검사기 코드는 있는데 실행 가능한 회귀 스위트가 하나도
  없으면 close 규율 자체가 이 저장소에서는 죽은 문장이 된다"는 지적을 받고 되살렸습니다.
- 웹폰트 실물(site/fonts/*.woff2) — 라이선스 서브셋이라 프로젝트마다 다시 뽑아야 합니다
  (tools/font_subset.py·tools/refresh_fonts.py가 방법입니다).
