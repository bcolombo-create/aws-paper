# AWS-in-Science: did the authors actually USE AWS?

A 2016-2026 dataset of scientific papers, labelled by whether the
authors **used Amazon Web Services** (not just mentioned it), with
a human-checked gold set and precision/recall.

Built for Group 10, Albert School x AWS.

## What this is

Full-text search of [OpenAlex](https://openalex.org) finds papers that
mention AWS. Most only mention it. We separate real **use** from
mention, keep a short **evidence sentence + link + date** for every
claim, and check a human **gold set** to measure how right we are.

Every number clicks back to evidence: open a paper, read the sentence,
follow the link, see the date it was read.

## Labels

| Label | Meaning |
|---|---|
| U | Used AWS to do the work |
| D | Used AWS open data |
| C | Got AWS credits / support |
| M | Does not count (reason: P R S K F E D X) |

Full rules: [`docs/label_guide.md`](docs/label_guide.md).

Secondary signals (recorded, never mixed into AWS counts):
generic cloud use, HPC/supercomputer, compute limits.

## Data (two tables)

- `papers_full` — one row per paper (36 fields: identity, year, venue,
  country, label, provenance, dedupe).
- `mentions` — one row per AWS mention (sentence, section, link, date).

Stored in DuckDB (`data/papers.duckdb`) and exported to Parquet.

## How to re-run (from scratch)

```bash
# 1. set up
python3 -m venv .venv
./.venv/bin/pip install duckdb requests

# 2. credentials (never committed)
cp .env.example .env     # then put your OpenAlex key + email in .env

# 3. harvest from OpenAlex (resumable; stops cleanly if daily budget runs out)
./.venv/bin/python src/harvest.py --fresh --years 2016 2017 2018 2019 2020 \
    2021 2022 2023 2024 2025 2026 --limit 0
# re-run the SAME command to resume after the budget resets (midnight UTC)

# 4. build the clean tables
./.venv/bin/python src/schema.py
./.venv/bin/python src/load_into_schema.py

# 5. first-pass labels by rules (a guess, not truth)
./.venv/bin/python src/classify_rules.py

# 6. make the human gold set (two people, same papers)
./.venv/bin/python src/label_tool.py --labeller alice --n 100
./.venv/bin/python src/label_tool.py --labeller bob   --n 100
# open http://127.0.0.1:8000 in a browser

# 7. (next) compare gold vs rules -> precision / recall
```

## Rules

- Open APIs only. OpenAlex with a free key + contact email in the
  User-Agent. One request at a time, with pauses.
- No API keys in the repo. Keys live in `.env` (git-ignored).
- We store short evidence sentences and links, never PDFs.
- We describe use; we never claim "impact".

## Status

| Part | State |
|---|---|
| Harvest pipeline | done, resumable |
| Data 2016-2022 | harvested (3,264 papers, 3,454 mentions) |
| Data 2023-2026 | pending (resume with the harvest command) |
| Schema + mentions | done |
| Rules first-pass | done |
| Labelling tool | done |
| Gold set | ready to label |
| Precision/recall | next |
| Web tool + deploy | next |

## Method version

`harvest-0.1` — recorded on every row in `method_version`.
