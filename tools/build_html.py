#!/usr/bin/env python3
"""
work/<slug>/summary.html 에 있는 로컬 이미지(figures/xxx.png)를 base64 로 인라인해서
docs/<slug>.html 하나짜리 파일로 만들고, docs/index.html 목록을 다시 생성.
(docs/ 인 이유: GitHub Pages 가 서빙할 수 있는 폴더가 저장소 루트 아니면 /docs 뿐이라서.)

사용법:
  python3 tools/build_html.py <slug>        # work/<slug>/summary.html -> docs/<slug>.html
  python3 tools/build_html.py --index       # index.html 만 다시 생성
"""
import base64, html, io, re, sys, json, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK, OUT = ROOT / "work", ROOT / "docs"
MAX_W = 1600          # 이보다 넓은 이미지는 축소
JPEG_OVER = 350_000   # 이보다 큰 PNG 는 JPEG 로 (사진 위주 그림)


def encode_image(path: Path) -> str:
    import pymupdf
    pix = pymupdf.Pixmap(str(path))
    if pix.width > MAX_W:
        # 축소
        scale = MAX_W / pix.width
        doc = pymupdf.open()
        page = doc.new_page(width=pix.width * scale, height=pix.height * scale)
        page.insert_image(page.rect, pixmap=pix)
        pix = page.get_pixmap(dpi=72)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    png = pix.tobytes("png")
    if len(png) > JPEG_OVER:
        data, mime = pix.tobytes("jpeg", jpg_quality=85), "image/jpeg"
    else:
        data, mime = png, "image/png"
    return f"data:{mime};base64," + base64.b64encode(data).decode()


def inline_images(src_html: str, base: Path):
    missing = []

    def repl(m):
        attr, quote, src = m.group(1), m.group(2), m.group(3)
        if src.startswith(("data:", "http://", "https://")):
            return m.group(0)
        p = (base / src).resolve()
        if not p.exists():
            missing.append(src)
            return m.group(0)
        return f'{attr}={quote}{encode_image(p)}{quote}'

    out = re.sub(r'(src)=(["\'])([^"\']+)\2', repl, src_html)
    return out, missing


MATH_RE = re.compile(r"\$\$.*?\$\$|(?<![\\$])\$[^$\n]+?\$", re.S)


def escape_math(text: str) -> str:
    """$...$ / $$...$$ 안의 날것 < > 를 &lt; &gt; 로 (브라우저가 태그로 오해하는 것 방지. KaTeX 는 textContent 를 읽으므로 OK)."""
    return MATH_RE.sub(lambda m: m.group(0).replace("<", "&lt;").replace(">", "&gt;"), text)


def meta_of(html_text: str):
    def m(name):
        r = re.search(rf'<meta\s+name=["\']{re.escape(name)}["\']\s+content=["\']([^"\']*)["\']', html_text, re.I)
        return html.unescape(r.group(1)) if r else ""
    t = re.search(r"<title>(.*?)</title>", html_text, re.S | re.I)
    return {
        "title": html.unescape(t.group(1).strip()) if t else "",
        "original": m("paper:original-title"),
        "venue": m("paper:venue"),
        "year": m("paper:year"),
        "tags": [x.strip() for x in m("paper:tags").split(",") if x.strip()],
        "desc": m("description"),
        "date": m("paper:summarized"),
        "category": m("paper:category"),
    }


