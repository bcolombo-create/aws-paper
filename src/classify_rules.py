#!/usr/bin/env python3
"""
First-pass label by simple rules, no AI, no API.

This is a STARTING GUESS for the human labeller, not the truth.
It writes label + confidence + classified_by='rules' to papers_full.
The human gold set overrides it later.

Logic, in plain terms:
  - strong use words near a service  -> U (used)
  - open-data words                  -> D
  - credit / support words           -> C
  - future-work / list-only / false  -> M with a reason
  - nothing clear                    -> M/X (cannot tell)

Run:  python src/classify_rules.py
"""
import os
import re
import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "data", "papers.duckdb")
DB = os.path.abspath(DB)

USE_WORDS = [
    "we use", "we used", "we ran", "we deployed", "we trained",
    "deployed on", "hosted on", "ran on", "running on", "stored in",
    "stored on", "implemented on", "using amazon", "using aws",
    "on amazon ec2", "on an ec2", "s3 bucket", "experiments were run",
    "we performed", "our experiments", "we leverage", "instance on aws",
]
OPEN_DATA = [
    "open data", "registry of open data", "aws open data",
    "public dataset on aws", "available on aws",
]
CREDIT = [
    "aws credit", "cloud credit", "credits for research",
    "supported by amazon", "aws research", "proof of concept credit",
]
FUTURE = ["future work", "we plan to", "in the future", "will use", "could use"]
LIST_ONLY = [
    "such as aws", "such as amazon web services", "e.g. aws",
    "providers like", "including aws", "aws, azure", "azure, aws",
    "aws, google", "google cloud, aws",
]
FALSE_POS = [
    "automatic weather station", "american welding society",
    "amazon river", "amazon forest", "amazon rainforest",
    "amazon basin", "amazon region", "mechanical turk",
]
SECONDARY = {
    "generic_cloud": ["cloud computing", "cloud platform", "cloud service"],
    "hpc": ["supercomputer", "hpc cluster", "high-performance computing",
            "high performance computing"],
    "compute_limited": ["limited compute", "computational constraints",
                        "lack of compute", "gpu memory"],
}


def classify(text):
    t = (text or "").lower()

    # false positives first
    for w in FALSE_POS:
        if w in t:
            return "M", "F", 0.9
    # credits
    if any(w in t for w in CREDIT):
        return "C", "", 0.6
    # open data
    if any(w in t for w in OPEN_DATA):
        return "D", "", 0.6
    # future work
    if any(w in t for w in FUTURE) and not any(w in t for w in USE_WORDS):
        return "M", "K", 0.6
    # real use
    if any(w in t for w in USE_WORDS):
        return "U", "", 0.6
    # list only
    if any(w in t for w in LIST_ONLY):
        return "M", "P", 0.5
    # nothing clear
    return "M", "X", 0.3


def secondary(text):
    t = (text or "").lower()
    hits = [k for k, words in SECONDARY.items() if any(w in t for w in words)]
    return ", ".join(hits)


def main():
    con = duckdb.connect(DB)
    # gather each paper's text = title + all its mention sentences
    rows = con.execute("""
        SELECT p.paper_id, p.title,
               string_agg(m.sentence, ' ') AS ev
        FROM papers_full p
        LEFT JOIN mentions m ON m.paper_id = p.paper_id
        GROUP BY p.paper_id, p.title
    """).fetchall()

    counts = {}
    for paper_id, title, ev in rows:
        text = f"{title or ''}. {ev or ''}"
        label, reason, conf = classify(text)
        sec = secondary(text)
        con.execute("""
            UPDATE papers_full
            SET label=?, m_reason=?, confidence=?, classified_by='rules',
                secondary_signal=?
            WHERE paper_id=?
        """, [label, reason, conf, sec, paper_id])
        counts[label] = counts.get(label, 0) + 1

    con.execute(f"COPY papers_full TO "
                f"'{DB.replace('.duckdb', '_papers.parquet')}' (FORMAT PARQUET)")
    print("First-pass labels (rules only — a guess, not truth):")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    con.close()


if __name__ == "__main__":
    main()
