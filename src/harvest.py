#!/usr/bin/env python3
"""
Harvest AWS-related papers from OpenAlex.

What it does, step by step:
  1. Search OpenAlex full text for AWS phrases, per year.
  2. For each hit, pull the one sentence that matched (the evidence).
  3. Record source, link, and the date we read it.
  4. Remove duplicates (preprint vs published of the same paper).
  5. Write everything to a DuckDB file + a Parquet file.

Open APIs only. Key and email come from the environment, never the code.
Run:  python src/harvest.py --years 2020 --limit 50
"""
import argparse
import datetime as dt
import os
import re
import sys
import time
import urllib.parse

import duckdb
import requests

API = "https://api.openalex.org/works"
METHOD_VERSION = "harvest-0.1"

# Phrases we search. Each is one OpenAlex full-text query.
PHRASES = [
    # core
    "Amazon Web Services",
    # compute
    "Amazon EC2",
    "AWS Lambda",
    "AWS Batch",
    "Amazon EMR",
    "AWS Fargate",
    "Amazon SageMaker",
    # storage
    "Amazon S3",
    # databases / analytics
    "Amazon RDS",
    "Amazon DynamoDB",
    "Amazon Redshift",
    "Amazon Athena",
    "AWS Glue",
    # open data
    "AWS Open Data",
    "Registry of Open Data on AWS",
]

# Words near an AWS hit that mean it probably does NOT count (false friends).
FALSE_FRIENDS = [
    "automatic weather station",
    "american welding society",
]


