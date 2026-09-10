#!/usr/bin/env python3
"""
논문 PDF 를 URL 에서 받아 papers/ 에 넣는다. 노션 목록에서 이어받을 때 쓴다.

사용법:
  python3 tools/fetch_papers.py status
        현재 papers/ 와 docs/ 현황 (정리 완료 / PDF 만 있음 / 없음)

  python3 tools/fetch_papers.py add <slug> <url> [<slug> <url> ...]
        받아서 papers/<slug>.pdf 로 저장. 이미 정리된 논문은 건너뛴다.

  python3 tools/fetch_papers.py add --force <slug> <url>
        이미 정리됐어도 다시 받는다.

  python3 tools/fetch_papers.py add --dry-run <slug> <url> ...
        뭘 받을지만 출력하고 실제로 받지는 않는다.

동작:
  - arXiv abs/ 링크는 pdf/ 로 자동 변환한다.
  - docs/<slug>.html 이 있으면 (= 이미 정리 완료) 건너뛴다.
  - papers/<slug>.pdf 가 이미 있으면 건너뛴다.
  - 받은 파일이 진짜 PDF 인지 매직바이트로 확인하고, 아니면 지운다.
    (arXiv 가 rate limit 에 걸리면 HTML 안내 페이지를 200 으로 돌려주기 때문)
  - arXiv 예의상 요청 사이에 3초 쉰다.
"""
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS, DOCS = ROOT / "papers", ROOT / "docs"

UA = "Mozilla/5.0 (X11; Linux x86_64) paper-summary-bot/1.0 (personal research use)"
DELAY = 3.0          # arXiv 연속 요청 간격 (초)
MIN_SIZE = 20_000    # 이보다 작으면 논문 PDF 가 아니라고 본다


def normalize(url: str) -> str:
    """arXiv abs 링크를 pdf 링크로. 나머지는 그대로."""
    m = re.match(r"https?://arxiv\.org/abs/([\w.\-/]+?)(v\d+)?/?$", url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}{m.group(2) or ''}"
    return url


def slug_ok(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", s))


def status():
    done, pdf_only = [], []
    for p in sorted(PAPERS.glob("*.pdf")):
        (done if (DOCS / f"{p.stem}.html").exists() else pdf_only).append(p.stem)
    orphan = sorted(
        f.stem for f in DOCS.glob("*.html")
        if f.stem != "index" and not (PAPERS / f"{f.stem}.pdf").exists()
    )
    print(f"정리 완료 ({len(done)}): {', '.join(done) or '-'}")
    print(f"PDF 만 있음 ({len(pdf_only)}): {', '.join(pdf_only) or '-'}")
    if orphan:
        print(f"PDF 없이 정리만 있음 ({len(orphan)}): {', '.join(orphan)}")


def fetch(slug: str, url: str, force: bool, dry: bool) -> str:
    """반환: 'skip' | 'ok' | 'fail'"""
    if not slug_ok(slug):
        print(f"  ✗ {slug}: slug 에 쓸 수 없는 문자 (영문/숫자/._- 만)")
        return "fail"
    if (DOCS / f"{slug}.html").exists() and not force:
        print(f"  · {slug}: 이미 정리됨 → 건너뜀 (--force 로 강제)")
        return "skip"
    dst = PAPERS / f"{slug}.pdf"
    if dst.exists() and not force:
        print(f"  · {slug}: PDF 이미 있음 ({dst.stat().st_size/1e6:.1f} MB) → 건너뜀")
        return "skip"

    url = normalize(url)
    if dry:
        print(f"  → {slug}  {url}")
        return "ok"

    PAPERS.mkdir(exist_ok=True)
    tmp = dst.with_suffix(".pdf.part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 16):
                f.write(chunk)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        tmp.unlink(missing_ok=True)
        print(f"  ✗ {slug}: 받기 실패 — {e}")
        return "fail"

    size = tmp.stat().st_size
    head = tmp.open("rb").read(5)
    if head != b"%PDF-" or size < MIN_SIZE:
        tmp.unlink()
        why = "PDF 가 아님" if head != b"%PDF-" else f"너무 작음 ({size}B)"
        print(f"  ✗ {slug}: {why} — URL 확인 필요 (arXiv rate limit 일 수도)")
        return "fail"

    tmp.replace(dst)
    print(f"  ✓ {slug}: {size/1e6:.1f} MB  ← {url}")
    return "ok"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "status":
        status()
        return
    if cmd != "add":
        sys.exit(f"모르는 명령: {cmd}")

    args = sys.argv[2:]
    force = "--force" in args
    dry = "--dry-run" in args
    args = [a for a in args if a not in ("--force", "--dry-run")]
    if not args or len(args) % 2:
        sys.exit("<slug> <url> 쌍으로 넣어야 한다.")

    pairs = list(zip(args[::2], args[1::2]))
    print(f"{'[예행연습] ' if dry else ''}{len(pairs)}편 처리")
    counts = {"ok": 0, "skip": 0, "fail": 0}
    for i, (slug, url) in enumerate(pairs):
        counts[fetch(slug, url, force, dry)] += 1
        if not dry and i < len(pairs) - 1:
            time.sleep(DELAY)
    print(f"\n받음 {counts['ok']} · 건너뜀 {counts['skip']} · 실패 {counts['fail']}")
    if counts["ok"] and not dry:
        got = [s for s, _ in pairs if (PAPERS / f"{s}.pdf").exists()
               and not (DOCS / f"{s}.html").exists()]
        print(f"다음: 이 논문들을 정리하면 된다 → {', '.join(got)}")
    if counts["fail"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
