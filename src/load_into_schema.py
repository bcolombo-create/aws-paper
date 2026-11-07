#!/usr/bin/env python3
"""
Move harvested rows (raw table) into the clean schema:
  - one row per paper in papers_full
  - one row per mention in mentions

Dedupe: if the same paper matched several phrases, it is ONE paper row
but SEVERAL mention rows. Preprint+published of the same title collapse
to one paper (published kept), both mentions kept.

Run:  python src/load_into_schema.py
"""
import os
import re
import hashlib
import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "data", "papers.duckdb")
DB = os.path.abspath(DB)


def norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"[^a-z0-9 ]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:120]


def pid(openalex_id):
    return hashlib.sha1((openalex_id or "").encode()).hexdigest()[:16]


def section_of(sentence, title):
    """Cheap guess at where the mention sits."""
    if title and sentence and sentence.lower().startswith(title.lower()[:30]):
        return "title"
    return "abstract"


def main():
    con = duckdb.connect(DB)
    raw = con.execute("SELECT * FROM raw").fetchall()
    cols = [d[0] for d in con.description]
    rows = [dict(zip(cols, r)) for r in raw]
    print(f"raw rows: {len(rows)}")

    # group by normalized title to dedupe papers
    by_title = {}
    for r in rows:
        key = norm_title(r["title"]) or r["openalex_id"]
        by_title.setdefault(key, []).append(r)

    con.execute("DELETE FROM papers_full")
    con.execute("DELETE FROM mentions")

    n_papers = 0
    n_mentions = 0
    for key, group in by_title.items():
        # pick the canonical paper: prefer non-preprint
        canon = sorted(group, key=lambda x: x["type"] == "preprint")[0]
        pid_val = pid(canon["openalex_id"])
        phrases = sorted({g["matched_phrase"] for g in group})

        con.execute("""
            INSERT INTO papers_full
                (paper_id, openalex_id, doi, title, year, source, type,
                 first_author_country, aws_services, link, date_read,
                 method_version, harvest_phrase, has_abstract,
                 text_source, is_duplicate)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, [
            pid_val, canon["openalex_id"], canon["doi"], canon["title"],
            canon["year"], canon["source"], canon["type"],
            canon["first_author_country"], ", ".join(phrases),
            canon["link"], canon["date_read"], canon["method_version"],
            ", ".join(phrases), True, "abstract", False,
        ])
        n_papers += 1

        # one mention row per (paper, phrase) with its own sentence
        seen_ph = set()
        for g in group:
            ph = g["matched_phrase"]
            if ph in seen_ph:
                continue
            seen_ph.add(ph)
            mid = hashlib.sha1(
                f"{pid_val}:{ph}".encode()).hexdigest()[:16]
            con.execute("""
                INSERT INTO mentions
                    (mention_id, paper_id, matched_phrase, sentence,
                     section, link, date_read, counts_as_use)
                VALUES (?,?,?,?,?,?,?,?)
            """, [
                mid, pid_val, ph, g["evidence_sentence"],
                section_of(g["evidence_sentence"], g["title"]),
                g["link"], g["date_read"], None,
            ])
            n_mentions += 1

    con.execute(f"COPY papers_full TO "
                f"'{DB.replace('.duckdb', '_papers.parquet')}' (FORMAT PARQUET)")
    con.execute(f"COPY mentions TO "
                f"'{DB.replace('.duckdb', '_mentions.parquet')}' (FORMAT PARQUET)")
    print(f"papers_full: {n_papers}")
    print(f"mentions: {n_mentions}")
    con.close()


if __name__ == "__main__":
    main()
