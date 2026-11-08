#!/usr/bin/env python3
"""
Build the web tool: one self-contained index.html with the data baked in.

Reads papers_full + mentions, writes site/index.html. No server needed.
Host it free on GitHub Pages (Settings -> Pages -> branch /site) or just
open the file in a browser. Reads whatever years are present, so adding
2023-2026 later just makes the tool show more years.

Run:  python src/build_tool.py
"""
import json
import os
import datetime as dt
import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = os.path.join(ROOT, "data", "papers.duckdb")
OUT_DIR = os.path.join(ROOT, "site")
OUT = os.path.join(OUT_DIR, "index.html")

LABEL_NAME = {"U": "Used AWS", "D": "Used open data",
              "C": "Credits/support", "M": "Does not count"}


def main():
    con = duckdb.connect(DB)
    papers = con.execute("""
        SELECT paper_id, title, year, source, first_author_country,
               label, m_reason, aws_services, link, date_read,
               classified_by, secondary_signal
        FROM papers_full
    """).fetchall()
    pcols = [d[0] for d in con.description]

    mentions = con.execute("""
        SELECT paper_id, matched_phrase, sentence, section, link, date_read
        FROM mentions
    """).fetchall()

    # one evidence list per paper
    ev = {}
    for m in mentions:
        ev.setdefault(m[0], []).append({
            "phrase": m[1], "sentence": m[2], "section": m[3],
            "link": m[4], "date_read": m[5],
        })

    data = []
    for row in papers:
        d = dict(zip(pcols, row))
        d["evidence"] = ev.get(d["paper_id"], [])
        data.append(d)

    years = sorted({d["year"] for d in data if d["year"]})
    method_version = "harvest-0.1"
    built = dt.date.today().isoformat()

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False)

    html = TEMPLATE.replace("__DATA__", payload) \
                   .replace("__YEARS__", json.dumps(years)) \
                   .replace("__BUILT__", built) \
                   .replace("__METHOD__", method_version) \
                   .replace("__NPAPERS__", str(len(data)))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    con.close()
    print(f"Built {OUT}")
    print(f"  {len(data)} papers, years {years[0]}-{years[-1]}")
    print(f"  open it in a browser, or host site/ on GitHub Pages")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AWS-in-Science — did the authors USE AWS?</title>
