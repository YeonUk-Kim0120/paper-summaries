# paper_summury — 논문 한국어 정리 저장소

`papers/` 에 넣어둔 PDF 논문을 읽고, 논문 하나당 한국어 정리 HTML 한 파일을 `docs/` 에 만드는 프로젝트.

## 폴더
- `papers/`      읽을 논문 PDF (사용자가 넣음)
- `docs/`        결과물이자 **공개 웹사이트**. `<slug>.html` (그림·표 base64 인라인, 단일 파일) + `index.html` (검색·태그 필터 목록)
                 GitHub Pages 가 이 폴더를 서빙한다. 폴더 이름을 바꾸면 사이트가 죽으니 주의.
- `work/`        중간 산출물 (추출 텍스트, 그림 클립, 페이지 렌더). 지워도 됨.
- `tools/`       `extract_pdf.py` (PDF → 텍스트/그림/표), `build_html.py` (이미지 인라인 + index 생성),
                 `fetch_papers.py` (URL → papers/ 다운로드, 중복 스킵)
- `templates/`   정리 HTML 템플릿

## 사용
논문이 들어오는 경로가 둘이다.

1. **직접 넣기** — `papers/` 에 PDF 를 넣고 "논문 정리해줘" / "papers 처리해줘" / `/summarize-papers`
   → `.claude/skills/summarize-papers/SKILL.md`
2. **노션에서 이어받기** — "노션 논문 진행해" / `/papers-from-notion`
   → `.claude/skills/papers-from-notion/SKILL.md`
   매주 월요일 클라우드 루틴이 노션 "📖 논문" 페이지에 적어둔 추천 논문을 받아와서 1번 절차로 넘긴다.

어느 쪽이든 이미 정리된 논문(`docs/<slug>.html` 존재)은 건너뛴다. 특정 논문만 다시 하려면 파일명을 말하면 된다.

## 배포
`docs/` 는 GitHub Pages 로 공개된다 → **https://yeonuk-kim0120.github.io/paper-summaries/**
정리를 만든 뒤 `git push` 하면 1~2분 안에 사이트에 반영된다 (remote: `Yeonuk-Kim0120/paper-summaries`, 브랜치 `main`, Pages 소스 `/docs`).

**주의: Claude 가 쓰는 셸에서는 `git push` 가 실패한다** (`could not read Username`).
자격증명이 VS Code 의 askpass 를 거치는데, VS Code 는 **자기가 띄운 통합 터미널에만**
`GIT_ASKPASS` 를 주입하기 때문이다. Claude 의 셸은 그 밖에서 뜬다.

따라서 커밋까지만 하고, 사용자에게 둘 중 하나를 안내할 것:
- VS Code **통합 터미널**에서 `git push`
- 또는 `Ctrl+Shift+P` → `Git: Push`

Claude 가 push 까지 하려면 SSH 키 등록이 필요하다. 절차는 [`SETUP.md`](SETUP.md).

## 규칙
- 정리는 한국어. 용어는 한국어(영문) 병기. 숫자는 원문 그대로.
- 그림/표는 `work/<slug>/figures/` 의 클립을 쓰고, 쓰기 전에 반드시 직접 보고 확인한다.
- 의존성: Python 3 + `pymupdf` (`pip install --user pymupdf`).
