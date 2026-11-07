#!/usr/bin/env python3
"""
Gold-set labelling tool. A tiny local web page, no extra installs.

A person opens http://127.0.0.1:8000, reads the paper title + evidence
+ the rules guess, and clicks the real label. It saves to papers_full
(gold_label, in_gold_set=TRUE) so we can measure precision/recall.

Two people run it with a different --labeller name on the same DB to
make the agreement check.

Run:  python src/label_tool.py --labeller alice --n 100
Then open the printed address in a browser.
Binds to 127.0.0.1 only (never public).
"""
import argparse
import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "data", "papers.duckdb")
DB = os.path.abspath(DB)

LABELLER = "anon"
SAMPLE_N = 100


def ensure_gold_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS gold (
            paper_id TEXT, labeller TEXT, gold_label TEXT,
            m_reason TEXT, secondary TEXT, note TEXT, ts TEXT,
            PRIMARY KEY (paper_id, labeller)
        )""")


def pick_sample(con, n):
    """Stratified-ish sample: mostly U/D/C guesses (where use likely),
    plus some M, across years. These are what a gold set must check."""
    rows = con.execute(f"""
        SELECT paper_id FROM papers_full
        WHERE label IN ('U','D','C')
        ORDER BY year, paper_id
        LIMIT {int(n*0.6)}
    """).fetchall()
    rows += con.execute(f"""
        SELECT paper_id FROM papers_full
        WHERE label = 'M'
        ORDER BY random()
        LIMIT {int(n*0.4)}
    """).fetchall()
    return [r[0] for r in rows]


PAGE = """<!doctype html><html><head><meta charset=utf-8>
<title>AWS label tool</title><style>
body{{font-family:system-ui;max-width:760px;margin:24px auto;padding:0 16px;
background:#111;color:#eee}}
.card{{background:#1d1d1d;border:1px solid #333;border-radius:10px;padding:18px;margin:12px 0}}
.ev{{background:#262626;padding:10px;border-radius:6px;font-size:15px;line-height:1.5}}
.guess{{color:#f5a623}}
button{{font-size:16px;padding:10px 16px;margin:4px;border:0;border-radius:8px;
cursor:pointer;background:#2d6cdf;color:#fff}}
button.m{{background:#555}} a{{color:#6ab0ff}}
.bar{{height:8px;background:#333;border-radius:4px}}.bar>i{{display:block;height:8px;background:#2d6cdf;border-radius:4px}}
small{{opacity:.7}}
</style></head><body>
<h2>Gold-set labelling — labeller: {labeller}</h2>
<div class=bar><i style="width:{pct}%"></i></div>
<small>{done} of {total} done</small>
<div class=card>
<h3>{title}</h3>
<p><small>{year} · {source} · phrases: {phrases}</small></p>
<p>Link: <a href="{link}" target=_blank>{link}</a></p>
<div class=ev>{evidence}</div>
<p class=guess>Rules guess: <b>{guess}</b> {reason}</p>
<form method=post action=/save>
<input type=hidden name=paper_id value="{paper_id}">
<p><b>Did the authors USE AWS?</b></p>
<button name=label value=U>U — Used</button>
<button name=label value=D>D — Open data</button>
<button name=label value=C>C — Credits</button>
<button class=m name=label value=M>M — Does not count</button>
<p>If M, reason: <input name=m_reason placeholder="P R S K F E D X" size=6></p>
<p>Note (optional): <input name=note size=50></p>
</form>
<form method=post action=/skip>
<input type=hidden name=paper_id value="{paper_id}">
<button class=m name=skip value=1>Skip for now</button>
</form>
</div>
<p><small>Read the guide: docs/label_guide.md · This saves to the shared database.</small></p>
</body></html>"""

DONE_PAGE = """<!doctype html><html><body style="font-family:system-ui;
background:#111;color:#eee;text-align:center;padding:60px">
<h2>All done for labeller {labeller}.</h2>
<p>{done} papers labelled. You can close this tab.</p>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _con(self):
        c = duckdb.connect(DB)
        ensure_gold_table(c)
        return c

    def _next(self, con):
        sample = pick_sample(con, SAMPLE_N)
        done_ids = {r[0] for r in con.execute(
            "SELECT paper_id FROM gold WHERE labeller=?", [LABELLER]
        ).fetchall()}
        for pid in sample:
            if pid not in done_ids:
                return pid, len(done_ids), len(sample)
        return None, len(done_ids), len(sample)

    def do_GET(self):
        con = self._con()
        pid, done, total = self._next(con)
        if pid is None:
            html = DONE_PAGE.format(labeller=LABELLER, done=done)
            con.close()
            return self._send(html)
        p = con.execute("""
            SELECT title, year, source, link, label, m_reason, harvest_phrase
            FROM papers_full WHERE paper_id=?""", [pid]).fetchone()
        ev = con.execute(
            "SELECT string_agg(sentence, ' — ') FROM mentions WHERE paper_id=?",
            [pid]).fetchone()[0] or "(no evidence sentence)"
        con.close()
        html = PAGE.format(
            labeller=LABELLER, paper_id=pid,
            title=p[0] or "(no title)", year=p[1], source=p[2] or "?",
            link=p[3] or "#", evidence=ev, guess=p[4] or "?",
            reason=("/" + p[5]) if p[5] else "",
            phrases=p[6] or "", done=done, total=total,
            pct=int(100*done/max(total, 1)))
        self._send(html)

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length).decode()
        form = urllib.parse.parse_qs(body)
        pid = form.get("paper_id", [""])[0]
        con = self._con()
        if self.path == "/save":
            import datetime as dt
            con.execute("""
                INSERT OR REPLACE INTO gold
                VALUES (?,?,?,?,?,?,?)""", [
                pid, LABELLER,
                form.get("label", [""])[0],
                form.get("m_reason", [""])[0],
                form.get("secondary", [""])[0],
                form.get("note", [""])[0],
                dt.datetime.now().isoformat(timespec="seconds"),
            ])
        # skip just moves on
        con.close()
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def _send(self, html):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())


def main():
    global LABELLER, SAMPLE_N
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeller", default="anon")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    LABELLER = args.labeller
    SAMPLE_N = args.n
    srv = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Labeller: {LABELLER}  sample: {SAMPLE_N}")
    print(f"Open  http://127.0.0.1:{args.port}  in your browser.")
    print("Press Ctrl+C to stop.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