<style>
  :root{--bg:#0f1115;--card:#1a1d24;--line:#2a2f3a;--text:#e8eaed;
        --muted:#9aa0aa;--blue:#4a90d9;--amber:#f5a623;--green:#3fb568}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
       font-family:system-ui,-apple-system,sans-serif;line-height:1.5}
  header{padding:20px;border-bottom:1px solid var(--line)}
  h1{margin:0 0 4px;font-size:22px}
  .sub{color:var(--muted);font-size:14px}
  .wrap{max-width:1100px;margin:0 auto;padding:16px}
  .cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
  .stat{background:var(--card);border:1px solid var(--line);border-radius:10px;
        padding:14px 18px;min-width:130px}
  .stat b{font-size:26px;display:block}
  .stat span{color:var(--muted);font-size:13px}
  .filters{display:flex;gap:10px;flex-wrap:wrap;background:var(--card);
           border:1px solid var(--line);border-radius:10px;padding:14px;margin:12px 0}
  .filters label{font-size:13px;color:var(--muted);display:block;margin-bottom:4px}
  select,input{background:var(--bg);color:var(--text);border:1px solid var(--line);
               border-radius:7px;padding:7px 9px;font-size:14px}
  .bars{background:var(--card);border:1px solid var(--line);border-radius:10px;
        padding:14px;margin:12px 0}
  .barrow{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:13px}
  .barrow .y{width:46px;color:var(--muted)}
  .barrow .bar{height:14px;background:var(--blue);border-radius:3px}
  .barrow .n{color:var(--muted)}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);
        vertical-align:top}
  th{color:var(--muted);font-weight:600;cursor:pointer}
  .tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:12px;
       font-weight:600}
  .tag.U{background:rgba(63,181,104,.2);color:#6fe09a}
  .tag.D{background:rgba(74,144,217,.2);color:#8ec2f5}
  .tag.C{background:rgba(245,166,35,.2);color:#f7bf63}
  .tag.M{background:rgba(154,160,170,.15);color:var(--muted)}
  .ev{background:var(--bg);border:1px solid var(--line);border-radius:8px;
      padding:10px;margin:6px 0;font-size:13px}
  .ev .s{color:var(--text)}
  .ev .meta{color:var(--muted);font-size:12px;margin-top:4px}
  a{color:#6ab0ff}
  details summary{cursor:pointer;color:var(--blue)}
  .note{color:var(--muted);font-size:13px;margin:10px 0}
  .pager{display:flex;gap:8px;align-items:center;margin:12px 0}
  button{background:var(--blue);color:#fff;border:0;border-radius:7px;
         padding:7px 12px;cursor:pointer;font-size:14px}
  button:disabled{opacity:.4;cursor:default}
</style></head>
<body>
<header><div class="wrap">
  <h1>AWS-in-Science — did the authors actually <em>use</em> AWS?</h1>
  <div class="sub">Scientific papers 2016-2022 · every claim links to an
  evidence sentence, a link, and the date it was read.</div>
</div></header>

<div class="wrap">
  <div class="note">
    <b>How to read this:</b> most papers only <em>mention</em> AWS. We separate
    real <b>use</b> (labels U/D/C) from mention (M). Labels below are a
    rules-based first pass (<code>classified_by</code> shows how each was decided);
    a human gold set and precision/recall come next. Scope: 2016-2022,
    title + abstract text. Built __BUILT__ · method __METHOD__.
  </div>

  <div class="cards" id="cards"></div>

  <div class="bars" id="yearbars"></div>

  <div class="filters">
    <div><label>Year</label><select id="fYear"><option value="">All</option></select></div>
    <div><label>Verdict</label><select id="fLabel">
      <option value="">All</option>
      <option value="U">U — Used AWS</option>
      <option value="D">D — Open data</option>
      <option value="C">C — Credits</option>
      <option value="use">Any use (U/D/C)</option>
      <option value="M">M — Does not count</option>
    </select></div>
    <div><label>Country (first author)</label><select id="fCountry"><option value="">All</option></select></div>
    <div><label>Service</label><select id="fService"><option value="">All</option></select></div>
    <div><label>Search title</label><input id="fText" placeholder="type to filter"></div>
  </div>

  <div class="note" id="count"></div>

  <table><thead><tr>
    <th data-k="title">Title</th><th data-k="year">Year</th>
    <th data-k="label">Verdict</th><th data-k="first_author_country">Country</th>
    <th>Evidence</th>
  </tr></thead><tbody id="rows"></tbody></table>

  <div class="pager">
    <button id="prev">Prev</button>
    <span id="pageinfo" class="note"></span>
    <button id="next">Next</button>
  </div>
</div>

<script>
const DATA = __DATA__;
const YEARS = __YEARS__;
const LABELNAME = {U:"Used AWS",D:"Used open data",C:"Credits/support",M:"Does not count"};
const PAGE = 25;
let page = 0, sortK = "year", sortDir = 1, view = DATA;

function unique(key){
  const s = new Set();
  DATA.forEach(d => { if(d[key]) s.add(d[key]); });
  return [...s].sort();
}
function services(){
  const s = new Set();
  DATA.forEach(d => (d.aws_services||"").split(", ").forEach(x => x && s.add(x)));
  return [...s].sort();
}
function fill(id, items){
  const el = document.getElementById(id);
  items.forEach(v => { const o=document.createElement("option");
    o.value=v;o.textContent=v;el.appendChild(o); });
}
fill("fYear", YEARS); fill("fCountry", unique("first_author_country"));
fill("fService", services());

function cards(){
  const n = DATA.length;
  const use = DATA.filter(d=>["U","D","C"].includes(d.label)).length;
  const u = DATA.filter(d=>d.label==="U").length;
  const countries = unique("first_author_country").length;
  const html = [
    ["Papers", n], ["Confirmed use (U/D/C)", use],
    ["Used AWS (U)", u], ["Countries", countries],
    ["Years", YEARS.length ? YEARS[0]+"–"+YEARS[YEARS.length-1] : "-"]
  ].map(([k,v])=>`<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
  document.getElementById("cards").innerHTML = html;
}
function yearbars(){
  const byYear = {};
  DATA.filter(d=>["U","D","C"].includes(d.label))
      .forEach(d=>byYear[d.year]=(byYear[d.year]||0)+1);
  const max = Math.max(1,...Object.values(byYear));
  const rows = YEARS.map(y=>{
    const n = byYear[y]||0;
    return `<div class="barrow"><span class="y">${y}</span>
      <span class="bar" style="width:${300*n/max}px"></span>
      <span class="n">${n}</span></div>`;
  }).join("");
  document.getElementById("yearbars").innerHTML =
    "<b>Confirmed AWS use per year</b>"+rows;
}

function apply(){
  const y=fYear.value, l=fLabel.value, c=fCountry.value,
        s=fService.value, t=fText.value.toLowerCase();
  view = DATA.filter(d=>{
    if(y && String(d.year)!==y) return false;
    if(l==="use" && !["U","D","C"].includes(d.label)) return false;
    else if(l && l!=="use" && d.label!==l) return false;
    if(c && d.first_author_country!==c) return false;
    if(s && !(d.aws_services||"").includes(s)) return false;
    if(t && !((d.title||"").toLowerCase().includes(t))) return false;
    return true;
  });
  page=0; render();
}
function render(){
  view.sort((a,b)=>{
    let x=a[sortK], y=b[sortK];
    if(x==null)x=""; if(y==null)y="";
    return (x>y?1:x<y?-1:0)*sortDir;
  });
  const start=page*PAGE, slice=view.slice(start,start+PAGE);
  document.getElementById("count").textContent =
    view.length+" papers match.";
  document.getElementById("rows").innerHTML = slice.map(d=>{
    const ev = (d.evidence||[]).map(e=>`<div class="ev">
      <div class="s">“${(e.sentence||"").replace(/</g,"&lt;")}”</div>
      <div class="meta">${e.phrase} · ${e.section} ·
      <a href="${e.link}" target="_blank">link</a> · read ${e.date_read}</div>
    </div>`).join("");
    return `<tr>
      <td>${(d.title||"(no title)").replace(/</g,"&lt;")}</td>
      <td>${d.year||""}</td>
      <td><span class="tag ${d.label}">${d.label}</span>
          ${d.m_reason?("/"+d.m_reason):""}</td>
      <td>${d.first_author_country||"—"}</td>
      <td><details><summary>${(d.evidence||[]).length} evidence</summary>
          ${ev||"(none)"}</details></td>
    </tr>`;
  }).join("");
  const pages=Math.max(1,Math.ceil(view.length/PAGE));
  document.getElementById("pageinfo").textContent=`page ${page+1} of ${pages}`;
  document.getElementById("prev").disabled = page<=0;
  document.getElementById("next").disabled = page>=pages-1;
}
["fYear","fLabel","fCountry","fService"].forEach(id=>
  document.getElementById(id).addEventListener("change",apply));
document.getElementById("fText").addEventListener("input",apply);
document.getElementById("prev").onclick=()=>{if(page>0){page--;render();}};
document.getElementById("next").onclick=()=>{page++;render();};
document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{
  const k=th.dataset.k;
  if(sortK===k)sortDir*=-1; else{sortK=k;sortDir=1;}
  render();
});
cards(); yearbars(); apply();
</script>
</body></html>"""


if __name__ == "__main__":
    main()
