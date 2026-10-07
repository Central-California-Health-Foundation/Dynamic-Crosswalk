#!/usr/bin/env python3
"""
Reproduce every number in the README. Run from the repo root:

    python3 validation/reproduce.py

Needs duckdb (pip install duckdb). Reads the CSVs in data/ directly — no
server, no database, no load step.

The three tests are the only claims this repo makes about its own accuracy.
"""

import sys
from pathlib import Path

try:
    import duckdb
except ImportError:
    sys.exit("needs duckdb:  pip install duckdb")

ROOT = Path(__file__).resolve().parent.parent
con = duckdb.connect()

con.execute(f"CREATE VIEW cw_static AS SELECT * FROM read_csv_auto('{ROOT}/data/static_crosswalk.csv')")
con.execute(f"CREATE VIEW cw_hybrid AS SELECT * FROM read_csv_auto('{ROOT}/data/hybrid_70_30_crosswalk.csv')")
con.execute(f"CREATE VIEW dec2010   AS SELECT * FROM read_csv_auto('{ROOT}/data/decennial_2010_tract.csv')")
con.execute(f"CREATE VIEW dec2020   AS SELECT * FROM read_csv_auto('{ROOT}/data/decennial_2020_tract.csv')")

SEP = "=" * 78


def show(title, sql):
    print(f"\n{SEP}\n{title}\n{SEP}")
    print(con.execute(sql).df().to_string(index=False))


# ── 1. Do the weights sum to one? ────────────────────────────────────────────
# A crosswalk row is a share of a 2010 tract going to a 2020 tract, so the rows
# under any one 2010 tract, within one year, must sum to 1.000000. Anything else
# is a weight that is not a weight.
show(
    "1. WEIGHT CONSERVATION  (per 2010 tract, per year)",
    """
    with sums as (
        select 'static' as method, geoid_tract_10, year, sum(static_composite_weight) as w
        from cw_static group by 1, 2, 3
        union all
        select 'hybrid 70/30', geoid_tract_10, year, sum(final_adjusted_composite_new)
        from cw_hybrid group by 1, 2, 3
    )
    select method,
           count(*)                                                        as tract_years,
           sum(case when abs(w - 1.0) < 1e-9 then 1 else 0 end)           as exact,
           round(median(abs(w - 1.0)), 6)                                   as median_deviation,
           round(max(abs(w - 1.0)), 6)                                      as worst_deviation
    from sums group by method order by method
    """,
)

# ── 2. Continuous variables ──────────────────────────────────────────────────
# The headline test. Estimate each 2020 tract's decennial population by summing
# (2010 population x weight) over its parents, and compare against what the 2020
# census actually counted. This is the task the method was NOT validated on.
show(
    "2. CONTINUOUS VALIDATION  (estimated vs actual 2020 decennial population)",
    """
    with est as (
        select 'static' as method, c.geoid_tract_20 as b, c.year,
               sum(c.static_composite_weight * t1.pop) as e, max(t2.pop) as actual
        from cw_static c
        join dec2010 t1 on t1.geoid = c.geoid_tract_10
        join dec2020 t2 on t2.geoid = c.geoid_tract_20
        group by 2, 3, 1
        union all
        select 'hybrid 70/30', c.geoid_tract_20, c.year,
               sum(c.final_adjusted_composite_new * t1.pop), max(t2.pop)
        from cw_hybrid c
        join dec2010 t1 on t1.geoid = c.geoid_tract_10
        join dec2020 t2 on t2.geoid = c.geoid_tract_20
        group by 2, 3, 1
    ),
    ranked as (
        select method, e, actual,
               rank() over (partition by method order by e)      as rx,
               rank() over (partition by method order by actual) as ry
        from est where e is not null and actual is not null
    ),
    thr as (select method, quantile_cont(actual, 0.75) as t from ranked group by method)
    select r.method,
           count(*)                                              as n,
           round(avg(abs(r.e - r.actual)), 1)                     as mae,
           round(sqrt(avg(power(r.e - r.actual, 2))), 1)          as rmse,
           round(corr(r.e, r.actual), 4)                          as pearson_r,
           round(corr(r.rx, r.ry), 4)                             as spearman_rho,
           sum(case when (r.e > t.t) <> (r.actual > t.t) then 1 else 0 end) as wrong_side_of_p75
    from ranked r join thr t using (method)
    group by r.method
    order by mae
    """,
)

# ── 3. Does the error track the boundary? ────────────────────────────────────
# If the method is sound, a tract that did not move should be as accurate as it
# can possibly be — and the error should grow only as the boundary moves more.
# The first row is therefore the floor, not a result: it is real change.
show(
    "3. ERROR AGAINST HOW MUCH THE BOUNDARY MOVED  (static method)",
    """
    with shape as (
        select geoid_tract_10, year, max(static_composite_weight) as largest_piece, count(*) as pieces
        from cw_static group by 1, 2
    ),
    est as (
        select c.geoid_tract_10, c.year,
               sum(c.static_composite_weight * t1.pop) as e, max(t2.pop) as actual
        from cw_static c
        join dec2010 t1 on t1.geoid = c.geoid_tract_10
        join dec2020 t2 on t2.geoid = c.geoid_tract_20
        group by 1, 2
    ),
    banded as (
        select case when pieces = 1                  then '1  did not move (1:1)'
                    when largest_piece >= 0.9         then '2  barely moved (>=90%)'
                    when largest_piece >= 0.5         then '3  split (50-90%)'
                    else                                   '4  shattered (<50%)'
               end as band,
               abs(e - actual) / nullif(actual, 0) * 100 as pct
        from shape join est using (geoid_tract_10, year)
        where e is not null and actual is not null and actual > 0
    )
    select band, count(*) as n, round(median(pct), 1) as median_disagreement_pct
    from banded group by band order by band
    """,
)

print(
    "\nRows 1 and 2 of test 3 are the floor — that is real change, not method error.\n"
    "The method's cost is what the later rows add to it."
)
