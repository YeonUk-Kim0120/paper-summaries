#!/usr/bin/env python3
"""
PDF 논문에서 텍스트 / 그림 / 표를 뽑아내는 스크립트.

사용법:
  python3 tools/extract_pdf.py papers/foo.pdf                # -> work/foo/ 에 산출물 생성
  python3 tools/extract_pdf.py papers/foo.pdf --dpi 220      # 클립 해상도 조절
  python3 tools/extract_pdf.py papers/foo.pdf --blocks 3                 # 3페이지 블록 좌표 보기
  python3 tools/extract_pdf.py papers/foo.pdf --clip 3,40,80,560,420 --name fig-2
        # 자동 클립이 잘못됐을 때 수동으로 (페이지번호(1-base), x0,y0,x1,y1 in PDF pt) 잘라내기

산출물 (work/<slug>/):
  text.md          페이지별 전체 텍스트 (## Page N)
  manifest.md      찾은 그림/표 목록 + 캡션 + 파일 경로 (+ find_tables 로 뽑은 표 마크다운)
  meta.json        제목 추정, 페이지 수, 그림/표 개수
  figures/         fig-N.png, table-N.png  (캡션 포함해서 잘라낸 이미지)
  pages/           page-NNN.png            (전체 페이지 렌더, 확인용/수동 클립 좌표 참고용)
"""
import argparse, json, os, re, sys, statistics
from pathlib import Path

import pymupdf  # PyMuPDF

CAPTION_RE = re.compile(
    r"^\s*(?P<kind>Fig(?:ure)?|Table|Algorithm)\.?\s*(?P<num>S?\d+|[IVX]+)\s*[.:|\-–—]?\s",
    re.IGNORECASE,
)


HEADING_RE = re.compile(r"^\s*(\d+(\.\d+)*\.?|[A-Z]\.|Appendix\s+[A-Z])\s+[A-Z][^\n]{2,80}$")


