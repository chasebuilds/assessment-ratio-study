"""Per-stratum statistics and pass/fail against target ranges."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import stats
from .targets import DEFAULT, Targets

COLUMNS = [
    "dimension", "stratum", "n", "median", "weighted_mean", "mean", "cod", "prd",
    "prb", "prb_ci_low", "prb_ci_high", "n_trimmed", "trim_pct", "median_ok", "cod_ok", "prd_ok", "prb_status",
    "verdict", "notes",
]  # fmt: skip

# Grouping on sale price makes PRD and PRB meaningless (the grouping variable is the
# denominator of the ratio), so those two are not computed for price strata.
PRICE_DIMS = {"price_quartile"}


def age_band(age: float) -> str:
    if np.isnan(age):
        return "unknown"
    if age < 20:
        return "0-19 yrs"
    if age < 50:
        return "20-49 yrs"
    return "50+ yrs"


def add_strata_columns(sales: pd.DataFrame) -> pd.DataFrame:
    out = sales.copy()
    if "sale_date" in out.columns and "year_built" in out.columns:
        year = pd.to_datetime(out["sale_date"], errors="coerce").dt.year
        out["age_band"] = (year - out["year_built"]).map(age_band)
    else:
        out["age_band"] = "unknown"
    return out


MAX_TRIM_PCT = 10.0


def evaluate(
    grp: pd.DataFrame,
    dimension: str,
    stratum: str,
    cls: str | None,
    t: Targets = DEFAULT,
    n_trimmed: int | None = None,
) -> dict[str, object]:
    a = grp["assessed_value"].to_numpy(dtype=float)
    s = grp["sale_price"].to_numpy(dtype=float)
    r = a / s
    n = len(grp)
    med = stats.median_ratio(r)
    cod_v = stats.cod(r)
    row: dict[str, object] = {"dimension": dimension, "stratum": stratum, "n": n}
    row["median"] = med
    row["weighted_mean"] = stats.weighted_mean_ratio(a, s)
    row["mean"] = stats.mean_ratio(r)
    row["cod"] = cod_v
    trim_pct = None if n_trimmed is None else 100.0 * n_trimmed / (n + n_trimmed)
    row["n_trimmed"] = n_trimmed
    row["trim_pct"] = trim_pct
    notes: list[str] = []
    judged = n >= t.min_sales
    if not judged:
        notes.append(f"n<{t.min_sales}: shown, not judged")

    price_dim = dimension in PRICE_DIMS
    prd_v = None if price_dim else stats.prd(a, s)
    res = None if price_dim else stats.prb(a, s)
    row["prd"] = prd_v
    row["prb"] = res.prb if res else None
    row["prb_ci_low"] = res.ci_low if res else None
    row["prb_ci_high"] = res.ci_high if res else None
    if price_dim:
        notes.append("PRD/PRB not valid when grouped by price")

    median_ok = t.median_low <= med <= t.median_high
    cod_ok = cod_v <= t.cod_limit(cls)
    if cod_v < t.cod_low:
        notes.append(f"COD below {t.cod_low}: check for sales chasing or thin data")
    prd_ok = None if prd_v is None else (t.prd_low <= prd_v <= t.prd_high)
    row["median_ok"], row["cod_ok"], row["prd_ok"] = median_ok, cod_ok, prd_ok

    if res is None:
        status = "n/a"
    elif not res.significant or abs(res.prb) <= t.prb_ok:
        status = "ok"
    elif abs(res.prb) <= t.prb_fail:
        status = "marginal"
    else:
        status = "fail"
    row["prb_status"] = status

    if not judged:
        verdict = "NOT JUDGED"
    elif not median_ok or not cod_ok or prd_ok is False or status == "fail":
        verdict = "FAIL"
    elif status == "marginal" or (trim_pct is not None and trim_pct > MAX_TRIM_PCT):
        verdict = "REVIEW"
        if trim_pct is not None and trim_pct > MAX_TRIM_PCT:
            notes.append(f"{trim_pct:.0f}% of sales trimmed as outliers: COD likely understated")
    else:
        verdict = "PASS"
    row["verdict"] = verdict
    row["notes"] = "; ".join(notes)
    return row


def _trimmed(excluded: pd.DataFrame | None, col: str | None, value: str | None) -> int:
    """Outlier-trimmed sales inside one stratum (all outliers when col is None)."""
    if excluded is None:
        return 0
    out = excluded[excluded["reason"].str.startswith("outlier")]
    if col is not None:
        out = out[out[col] == value]
    return int(len(out))


def run(
    sales: pd.DataFrame,
    focus_class: str,
    t: Targets = DEFAULT,
    excluded: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Overall, per class, then (inside `focus_class`) neighborhood, price quartile, age band."""
    sales = add_strata_columns(sales)
    rows = [evaluate(sales, "overall", "all sales", None, t, _trimmed(excluded, None, None))]
    for cls, g in sales.groupby("property_class"):
        rows.append(
            evaluate(
                g,
                "property_class",
                str(cls),
                str(cls),
                t,
                _trimmed(excluded, "property_class", str(cls)),
            )
        )
    focus = sales[sales["property_class"] == focus_class].copy()
    if len(focus):
        for nb, g in focus.groupby("neighborhood"):
            rows.append(
                evaluate(
                    g,
                    "neighborhood",
                    str(nb),
                    focus_class,
                    t,
                    _trimmed(excluded, "neighborhood", str(nb)),
                )
            )
        focus["price_quartile"] = pd.qcut(
            focus["sale_price"], 4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"]
        )
        for q, g in focus.groupby("price_quartile", observed=True):
            rows.append(evaluate(g, "price_quartile", str(q), focus_class, t))
        for band, g in focus.groupby("age_band"):
            if band != "unknown":
                rows.append(evaluate(g, "age_band", str(band), focus_class, t))
    return pd.DataFrame(rows, columns=COLUMNS)