# 분야 자동 분류. summary.html 에 <meta name="paper:category"> 가 있으면 그걸 우선 쓰고,
# 없으면 태그에서 아래 키워드로 추론한다. 위에 있는 규칙이 먼저 걸린다.
# 위에서부터 순서대로 검사해 처음 걸리는 규칙을 쓴다. 좁은 규칙을 위에 둘 것
# (예: 압축 논문도 "3D Gaussian Splatting" 태그를 갖고 있으므로, 넓은 "장면 표현·재구성"은 맨 아래).
CATEGORY_RULES = [
    # "6-DoF 추적"처럼 '포즈'가 빠진 표기도 잡도록 6dof/6-dof 자체를 키워드에 둔다.
    ("6-DoF 포즈 추적", ("6dof", "6-dof", "6d pose", "pose tracking", "포즈 추적", "물체 추적")),
    ("3DGS 압축·경량화", ("압축", "경량화", "memory reduction", "양자화", "quantization", "pruning", "가지치기")),
    ("생성 3D prior·형상 완성", ("image-to-3d", "shape completion", "diffusion prior", "3d generation",
                                  "생성", "generation", "score distillation", "sds", "completion")),
    ("장면 표현·재구성", ("표면 재구성", "surface reconstruction", "재구성", "reconstruction",
                          "래디언스", "radiance field", "메싱", "mesh", "sdf")),
    # 이 저장소의 주 관심사(포즈 추적·3DGS)와 별개 계열. 음성·텍스트 언어모델 논문용.
    ("음성·언어 모델", ("speech", "음성", "asr", "tts", "언어모델", "llm", "hubert")),
]


def categorize(info) -> str:
    if info["category"]:
        return info["category"]
    blob = " ".join(info["tags"]).lower()
    for name, keys in CATEGORY_RULES:
        if any(k in blob for k in keys):
            return name
    return "기타"


INDEX_CSS = """
:root{--bg:#f7f7f5;--card:#fff;--fg:#1f2328;--muted:#656d76;--line:#e5e7eb;--accent:#2563eb;
      --accent-soft:#eaf0ff;--tagbg:#eef2ff;--tagfg:#3730a3;--field:#fff;--shadow:rgba(0,0,0,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--fg:#e6e8ec;--muted:#9aa3ad;--line:#262b33;
      --accent:#7aa2ff;--accent-soft:#1a2240;--tagbg:#1e2340;--tagfg:#b4c0ff;--field:#12151b;--shadow:rgba(0,0,0,.5)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);line-height:1.55;
     font-family:"Pretendard","Apple SD Gothic Neo","Noto Sans KR",system-ui,-apple-system,sans-serif;word-break:keep-all}
main{max-width:1060px;margin:0 auto;padding:44px 20px 90px}
header.site h1{font-size:1.8rem;margin:0 0 6px}
header.site .sub{color:var(--muted);font-size:.92rem;margin:0 0 26px}

.controls{margin-bottom:22px}
#q{width:100%;padding:11px 14px;font-size:.95rem;font-family:inherit;color:var(--fg);
   background:var(--field);border:1px solid var(--line);border-radius:10px;outline:none}
#q:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
#q::placeholder{color:var(--muted)}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin-top:12px}
.cats{display:flex;flex-wrap:wrap;gap:6px}
.chip{font:inherit;font-size:.83rem;cursor:pointer;padding:5px 12px;border-radius:999px;
      background:transparent;color:var(--muted);border:1px solid var(--line)}
.chip:hover{border-color:var(--accent);color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
.chip .n{opacity:.65;font-size:.78em;margin-left:3px}
.sortwrap{font-size:.83rem;color:var(--muted);display:flex;align-items:center;gap:6px;white-space:nowrap}
#sort{font:inherit;font-size:.83rem;color:var(--fg);background:var(--field);
      border:1px solid var(--line);border-radius:8px;padding:5px 8px;cursor:pointer}
.activetags{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:12px;font-size:.83rem;color:var(--muted)}
.activetags .sel{background:var(--accent);color:#fff;border-radius:999px;padding:3px 10px;cursor:pointer;border:none;font:inherit;font-size:.78rem}
.activetags .sel::after{content:" ×";opacity:.8}
.activetags .clear{background:none;border:none;color:var(--accent);cursor:pointer;font:inherit;font-size:.8rem;text-decoration:underline}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-top:20px}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);
      border-radius:12px;padding:18px;transition:transform .12s,box-shadow .12s,border-color .12s}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 20px var(--shadow);border-color:var(--accent)}
.card-main{display:block;color:inherit;text-decoration:none;flex:1}
.card-title{font-weight:700;font-size:1.05rem;margin-bottom:4px}
.card-orig{font-size:.85rem;color:var(--muted);font-style:italic}
.card-meta{font-size:.8rem;color:var(--muted);margin:6px 0 8px}
.card-desc{font-size:.9rem;margin:0 0 12px}
.tags{display:flex;flex-wrap:wrap;gap:4px}
.tag{font:inherit;font-size:.72rem;background:var(--tagbg);color:var(--tagfg);border:1px solid transparent;
     border-radius:999px;padding:2px 9px;cursor:pointer}
.tag:hover{border-color:var(--accent)}
.tag.on{background:var(--accent);color:#fff}
.empty{text-align:center;color:var(--muted);padding:50px 0;font-size:.95rem}
footer.site{margin-top:50px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:.82rem}
@media (max-width:560px){main{padding:28px 16px 60px}.row{align-items:flex-start}}
"""