def slugify(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", name).strip("_")
    return s or "paper"


def block_text(b):
    return b[4].strip() if len(b) > 4 else ""


def is_body_block(b, col_w, gfx=()):
    """본문 문단으로 보이는 블록인지 (폭이 넓고, 줄이 빽빽하고, 괘선이 겹치지 않음)."""
    x0, y0, x1, y1 = b[:4]
    t = block_text(b)
    w = x1 - x0
    if w <= col_w * 0.7 or len(t) <= 180 or t.count("\n") < 3:
        return False
    lines = [l for l in t.split("\n") if l.strip()]
    density = (sum(len(l) for l in lines) / len(lines)) / w  # 줄당 글자수 / 폭 (본문 ≈ 0.18~0.22)
    if density < 0.14:
        return False  # 표처럼 띄엄띄엄 있는 텍스트
    r = pymupdf.Rect(x0, y0, x1, y1)
    rules = sum(1 for g in gfx if g.intersects(r) and g.width > w * 0.5 and g.height < 3)
    return rules < 2  # 가로 괘선이 2개 이상 겹치면 표


def merge_caption(blocks, idx, col_w):
    """캡션이 여러 블록으로 쪼개진 경우 이어붙임."""
    b = blocks[idx]
    text = block_text(b)
    x0, y0, x1, y1 = b[:4]
    for nb in blocks[idx + 1:]:
        nx0, ny0, nx1, ny1 = nb[:4]
        if ny0 - y1 > 6 or abs(nx0 - x0) > 20:
            break
        nt = block_text(nb)
        if CAPTION_RE.match(nt) or len(nt) > 600 or HEADING_RE.match(nt):
            break
        if re.search(r"[.!?]\s*$", text):
            break  # 캡션 문장이 이미 끝났으면 다음 블록은 본문
        text += " " + nt
        y1 = ny1
        x1 = max(x1, nx1)
        if len(text) > 900:
            break
    return re.sub(r"\s+", " ", text).strip(), pymupdf.Rect(x0, y0, x1, y1)


def is_prose(b, col_w, gfx=()):
    """본문 문장 블록인지 (2줄 이상, 폭 넓고, 줄이 빽빽함). 영역 탐색을 멈추는 기준."""
    x0, y0, x1, y1 = b[:4]
    t = block_text(b)
    w = x1 - x0
    lines = [l for l in t.split("\n") if l.strip()]
    if HEADING_RE.match(t) and len(lines) <= 2:
        return True  # 섹션 제목
    if not lines or w < col_w * 0.6:
        return False
    density = (sum(len(l) for l in lines) / len(lines)) / w
    if len(lines) == 1:
        return w > col_w * 0.85 and density >= 0.16
    if density < 0.14:
        return False
    r = pymupdf.Rect(x0, y0, x1, y1)
    rules = sum(1 for g in gfx if g.intersects(r) and g.width > w * 0.5 and g.height < 3)
    return rules < 2


def x_overlap_ok(a, b):
    ov = min(a.x1, b.x1) - max(a.x0, b.x0)
    return ov > 0.3 * min(a.width, b.width)


def region_for(page, cap_rect, blocks, gfx_rects, col_w, direction, caption_idx, cur_idx, other_caps=(), headings=()):
    """캡션 위(direction=-1) 또는 아래(+1)로 요소를 하나씩 더해가며 그림/표 영역을 찾음.
    본문 문단, 다른 캡션, 큰 빈틈을 만나면 멈춤. 실패하면 None."""
    pw, ph = page.rect.width, page.rect.height
    cands = []

    def on_side(r):
        if direction < 0:
            return r.y1 <= cap_rect.y0 + 4 and r.y0 < cap_rect.y0 - 1
        return r.y0 >= cap_rect.y1 - 4 and r.y1 > cap_rect.y1 + 1

    for r in gfx_rects:
        if (r.width * r.height) > 0.45 * pw * ph or r.height > ph * 0.6:
            continue  # 페이지 배경/거대한 클립 영역
        if not ((r.width > 3 and r.height > 3) or r.width > 30):
            continue
        if on_side(r) and x_overlap_ok(r, cap_rect):
            cands.append((r, "gfx"))
    single_col = cap_rect.width < pw * 0.55
    col_lo = (pw / 2 + 4) if (single_col and cap_rect.x0 > pw / 2 - 20) else 0
    col_hi = (pw / 2 - 4) if (single_col and cap_rect.x1 < pw / 2 + 20) else pw
    for i, b in enumerate(blocks):
        r = pymupdf.Rect(b[:4])
        if i == cur_idx or not on_side(r) or not x_overlap_ok(r, cap_rect):
            continue
        if i in caption_idx or HEADING_RE.match(block_text(b)):
            kind = "hard"   # 다른 캡션/섹션 제목: 그래픽 bbox 가 덮고 있어도 여기서 잘라냄
        elif is_prose(b, col_w, gfx_rects):
            kind = "stop"
        else:
            kind = "txt"
        if kind == "txt" and single_col and (r.x0 < col_lo - 15 or r.x1 > col_hi + 15) and r.width > cap_rect.width * 1.3:
            kind = "hard"  # 단일 컬럼 그림인데 양쪽 컬럼에 걸친 텍스트(논문 제목 등)
        cands.append((r, kind))

    for r in headings:
        if on_side(r) and x_overlap_ok(r, cap_rect):
            cands.append((r, "hard"))
    cands.sort(key=(lambda c: -c[0].y1) if direction < 0 else (lambda c: c[0].y0))
    union = None
    edge = cap_rect.y0 if direction < 0 else cap_rect.y1
    def claimed_by_other(r):
        """r 가 현재 캡션보다 다른 캡션에 (그 캡션의 통상적인 방향으로) 더 가까우면 True."""
        d_cur = (cap_rect.y0 - r.y1) if direction < 0 else (r.y0 - cap_rect.y1)
        for orect, okind in other_caps:
            if not x_overlap_ok(orect, r):
                continue
            if direction < 0:   # 위로 스캔 중 → 더 위에 있는 캡션(표 캡션은 표 위에 옴)
                if okind == "table" and orect.y1 <= r.y0 + 2 and (r.y0 - orect.y1) < d_cur:
                    return True
            else:               # 아래로 스캔 중 → 더 아래에 있는 캡션(그림 캡션은 그림 아래에 옴)
                if okind == "fig" and orect.y0 >= r.y1 - 2 and (orect.y0 - r.y1) < d_cur:
                    return True
        return False

    for r, kind in cands:
        if kind == "txt" or kind == "gfx":
            if claimed_by_other(r):
                break
        else:
            inside = union is not None and ((direction < 0 and r.y0 >= union.y0 - 1) or (direction > 0 and r.y1 <= union.y1 + 1))
            if inside and kind == "stop":
                continue
            if inside and kind == "hard":
                # 그래픽 여백 bbox 가 제목/캡션을 덮은 경우 → 그 직전에서 자름
                if direction < 0:
                    union = pymupdf.Rect(union.x0, r.y1 + 2, union.x1, union.y1)
                else:
                    union = pymupdf.Rect(union.x0, union.y0, union.x1, r.y0 - 2)
            break
        gap = (edge - r.y1) if direction < 0 else (r.y0 - edge)
        if gap > (45 if union is not None else 120):
            break
        union = r if union is None else union | r
        edge = union.y0 if direction < 0 else union.y1
    if union is None or union.height < 20 or union.width < 40:
        return None
    rect = union | cap_rect
    pad_top, pad_bot = (6, 2) if direction < 0 else (2, 6)  # 캡션 쪽은 살짝만
    rect = pymupdf.Rect(max(rect.x0, col_lo) - 4, rect.y0 - pad_top, min(rect.x1, col_hi) + 4, rect.y1 + pad_bot) & page.rect
    return rect


def heading_line_rects(page, body_size):
    """굵은 글씨 + 제목 패턴인 '줄'의 bbox (블록이 그림 텍스트와 섞여도 잡기 위함)."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(sp["text"] for sp in spans).strip()
            if not HEADING_RE.match(text):
                continue
            bold = any(sp["flags"] & 16 or "bold" in sp["font"].lower() for sp in spans)
            big = max(sp["size"] for sp in spans) > body_size + 0.5
            if bold or big:
                out.append(pymupdf.Rect(line["bbox"]))
    return out


def gfx_rects_of(page):
    rects = []
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r and r.is_valid and not r.is_empty:
                rects.append(pymupdf.Rect(r))
    except Exception:
        pass
    try:
        for info in page.get_image_info():
            rects.append(pymupdf.Rect(info["bbox"]))
    except Exception:
        pass
    return rects


def make_contact_sheet(figdir, path, cols=3, cell=520):
    """figures/ 의 모든 클립을 한 장에 타일링 (검수용)."""
    files = sorted(figdir.glob("*.png"), key=lambda f: (f.stem.split("-")[0], int(re.sub(r"\D", "", f.stem) or 0)))
    if not files:
        return
    rows = (len(files) + cols - 1) // cols
    W, H = cols * cell, rows * (cell + 24)
    sheet = pymupdf.open()
    page = sheet.new_page(width=W, height=H)
    for i, f in enumerate(files):
        c, r = i % cols, i // cols
        x, y = c * cell, r * (cell + 24)
        page.insert_text((x + 6, y + 16), f.stem, fontsize=12, color=(0.8, 0, 0))
        page.draw_rect(pymupdf.Rect(x + 2, y + 22, x + cell - 2, y + cell + 20), color=(0.7, 0.7, 0.7), width=0.5)
        try:
            page.insert_image(pymupdf.Rect(x + 6, y + 26, x + cell - 6, y + cell + 16), filename=str(f), keep_proportion=True)
        except Exception:
            pass
    page.get_pixmap(dpi=72).save(path)
    sheet.close()


def guess_title(doc):
    page = doc[0]
    best, best_size = "", 0
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for line in b.get("lines", []):
            if abs(line.get("dir", (1, 0))[0] - 1) > 0.01:
                continue  # 세로 텍스트(arXiv 워터마크) 제외
            for span in line.get("spans", []):
                t = span["text"].strip()
                if t and "arxiv" not in t.lower():
                    spans.append((span["size"], t))
    for size, t in spans:
        if size > best_size and len(t) > 8:
            best_size, best = size, t
    # 같은 크기의 span 들을 이어붙임
    parts = [t for size, t in spans if abs(size - best_size) < 0.5]
    return " ".join(parts).strip() or best or doc.metadata.get("title", "")


def table_markdown(page):
    out = []
    try:
        tabs = page.find_tables()
    except Exception:
        return out
    for i, t in enumerate(tabs):
        try:
            rows = t.extract()
        except Exception:
            continue
        rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in rows if r and any(c for c in r)]
        if len(rows) < 2 or len(rows[0]) < 2:
            continue
        w = max(len(r) for r in rows)
        rows = [r + [""] * (w - len(r)) for r in rows]
        md = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w]
        md += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        out.append("\n".join(md))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", help="출력 폴더 (기본 work/<slug>)")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--page-dpi", type=int, default=90)
    ap.add_argument("--clip", help="수동 클립: page,x0,y0,x1,y1 (page는 1부터, 좌표는 PDF pt)")
    ap.add_argument("--name", help="수동 클립 파일명 (확장자 제외)")
    ap.add_argument("--blocks", type=int, help="해당 페이지(1부터)의 텍스트 블록/이미지 좌표를 출력 (수동 클립 좌표 잡을 때)")
    args = ap.parse_args()

    pdf = Path(args.pdf)
    slug = slugify(pdf.stem)
    out = Path(args.out) if args.out else Path("work") / slug
    figdir, pagedir = out / "figures", out / "pages"
    figdir.mkdir(parents=True, exist_ok=True)
    pagedir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf)

    # ---- 좌표 확인 모드 ----
    if args.blocks:
        page = doc[args.blocks - 1]
        print(f"page {args.blocks}  size=({page.rect.width:.0f} x {page.rect.height:.0f}) pt")
        for b in page.get_text("blocks"):
            if len(b) > 6 and b[6] == 0:
                t = block_text(b).replace("\n", " ")[:70]
                print(f"  text  ({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})  {t}")
        for info in page.get_image_info():
            x0, y0, x1, y1 = info["bbox"]
            print(f"  image ({x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f})")
        return

    # ---- 수동 클립 모드 ----
    if args.clip:
        pno, x0, y0, x1, y1 = [float(v) for v in args.clip.split(",")]
        page = doc[int(pno) - 1]
        rect = pymupdf.Rect(x0, y0, x1, y1) & page.rect
        name = args.name or f"manual-p{int(pno)}"
        path = figdir / f"{name}.png"
        page.get_pixmap(dpi=args.dpi, clip=rect).save(path)
        print(f"saved {path}  ({rect})")
        return

    # ---- 텍스트 ----
    text_md = [f"# {pdf.name}\n"]
    for i, page in enumerate(doc, 1):
        text_md.append(f"\n\n## Page {i}\n\n{page.get_text('text')}")
    (out / "text.md").write_text("".join(text_md), encoding="utf-8")

    # ---- 페이지 렌더 ----
    for i, page in enumerate(doc, 1):
        page.get_pixmap(dpi=args.page_dpi).save(pagedir / f"page-{i:03d}.png")

    # ---- 그림/표 ----
    manifest = [f"# {pdf.name} — 그림/표 목록\n", "좌표 단위: PDF pt (수동 클립 시 --clip page,x0,y0,x1,y1 로 사용)\n"]
    counts = {}
    seen = set()
    all_tables_md = []
    for pno, page in enumerate(doc, 1):
        blocks = [b for b in page.get_text("blocks") if len(b) > 6 and b[6] == 0]  # 텍스트 블록만
        blocks.sort(key=lambda b: (b[1], b[0]))
        widths = [b[2] - b[0] for b in blocks if len(block_text(b)) > 100]
        col_w = statistics.median(widths) if widths else page.rect.width * 0.45
        gfx = gfx_rects_of(page)
        sizes = [sp["size"] for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for sp in l.get("spans", []) if len(sp["text"]) > 20]
        headings = heading_line_rects(page, statistics.median(sizes) if sizes else 10)
        caption_idx = {i for i, b in enumerate(blocks) if CAPTION_RE.match(block_text(b)) and not is_body_block(b, col_w, gfx)}

        def cap_kind(i):
            k = CAPTION_RE.match(block_text(blocks[i])).group("kind").lower()
            return "fig" if k.startswith("fig") else ("table" if k == "table" else "alg")

        for idx, b in enumerate(blocks):
            t = block_text(b)
            m = CAPTION_RE.match(t)
            if not m:
                continue
            # 본문 중간의 "Figure 3 shows..." 같은 문장 참조 제외: 캡션 블록은 보통 문단이 아님
            if is_body_block(b, col_w, gfx) and not re.match(r"^\s*(Fig|Table|Algorithm)", t):
                continue
            first_line = t.split("\n")[0]
            if len(first_line) > 20 and not re.match(r"^\s*(Fig(ure)?|Table|Algorithm)\.?\s*\S+\s*[.:|\-–—]", first_line, re.I):
                continue
            kind = m.group("kind").lower()
            kind = "fig" if kind.startswith("fig") else ("table" if kind == "table" else "alg")
            num = m.group("num").upper()
            key = (kind, num)
            if key in seen:
                continue
            caption, cap_rect = merge_caption(blocks, idx, col_w)
            # 그림은 캡션 위, 표는 캡션 아래(없으면 반대쪽) 우선
            order = (-1, 1) if kind == "fig" else (1, -1)
            rect = None
            for d in order:
                others = [(pymupdf.Rect(blocks[i][:4]), cap_kind(i)) for i in caption_idx if i != idx]
                rect = region_for(page, cap_rect, blocks, gfx, col_w, d, caption_idx, idx, others, headings)
                if rect is not None:
                    break
            if rect is None:
                manifest.append(f"\n- **{kind}-{num}** (p.{pno}) 자동 클립 실패 — pages/page-{pno:03d}.png 보고 --clip 으로 수동 지정\n  캡션: {caption}")
                continue
            seen.add(key)
            counts[kind] = counts.get(kind, 0) + 1
            fname = f"{kind}-{num}.png"
            page.get_pixmap(dpi=args.dpi, clip=rect).save(figdir / fname)
            manifest.append(
                f"\n- **{kind}-{num}** (p.{pno}) → figures/{fname}  clip=({rect.x0:.0f},{rect.y0:.0f},{rect.x1:.0f},{rect.y1:.0f})\n  캡션: {caption}"
            )
        for md in table_markdown(page):
            all_tables_md.append(f"\n### p.{pno} 에서 find_tables 로 추출한 표\n\n{md}\n")

    if all_tables_md:
        manifest.append("\n\n# 표 텍스트 (find_tables) — 정확하지 않을 수 있으니 이미지와 대조할 것\n")
        manifest.extend(all_tables_md)
    (out / "manifest.md").write_text("\n".join(manifest), encoding="utf-8")
    make_contact_sheet(figdir, out / "contact_sheet.png")

    meta = {
        "file": str(pdf),
        "slug": slug,
        "title_guess": guess_title(doc),
        "pages": len(doc),
        "figures": counts.get("fig", 0),
        "tables": counts.get("table", 0),
        "algorithms": counts.get("alg", 0),
        "pdf_metadata": {k: v for k, v in doc.metadata.items() if v},
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\n-> {out}/  (text.md, manifest.md, figures/, pages/)")


if __name__ == "__main__":
    main()