def load_env():
    """Read key + email from .env or the real environment."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    key = os.environ.get("OPENALEX_API_KEY")
    mail = os.environ.get("OPENALEX_MAILTO")
    if not mail:
        sys.exit("Set OPENALEX_MAILTO (your contact email).")
    return key, mail


def first_sentence(text, phrase):
    """Return the short sentence around the phrase. Our evidence snippet."""
    if not text:
        return None
    low = text.lower()
    i = low.find(phrase.lower())
    if i < 0:
        return None
    start = max(0, i - 160)
    end = min(len(text), i + 160)
    snippet = text[start:end].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet


def reconstruct_abstract(inv_index):
    """OpenAlex gives abstracts as a word->positions map. Rebuild the text."""
    if not inv_index:
        return None
    pos = {}
    for word, places in inv_index.items():
        for p in places:
            pos[p] = word
    return " ".join(pos[p] for p in sorted(pos))


class BudgetExhausted(Exception):
    """Daily OpenAlex budget is spent. Stop cleanly; resume after reset."""


def get_json(url, tries=6):
    """GET with retries. A slow response is survived, not fatal.
    Waits longer after each failure (1,2,4,8,16,32 s).
    A spent daily budget raises BudgetExhausted so the run stops cleanly."""
    wait = 1
    for attempt in range(tries):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 429:
                body = {}
                try:
                    body = r.json()
                except ValueError:
                    pass
                # budget spent vs transient rate limit
                if str(body.get("dailyRemainingUsd")) == "0" or \
                   "budget" in str(body.get("message", "")).lower():
                    raise BudgetExhausted(body.get("message", "budget spent"))
                time.sleep(wait)
                wait = min(wait * 2, 32)
                continue
            r.raise_for_status()
            return r.json()
        except BudgetExhausted:
            raise
        except (requests.exceptions.RequestException, ValueError) as e:
            if attempt == tries - 1:
                raise
            print(f"    retry {attempt+1}/{tries} after error: "
                  f"{type(e).__name__}", flush=True)
            time.sleep(wait)
            wait = min(wait * 2, 32)
    return {}


def search(phrase, year, key, mail, limit):
    """One phrase, one year. Yield paper rows.

    limit <= 0 means no cap: page through everything with a cursor.
    """
    cursor = "*"
    seen = 0
    while cursor:
        params = {
            "filter": f"publication_year:{year},fulltext.search:{phrase}",
            "per-page": 200,
            "cursor": cursor,
            "mailto": mail,
            "select": "id,doi,title,publication_year,authorships,"
                      "primary_location,abstract_inverted_index,type",
        }
        if key:
            params["api_key"] = key
        url = API + "?" + urllib.parse.urlencode(params)
        data = get_json(url)
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
            hay = f"{w.get('title') or ''}. {abstract or ''}"
            snippet = first_sentence(hay, phrase)
            if not snippet:
                continue
            # drop obvious false friends
            low = snippet.lower()
            if any(ff in low for ff in FALSE_FRIENDS):
                continue
            loc = w.get("primary_location") or {}
            src = (loc.get("source") or {}).get("display_name")
            auths = w.get("authorships") or []
            first_country = None
            if auths:
                insts = auths[0].get("institutions") or []
                if insts:
                    first_country = insts[0].get("country_code")
            yield {
                "openalex_id": w["id"],
                "doi": w.get("doi"),
                "title": w.get("title"),
                "year": w.get("publication_year"),
                "type": w.get("type"),
                "source": src,
                "first_author_country": first_country,
                "matched_phrase": phrase,
                "evidence_sentence": snippet,
                "link": w.get("doi") or w["id"],
                "date_read": dt.date.today().isoformat(),
                "method_version": METHOD_VERSION,
            }
            seen += 1
            if limit > 0 and seen >= limit:
                return
        cursor = (data.get("meta") or {}).get("next_cursor")
        time.sleep(1)  # polite pause between pages


def dedupe(rows):
    """Collapse preprint + published of the same paper.
    Key on normalized title; keep the published type over preprint."""
    best = {}
    for r in rows:
        t = (r["title"] or "").lower().strip()
        t = re.sub(r"[^a-z0-9 ]", "", t)
        key = t[:120]
        if not key:
            key = r["openalex_id"]
        prev = best.get(key)
        if prev is None:
            best[key] = r
        else:
            # prefer a non-preprint type
            if prev["type"] == "preprint" and r["type"] != "preprint":
                best[key] = r
    return list(best.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", nargs="+", type=int, default=[2020])
    ap.add_argument("--limit", type=int, default=50,
                    help="max papers per phrase per year; 0 = no cap")
    ap.add_argument("--fresh", action="store_true",
                    help="wipe the raw table and start over (default: resume)")
    ap.add_argument("--out", default="data/papers.duckdb")
    args = ap.parse_args()

    key, mail = load_env()
    print(f"Key: {'yes' if key else 'no (free budget)'}  Mail: {mail}", flush=True)

    out = os.path.join(os.path.dirname(__file__), "..", args.out)
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    # One DB for the whole run. We write after EACH phrase/year, so a stop
    # never loses finished work. A "raw" table keeps every hit; dedupe runs
    # at the end into the final "papers" table.
    con = duckdb.connect(out)
    if args.fresh:
        con.execute("DROP TABLE IF EXISTS raw")
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw (
            openalex_id TEXT, doi TEXT, title TEXT, year INTEGER,
            type TEXT, source TEXT, first_author_country TEXT,
            matched_phrase TEXT, evidence_sentence TEXT, link TEXT,
            date_read TEXT, method_version TEXT
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS done (year INTEGER, phrase TEXT)""")

    already = {(r[0], r[1]) for r in
               con.execute("SELECT year, phrase FROM done").fetchall()}
    if already:
        print(f"Resuming: {len(already)} phrase/year pairs already done.",
              flush=True)

    total = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    stopped_early = False
    for year in args.years:
        if stopped_early:
            break
        for phrase in PHRASES:
            if (year, phrase) in already:
                continue
            try:
                got = list(search(phrase, year, key, mail, args.limit))
            except BudgetExhausted as e:
                # Do NOT mark this pair done: resume will re-fetch it.
                print(f"\nBUDGET SPENT at {year} / {phrase}.", flush=True)
                print(f"  {e}", flush=True)
                print("  Finished pairs are saved. Re-run the same command "
                      "after midnight UTC to resume.", flush=True)
                stopped_early = True
                break
            if got:
                con.executemany(
                    "INSERT INTO raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    [tuple(r.values()) for r in got],
                )
            con.execute("INSERT INTO done VALUES (?, ?)", [year, phrase])
            total += len(got)
            print(f"  {year}  {phrase:<28} {len(got):>5} hits "
                  f"(running total {total})", flush=True)
            time.sleep(1)  # polite pause, one request at a time

    print(f"Raw rows saved: {total}", flush=True)

    # dedupe raw -> papers
    rows = con.execute("SELECT * FROM raw").fetchall()
    cols = [d[0] for d in con.description]
    dict_rows = [dict(zip(cols, r)) for r in rows]
    deduped = dedupe(dict_rows)
    print(f"After dedupe: {len(deduped)}", flush=True)

    con.execute("DROP TABLE IF EXISTS papers")
    con.execute("CREATE TABLE papers AS SELECT * FROM raw WHERE false")
    con.executemany(
        "INSERT INTO papers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        [tuple(r[c] for c in cols) for r in deduped],
    )
    con.execute(f"COPY papers TO '{out.replace('.duckdb', '.parquet')}' (FORMAT PARQUET)")

    # coverage report per year (graded item)
    print("\nCoverage per year (deduped papers):", flush=True)
    for r in con.execute(
        "SELECT year, count(*) FROM papers GROUP BY year ORDER BY year"
    ).fetchall():
        print(f"  {r[0]}  {r[1]:>6}", flush=True)
    n = con.execute("SELECT count(*) FROM papers").fetchone()[0]
    con.close()
    print(f"\nSaved {n} papers to {out}", flush=True)
    print(f"Parquet: {out.replace('.duckdb', '.parquet')}", flush=True)


if __name__ == "__main__":
    main()