INDEX_JS = """
(function(){
  var grid=document.getElementById('grid'), q=document.getElementById('q'),
      sort=document.getElementById('sort'), empty=document.getElementById('empty'),
      box=document.getElementById('activetags'), cards=[].slice.call(grid.children),
      cat='', tags=[];

  function norm(s){return (s||'').toLowerCase();}

  function apply(){
    var terms=norm(q.value).split(/\\s+/).filter(Boolean), shown=0;
    cards.forEach(function(c){
      var ok = (!cat || c.dataset.cat===cat)
        && tags.every(function(t){return c.dataset.tags.split('|').indexOf(t)>=0;})
        && terms.every(function(t){return c.dataset.search.indexOf(t)>=0;});
      c.hidden=!ok; if(ok) shown++;
    });
    empty.hidden = shown>0;
    grid.querySelectorAll('.tag').forEach(function(b){
      b.classList.toggle('on', tags.indexOf(b.dataset.tag)>=0);
    });
    box.hidden = tags.length===0;
    box.innerHTML='';
    if(tags.length){
      box.appendChild(document.createTextNode('태그 '));
      tags.forEach(function(t){
        var b=document.createElement('button'); b.className='sel'; b.textContent=t;
        b.onclick=function(){tags=tags.filter(function(x){return x!==t;});apply();};
        box.appendChild(b);
      });
      var c=document.createElement('button'); c.className='clear'; c.textContent='전체 해제';
      c.onclick=function(){tags=[];apply();}; box.appendChild(c);
    }
  }

  function resort(){
    var k=sort.value;
    cards.slice().sort(function(a,b){
      if(k==='title') return a.dataset.title.localeCompare(b.dataset.title,'ko');
      if(k==='year')  return (b.dataset.year||'').localeCompare(a.dataset.year||'')
                          || a.dataset.title.localeCompare(b.dataset.title,'ko');
      return (b.dataset.date||'').localeCompare(a.dataset.date||'')
          || a.dataset.title.localeCompare(b.dataset.title,'ko');
    }).forEach(function(c){grid.appendChild(c);});
  }

  q.addEventListener('input', apply);
  sort.addEventListener('change', resort);
  document.getElementById('cats').addEventListener('click', function(e){
    var b=e.target.closest('.chip'); if(!b) return;
    cat=b.dataset.cat;
    [].forEach.call(this.querySelectorAll('.chip'),function(x){x.classList.toggle('on',x===b);});
    apply();
  });
  grid.addEventListener('click', function(e){
    var b=e.target.closest('.tag'); if(!b) return;
    var t=b.dataset.tag, i=tags.indexOf(t);
    if(i>=0) tags.splice(i,1); else tags.push(t);
    apply();
  });
  apply();
})();
"""


