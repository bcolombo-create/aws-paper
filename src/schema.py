#!/usr/bin/env python3
"""
Create the full database schema.

Two tables:
  papers   — one row per paper (the data dictionary fields + extras)
  mentions — one row per AWS mention (sentence, section, link)

Run:  python src/schema.py
It is safe to run again; it only adds what is missing.
"""
import os
import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "data", "papers.duckdb")
DB = os.path.abspath(DB)


def main():
    con = duckdb.connect(DB)

    # --- papers: one row per paper -------------------------------------
    con.execute("""
    CREATE TABLE IF NOT EXISTS papers_full (
        -- identity
        paper_id            TEXT PRIMARY KEY,   -- our stable id
        openalex_id         TEXT,
        doi                 TEXT,
        arxiv_id            TEXT,
        title               TEXT,
        -- when / where
        year                INTEGER,
        publication_date    TEXT,
        venue               TEXT,               -- journal or conf name
        source              TEXT,               -- OpenAlex source
        type                TEXT,               -- article, preprint...
        -- authors / place
        first_author        TEXT,
        first_author_country TEXT,
        n_authors           INTEGER,
        affiliations        TEXT,
        -- subject
        field               TEXT,               -- top concept
        subfield            TEXT,
        concepts            TEXT,               -- list, joined
        -- the AWS judgement
        label               TEXT,               -- U / D / C / M / NULL
        m_reason            TEXT,               -- P R S K F E D X
        aws_services        TEXT,               -- EC2, S3... joined
        secondary_signal    TEXT,               -- generic_cloud/hpc/...
        -- how we decided
        classified_by       TEXT,               -- rules / ai / human
        confidence          DOUBLE,
        in_gold_set         BOOLEAN DEFAULT FALSE,
        gold_label          TEXT,               -- human truth, if in gold
        -- text we had
        has_abstract        BOOLEAN,
        has_fulltext        BOOLEAN,
        text_source         TEXT,               -- abstract / arxiv / none
        -- provenance (your required extras)
        link                TEXT,
        date_read           TEXT,
        method_version      TEXT,
        harvest_phrase      TEXT,
        -- dedupe
        is_duplicate        BOOLEAN DEFAULT FALSE,
        duplicate_of        TEXT,
        -- free note
        note                TEXT
    )""")

    # --- mentions: one row per AWS mention -----------------------------
    con.execute("""
    CREATE TABLE IF NOT EXISTS mentions (
        mention_id      TEXT PRIMARY KEY,
        paper_id        TEXT,          -- links to papers_full.paper_id
        matched_phrase  TEXT,          -- e.g. "Amazon EC2"
        sentence        TEXT,          -- the evidence sentence
        section         TEXT,          -- title / abstract / methods...
        link            TEXT,          -- where to read it
        date_read       TEXT,
        counts_as_use   BOOLEAN        -- did a human/AI judge this one real
    )""")

    # helpful indexes
    con.execute("CREATE INDEX IF NOT EXISTS idx_mentions_paper "
                "ON mentions(paper_id)")

    print("Schema ready in", DB)
    for t in ("papers_full", "mentions"):
        n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n} rows")
    con.close()


if __name__ == "__main__":
    main()
