# 배포 · 인증 설정 메모

사이트: **https://yeonuk-kim0120.github.io/paper-summaries/**
저장소: `Yeonuk-Kim0120/paper-summaries` · 브랜치 `main` · Pages 소스 `main` + `/docs`

## 지금 상태 (2026-09-10)

| 항목 | 상태 |
|---|---|
| GitHub 저장소 · Pages | ✅ 설정 완료 |
| VS Code 에서 push | ✅ 됨 (`Ctrl+Shift+P` → `Git: Push`) |
| 터미널/자동화에서 push | ❌ **안 됨** — 자격증명이 VS Code 안에만 있음 |
| SSH 키 (`~/.ssh/id_ed25519`) | 생성만 해둠. GitHub 에 **등록 안 함** |

즉 지금은 **정리를 만든 뒤 VS Code 에서 Push 를 직접 눌러야** 사이트에 반영된다.
그게 귀찮아지면 아래 절차로 키를 등록하면 push 까지 자동으로 끝난다.

---

## push 자동화하려면 (나중에 필요할 때)

### 1. 공개키 출력

```bash
cat ~/.ssh/id_ed25519.pub
```

키가 없으면 먼저 만든다:

```bash
ssh-keygen -t ed25519 -C "kimyeonuk0120@gmail.com" -f ~/.ssh/id_ed25519 -N ""
```

출력되는 `ssh-ed25519 AAAA...` 한 줄 전체를 복사한다.
**이건 공개키라서 남에게 보여도 안전하다.** 짝이 되는 비밀키(`~/.ssh/id_ed25519`, 확장자 없는 쪽)는 절대 공유하지 않는다.

### 2. GitHub 에 등록 — 두 가지 방식 중 선택

#### 방식 A. Deploy key (이 저장소 하나만)

1. https://github.com/Yeonuk-Kim0120/paper-summaries/settings/keys
2. **Add deploy key**
3. Title: 아무거나 (예: `KIST 데스크탑 자동화`)
4. Key: 1번에서 복사한 한 줄
5. ⚠️ **`Allow write access` 체크** — 안 하면 읽기만 되고 push 가 안 된다
6. **Add key**

#### 방식 B. 계정 SSH 키 (내 모든 저장소)

1. https://github.com/settings/ssh/new
2. Title / Key 채우고 **Add SSH key**

#### 어느 쪽을 고를까

|  | Deploy key | 계정 SSH 키 |
|---|---|---|
| 범위 | 이 저장소 **하나만** | 내가 쓰기 권한 가진 **모든 저장소** |
| 자동화에 맡길 때 | 사고 범위가 이 저장소로 한정 | 사고 나면 전체 저장소 영향 |
| 저장소가 여러 개일 때 | 저장소마다 **다른 키**를 새로 만들어야 함 (GitHub 이 같은 키의 중복 등록을 막음) | 키 하나로 전부 커버 |

자동화 대상이 이 저장소 하나면 **Deploy key**, 여러 저장소를 자동으로 다룰 거면 **계정 키**가 편하다.

### 3. remote 를 SSH 로 바꾸기

```bash
cd ~/Desktop/paper_summury
git remote set-url origin git@github.com:Yeonuk-Kim0120/paper-summaries.git

# 확인 (처음 한 번은 호스트 지문 확인 y/n 이 뜬다)
ssh -T git@github.com
git push
```

`Hi Yeonuk-Kim0120/paper-summaries! You've successfully authenticated, but GitHub does not provide shell access.`
같은 메시지가 나오면 성공이다 (deploy key 는 저장소 이름이, 계정 키는 사용자 이름이 나온다).

### 4. 되돌리기

```bash
# HTTPS 로 원복 (다시 VS Code 로만 push)
git remote set-url origin https://github.com/Yeonuk-Kim0120/paper-summaries.git

# 키 자체를 없애기
rm ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
```
GitHub 쪽에서도 등록했던 키를 지운다 (위 등록 페이지에서 삭제).

---

## GitHub Pages 를 다시 설정해야 한다면

https://github.com/Yeonuk-Kim0120/paper-summaries/settings/pages

- **Source**: `Deploy from a branch`
- **Branch**: `main` + **`/docs`** ← 기본값이 `/ (root)` 라서 반드시 바꿔야 한다
- Save 후 1~3분 뒤 반영

`docs/.nojekyll` 은 GitHub 이 Jekyll 로 파일을 건드리지 않게 하는 빈 파일이다. 지우지 말 것.

## 저장소에 올라가지 않는 것

`.gitignore` 로 제외 중이다.

- `papers/` — 원본 논문 PDF. 저작권 + 용량(230MB+)
- `work/` — 중간 산출물. `extract_pdf.py` 로 언제든 재생성 가능(118MB)

그래서 저장소를 새 PC 에 clone 하면 `docs/`(완성된 정리)와 `tools/`(파이프라인)는 있지만
원본 PDF 와 중간 파일은 없다. 논문을 다시 처리하려면 PDF 를 `papers/` 에 다시 넣으면 된다.
