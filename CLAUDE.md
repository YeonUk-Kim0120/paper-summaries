# paper_summury — 논문 한국어 정리 저장소

`papers/` 에 넣어둔 PDF 논문을 읽고, 논문 하나당 한국어 정리 HTML 한 파일을 `docs/` 에 만드는 프로젝트.

## 폴더
- `papers/`      읽을 논문 PDF (사용자가 넣음)
- `docs/`        결과물이자 **공개 웹사이트**. `<slug>.html` (그림·표 base64 인라인, 단일 파일) + `index.html` (검색·태그 필터 목록)
                 GitHub Pages 가 이 폴더를 서빙한다. 폴더 이름을 바꾸면 사이트가 죽으니 주의.
- `work/`        중간 산출물 (추출 텍스트, 그림 클립, 페이지 렌더). 지워도 됨.
- `tools/`       `extract_pdf.py` (PDF → 텍스트/그림/표), `build_html.py` (이미지 인라인 + index 생성)
- `templates/`   정리 HTML 템플릿

## 사용
"논문 정리해줘" / "papers 처리해줘" / `/summarize-papers` → `.claude/skills/summarize-papers/SKILL.md` 절차를 따른다.
이미 정리된 논문은 건너뛰고, 새로 추가된 PDF 만 처리한다. 특정 논문만 다시 하려면 파일명을 말하면 된다.

## 규칙
- 정리는 한국어. 용어는 한국어(영문) 병기. 숫자는 원문 그대로.
- 그림/표는 `work/<slug>/figures/` 의 클립을 쓰고, 쓰기 전에 반드시 직접 보고 확인한다.
- 의존성: Python 3 + `pymupdf` (`pip install --user pymupdf`).