def build_index():
    cards = []
    for f in sorted(OUT.glob("*.html")):
        if f.name == "index.html":
            continue
        info = meta_of(f.read_text(encoding="utf-8", errors="ignore")[:8000])
        info["file"] = f.name
        info["size_mb"] = f.stat().st_size / 1e6
        info["cat"] = categorize(info)
        cards.append(info)
    cards.sort(key=lambda c: (c["date"] or "", c["title"]), reverse=True)

    # 분야 목록 (등장 순서 유지, 개수 표시)
    cats = []
    for c in cards:
        if c["cat"] not in cats:
            cats.append(c["cat"])
    cat_counts = {name: sum(1 for c in cards if c["cat"] == name) for name in cats}

    def esc(s):
        return html.escape(s or "", quote=True)

    items = []
    for c in cards:
        tags = "".join(
            f'<button class="tag" data-tag="{esc(t)}">{esc(t)}</button>' for t in c["tags"]
        )
        vy = " · ".join(x for x in [c["venue"], c["year"]] if x)
        meta_line = vy + (" · 정리 " + c["date"] if c["date"] else "")
        search_blob = " ".join(
            [c["title"], c["original"], c["desc"], c["venue"], c["year"], c["cat"]] + c["tags"]
        ).lower()
        items.append(f'''
    <article class="card" data-cat="{esc(c["cat"])}" data-tags="{esc("|".join(c["tags"]))}"
             data-title="{esc(c["title"] or c["file"])}" data-year="{esc(c["year"])}"
             data-date="{esc(c["date"])}" data-search="{esc(search_blob)}">
      <a class="card-main" href="{esc(c["file"])}">
        <div class="card-title">{esc(c["title"] or c["file"])}</div>
        <div class="card-orig">{esc(c["original"])}</div>
        <div class="card-meta">{esc(meta_line)}</div>
        <p class="card-desc">{esc(c["desc"])}</p>
      </a>
      <div class="tags">{tags}</div>
    </article>''')

    chips = [f'<button class="chip on" data-cat="">전체 <span class="n">{len(cards)}</span></button>']
    chips += [
        f'<button class="chip" data-cat="{esc(n)}">{esc(n)} <span class="n">{cat_counts[n]}</span></button>'
        for n in cats
    ]

    updated = max((c["date"] for c in cards if c["date"]), default="")
    sub = f'{len(cards)}편' + (f' · 마지막 업데이트 {updated}' if updated else '')

    page = f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>논문 정리</title>
<meta name="description" content="읽은 논문을 한국어로 정리해 모아둔 곳. {len(cards)}편.">
<style>{INDEX_CSS}</style></head>
<body><main>

<header class="site">
  <h1>📚 논문 정리</h1>
  <p class="sub">읽은 논문을 한국어로 정리해 모아둔 곳 · {sub}</p>
</header>

<div class="controls">
  <input id="q" type="search" placeholder="제목 · 원제 · 태그 · 요약에서 검색" autocomplete="off" spellcheck="false">
  <div class="row">
    <div class="cats" id="cats">{"".join(chips)}</div>
    <label class="sortwrap">정렬
      <select id="sort">
        <option value="date">정리 최신순</option>
        <option value="year">논문 연도순</option>
        <option value="title">제목순</option>
      </select>
    </label>
  </div>
  <div class="activetags" id="activetags" hidden></div>
</div>

<div class="grid" id="grid">{"".join(items)}
</div>
<p class="empty" id="empty" hidden>조건에 맞는 논문이 없어요.</p>

<footer class="site">
  papers/ 폴더에 PDF를 넣고 "논문 정리해줘" 라고 하면 여기에 추가돼요.
</footer>

</main>
<script>{INDEX_JS}</script>
</body></html>'''
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"index.html: {len(cards)}편 ({', '.join(f'{n} {cat_counts[n]}' for n in cats)})")


def main():
    OUT.mkdir(exist_ok=True)
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    if sys.argv[1] == "--index":
        build_index(); return
    slug = sys.argv[1]
    src = WORK / slug / "summary.html"
    if not src.exists():
        sys.exit(f"없음: {src}")
    text = src.read_text(encoding="utf-8")
    if 'name="paper:summarized"' not in text:
        text = text.replace("</title>", f'</title>\n<meta name="paper:summarized" content="{datetime.date.today().isoformat()}">', 1)
    text = escape_math(text)
    out_html, missing = inline_images(text, src.parent)
    dst = OUT / f"{slug}.html"
    dst.write_text(out_html, encoding="utf-8")
    n_img = out_html.count("data:image/")
    print(f"-> {dst}  ({dst.stat().st_size/1e6:.1f} MB, 이미지 {n_img}개 인라인)")
    if missing:
        print("!! 찾지 못한 이미지:", *missing, sep="\n   ")
    build_index()


if __name__ == "__main__":
    main()
