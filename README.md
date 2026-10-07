# Dynamic Crosswalk

To support longitudinal geospatial analysis, we developed a dynamic crosswalk that maps 2010 U.S. Census tracts to 2020 tracts using population-weighted and housing-weighted conversion factors.

This repository holds the crosswalks and the validation. It states what the method is good at, what it is not, and where it will mislead you.

**Grant A. Mendoza, MPH — Central California Health Foundation**

---

## The short version

On the task this was built for — classifying tracts as inside or outside a threshold — the hybrid blend edges the static method by three hundredths of a percentage point.

On continuous variables, which is what the method actually gets used for and which it had not previously been tested on, **that advantage disappears.** The static method wins or ties every measure, and wins the one that decides funding by sixteen per cent.

Both results are reproducible from the data in this repository. Run `python3 validation/reproduce.py`.

---

## The three methods

| | how a 2010 tract's population is apportioned to its 2020 successors | file |
|---|---|---|
| **Static** | by the share of the 2010 tract's land area falling in each 2020 tract | `data/static_crosswalk.csv` |
| **Dynamic** | by annual ACS estimates for each component year | `data/dynamic_crosswalk.csv` |
| **Hybrid 70/30** | 70% static, 30% dynamic — the canonical version | `data/hybrid_70_30_crosswalk.csv` |

Two sensitivity blends are included, **90/10** and **44/56**. They are checks on the canonical weighting, not alternatives to it.

A crosswalk row is a *share*. One 2010 tract may appear on many rows, and one 2020 tract may draw from many parents. The rows under any single 2010 tract, within a single year, must sum to 1.000000.

---

## What the validation says

Every figure below is produced by `validation/reproduce.py` against the CSVs in this repository.

### 1. The static weights conserve. The hybrid's do not always.

| method | tract-years | sum to exactly 1.0 | median deviation | worst deviation |
|---|---|---|---|---|
| **static** | 80,562 | **80,012** (99.3%) | 0.000000 | **0.000298** |
| hybrid 70/30 | 80,562 | 40,024 (49.7%) | 0.000000 | **2.100000** |

The median hybrid tract-year is fine. The tail is not: a tract whose weights sum to 2.1 is not being apportioned, it is being doubled. **If you use the hybrid, check the tail before you publish the result.**

### 2. On continuous variables the hybrid's edge is gone

Estimated 2020 decennial population, reconstructed from 2010 data through the crosswalk, against what the 2020 census actually counted:

| | static | hybrid 70/30 |
|---|---|---|
| observations | 91,030 | 90,953 |
| **MAE** | **618.9** | 632.8 |
| RMSE | 1,207.8 | **1,146.8** |
| Pearson r | 0.7558 | 0.7561 |
| Spearman ρ | **0.8089** | 0.8070 |
| **wrong side of the 75th percentile** | **8,960** | 10,728 |

Static wins mean error, rank correlation and the threshold test. The hybrid wins RMSE. Pearson is a tie to four decimal places, which is to say it is noise.

**The threshold row is the one that matters**, because the threshold is what decides eligibility. The static method puts **16.4% fewer tracts on the wrong side of it.**

### 3. The error grows with the boundary, exactly as it should

Median disagreement with the 2020 actuals, by how much the tract moved:

| how much the tract moved | tract-years | median disagreement |
|---|---|---|
| did not move (1:1) | 49,362 | **4.8%** ← the floor |
| barely moved (largest piece ≥90%) | 20,490 | 16.0% |
| split (largest piece 50–90%) | 9,790 | 55.7% |
| shattered (largest piece <50%) | 420 | **89.0%** |

**The first row is not a result. It is the floor** — a tract whose boundary never moved cannot disagree because of the crosswalk, so its 4.8% is real population change. Everything above that line is the cost of the redraw.

The monotonicity is the reassuring part: the method degrades in proportion to how much it was asked to do. The uncomfortable part is how steep the curve is. **A tract that lost more than half its area to the redrawing disagrees with the census about nine times in ten.**

---

## Two things that will bite you

**`dynamic_composite_weight` is not on the same scale as the static weights.** Median sum per tract-year: **0.000138**, not 1.0. It is not a share and cannot be applied like one. The normalised columns — `norm_dynamic_pop_weight`, `norm_dynamic_housing_weight`, `norm_dynamic_composite_weight` — are the ones to use, and even those reach an exact 1.0 for only about half of tract-years.

**The `final_adjusted_*` columns and the `final_adjusted_*_new` columns are not the same thing.** The `_new` columns are the normalised versions, and they are what the validation above uses. Joining the wrong pair gives you a number that looks like a result.

---

## What is not here

The scripts that built the crosswalk are not published. The method is described above and in the write-up, and the pipeline is easily inferred from it — apportion by area, apportion by annual ACS, blend, normalise. What is published is the output and the means to check it, which is the part that was ever in doubt.

The decennial counts in `data/` are public Census Bureau data (PL 94-171 summary file, cross-checked against the API) and are included only so the validation runs without a download step.

---

## Running it

```
pip install duckdb pandas
python3 validation/reproduce.py
```

Run from the repository root. No server, no database, no load step.

---

## Citing

Mendoza, G. A. *Dynamic Crosswalk: population-weighted and housing-weighted conversion factors, 2010 to 2020 U.S. Census tracts.* Central California Health Foundation. https://github.com/Central-California-Health-Foundation/Dynamic-Crosswalk

Released under **CC BY 4.0**. Attribution is a condition of the licence, not a
courtesy: credit the author and link the repository wherever the data, the
validation or the write-up is used. The raw Census inputs are public domain;
the licence covers the derived work — the weights, the validation and the text.
