#!/usr/bin/env python3
"""
Report how far the harvest got. Read-only.

Prints: papers per year, total, which years are complete, and whether
another night's run is still needed (any year with fewer than all 15
phrases done).

Run:  python src/harvest_status.py
"""
import os
import duckdb

DB = os.path.join(os.path.dirname(__file__), "..", "data", "papers.duckdb")
DB = os.path.abspath(DB)
# Project scope: 2016-2022 only (team decision).
ALL_YEARS = list(range(2016, 2023))
N_PHRASES = 15


def main():
    con = duckdb.connect(DB)
    raw = con.execute("SELECT count(*) FROM raw").fetchone()[0]
    done = {(r[0]): r[1] for r in con.execute(
        "SELECT year, count(*) FROM done GROUP BY year").fetchall()}
    per_year = {r[0]: r[1] for r in con.execute(
        "SELECT year, count(*) FROM raw GROUP BY year ORDER BY year"
    ).fetchall()}

    print("Harvest status")
    print("=" * 40)
    print(f"Raw hits total: {raw}")
    print(f"{'Year':<6}{'papers':>8}{'phrases done':>16}")
    incomplete = []
    for y in ALL_YEARS:
        pd = done.get(y, 0)
        print(f"{y:<6}{per_year.get(y,0):>8}{pd:>12}/{N_PHRASES}")
        if pd < N_PHRASES:
            incomplete.append(y)

    print("=" * 40)
    if incomplete:
        print(f"INCOMPLETE years (need another run): {incomplete}")
        print("Re-run tonight after midnight UTC:")
        print("  ./.venv/bin/python src/harvest.py --years " +
              " ".join(str(y) for y in incomplete) + " --limit 0")
    else:
        print("ALL YEARS COMPLETE. Next: load + classify + gold set.")
    con.close()


if __name__ == "__main__":
    main()
