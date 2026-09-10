# 논문 정리

읽은 논문을 한국어로 정리해 모아두는 곳. 논문 하나당 HTML 한 파일이고, 그림·표가 파일 안에 박혀 있어서 그 파일 하나만 열면 됩니다.

**👉 [정리 보러 가기](https://yeonuk-kim0120.github.io/paper-summaries/)**

관심 분야는 **6-DoF 물체 포즈 추적**과 **3D Gaussian Splatting** 입니다.

## 폴더

| 폴더 | 내용 |
|---|---|
| `docs/` | 결과물이자 공개 웹사이트. GitHub Pages 가 이 폴더를 서빙합니다. |
| `tools/` | `extract_pdf.py` (PDF → 텍스트·그림·표), `build_html.py` (이미지 인라인 + 목록 생성) |
| `templates/` | 정리 HTML 템플릿 |
| `papers/` | 원본 PDF. 저작권 때문에 저장소에는 올리지 않습니다 (`.gitignore`). |
| `work/` | 중간 산출물. 언제든 재생성 가능해서 역시 올리지 않습니다. |

## 만드는 법

```bash
pip install --user pymupdf

python3 tools/extract_pdf.py papers/<이름>.pdf   # → work/<slug>/ 에 텍스트·그림 추출
#   ... 논문을 읽고 work/<slug>/summary.html 작성 ...
python3 tools/build_html.py <slug>               # → docs/<slug>.html + docs/index.html
```

정리 본문은 Claude Code 로 씁니다. `papers/` 에 PDF 를 넣고 "논문 정리해줘" 라고 하면
[`.claude/skills/summarize-papers/SKILL.md`](.claude/skills/summarize-papers/SKILL.md) 절차대로 진행됩니다.

배포·인증 설정은 [`SETUP.md`](SETUP.md) 참고.

## 정리 원칙

- 직역이 아니라 **이해한 내용을 한국어로 설명**하는 글. 전문 용어는 한국어(영문) 병기.
- 숫자는 원문 그대로. 논문 안에서 숫자가 서로 어긋나면 그 사실을 정리에 적어둡니다.
- 그림·표는 원문에서 잘라낸 것을 쓰고, **쓰기 전에 반드시 직접 보고 확인**합니다.
- 마지막에 "정리와 시사점" — 한 문장 요약, 가져갈 아이디어, 같이 보면 좋은 논문.

## 주의

정리 안에는 원 논문에서 잘라낸 그림과 표가 들어 있습니다. 정확한 내용은 반드시 원문을 확인하세요.
각 정리 페이지 상단에 원문(arXiv·프로젝트 페이지) 링크가 있습니다.
