---
name: summarize-papers
description: papers/ 폴더의 PDF 논문을 분석해 논문 하나당 한국어 정리 HTML(그림·표 포함, 단일 파일)을 docs/ 에 만든다. "논문 정리해줘", "papers 처리해줘", "/summarize-papers" 로 실행.
---

# 논문 → 한국어 정리 HTML

## 전체 흐름

```
papers/<name>.pdf
  └─ python3 tools/extract_pdf.py papers/<name>.pdf   → work/<slug>/{text.md, manifest.md, meta.json, figures/, pages/, contact_sheet.png}
  └─ (Claude) 읽고 분석 → work/<slug>/summary.html 작성 (templates/paper_template.html 기반)
  └─ python3 tools/build_html.py <slug>               → docs/<slug>.html (이미지 base64 인라인, 단일 파일) + docs/index.html
```

slug 는 파일명에서 확장자를 뺀 것 (특수문자는 `_`). 스크립트가 출력하는 `slug` 값을 그대로 쓴다.

## 절차

### 0. 대상 결정
- `ls papers/*.pdf` 로 목록 확인. `docs/<slug>.html` 이 이미 있고 PDF 보다 최신이면 **건너뛴다** (사용자가 "다시" 라고 하면 재생성).
- 사용자가 특정 논문을 지목하면 그것만.
- **논문이 2편 이상이면 논문마다 서브에이전트(general-purpose) 하나씩 병렬로** 돌린다. 서브에이전트에게는 이 SKILL.md 경로와 담당 PDF 경로를 알려주고 1~5 단계를 수행하게 한다. 메인 에이전트는 마지막에 `python3 tools/build_html.py --index` 로 목록을 갱신하고 결과를 보고한다.

### 1. 추출
```
python3 tools/extract_pdf.py papers/<name>.pdf
```
- `work/<slug>/meta.json` 에서 제목·페이지 수 확인.
- `work/<slug>/manifest.md` 에서 그림/표 목록과 캡션 확인. `자동 클립 실패` 항목이 있으면 3단계에서 수동 처리.

### 2. 읽기
- `work/<slug>/text.md` 를 **전부** 읽는다 (길면 나눠서). 본문은 정독, 부록은 필요한 부분만.
- 정확히 파악할 것: 문제 정의, 핵심 아이디어, 각 구성요소의 역할과 이유, 손실/수식, 데이터셋·지표·베이스라인, 주요 수치, ablation 에서 드러나는 각 요소의 기여, 저자가 밝힌 한계.
- 참고문헌 번호 `[12]` 는 정리문에서 빼거나 방법 이름으로 바꾼다.

### 3. 그림/표 검수 (필수)
- `work/<slug>/contact_sheet.png` 를 Read 로 **한 번에 확인**한다. 잘못 잘린 것(다른 그림이 섞임, 본문이 딸려옴, 잘림)이 있으면 `work/<slug>/pages/page-NNN.png` 를 보고 좌표를 잡아 수동 클립:
  ```
  python3 tools/extract_pdf.py papers/<name>.pdf --clip <page>,<x0>,<y0>,<x1>,<y1> --name fig-3
  ```
  (좌표는 PDF pt. 페이지 이미지는 90dpi 이므로 픽셀 × 0.8 = pt.) 좌표를 정확히 잡으려면 먼저
  `python3 tools/extract_pdf.py papers/<name>.pdf --blocks <page>` 로 그 페이지의 텍스트 블록·이미지 좌표를 출력해 캡션과 그림의 bbox 를 확인한 뒤 클립한다.
  주의: `extract_pdf.py` 를 옵션 없이 다시 돌리면 figures/ 가 자동 클립으로 덮어써지므로, 수동 클립은 마지막에 한다.
- 정리에 **실제로 쓸 그림은 개별 파일을 Read 로 직접 보고** 내용을 이해한 뒤 설명한다. 보지 않은 그림을 상상으로 설명하지 않는다.
- 어떤 그림/표를 넣을지 기준: 개요(pipeline) 그림, 방법의 핵심 아이디어 그림, 주요 결과 표, ablation 표, 대표 정성 결과 1~2개. 부록의 반복적인 정성 결과나 데이터셋 시각화는 보통 생략. 전부 넣는 것보다 필요한 것을 설명과 함께 넣는 게 목표.

### 4. summary.html 작성
`templates/paper_template.html` 을 읽고 그 구조/CSS 를 그대로 사용해 `work/<slug>/summary.html` 을 쓴다. 이미지 경로는 `figures/fig-N.png` 처럼 **work/<slug>/ 기준 상대경로**.

내용 원칙:
- **한국어로 "정리"**한다. 직역이 아니라 이해한 내용을 설명하는 글. 친근하지만 정확하게 ("~해요/~한다" 어느 쪽이든 문서 안에서 통일).
- 전문 용어는 한국어 뒤에 영문 병기: 예) 부호 거리 함수(Signed Distance Function, SDF). 널리 쓰이는 영문 약어(SDF, NeRF, ADD-S)는 그대로.
- **숫자는 원문 그대로** (지표, 개선폭, 파라미터, 속도). 표 수치를 옮길 때 대조할 것.
- 수식은 핵심만 KaTeX (`$...$`, `$$...$$`) 로. 기호 뜻을 바로 아래에 풀어쓴다. 수식 안의 `<`, `>` 는 `&lt;`, `&gt;` 로 쓴다 (빌드가 자동 보정하긴 하지만 습관적으로). 본문 텍스트의 `$` 기호(달러)는 `&#36;` 로.
- 그림마다 `<figcaption>` 에 원 캡션의 **한국어 번역**을 넣고, 이해에 도움이 되면 `.fig-note` 로 "이 그림에서 볼 것"을 덧붙인다.
- 핵심 결과 표 1~2개는 이미지 외에 한국어 HTML 표로 재구성 (`tr.ours`, `td.best` 클래스 활용). 나머지 표는 이미지만.
- `callout` 으로 "왜 이렇게 설계했나", `callout warn` 으로 주의점/한계를 강조.
- 마지막에 "정리와 시사점": 한 문장 요약, 이 논문에서 가져갈 아이디어, 같이 보면 좋은 논문(본문에서 비교되는 주요 방법들).
- `<head>` 의 메타(`title`, `paper:original-title`, `paper:venue`, `paper:year`, `paper:tags`, `description`) 를 **반드시** 채운다 — index 카드에 쓰인다. 템플릿의 `{{...}}` 자리표시자가 남아있으면 안 된다.
- 분량: 본문 기준 A4 3~6장 정도. 논문의 핵심을 다 담되 장황하지 않게.

### 5. 빌드 & 확인
```
python3 tools/build_html.py <slug>
```
- `찾지 못한 이미지` 경고가 없어야 한다. `{{` 가 남아있는지 `grep -c '{{' docs/<slug>.html` 로 확인 (0 이어야 함).
- 결과 파일 크기가 15MB 를 넘으면 쓰는 그림 수를 줄이거나 부록 그림을 뺀다.
- 렌더링 확인 (Chrome 이 있을 때): 스크린샷을 찍어 Read 로 본다. 레이아웃 깨짐, 그림 누락, 표 넘침이 없는지 확인.
  ```
  google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars --window-size=1300,2600 \
    --screenshot=<scratchpad>/check.png file://$PWD/docs/<slug>.html
  ```

## 보고
끝나면 사용자에게: 만든 파일 경로, 논문별 한 줄 요약, 수동 처리한 그림이나 확신이 낮은 부분(예: 표를 텍스트로 옮기며 불확실했던 값)을 짧게 알린다.
