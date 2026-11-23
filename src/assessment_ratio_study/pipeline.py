"""End to end: screen sales, compute strata, run the sales-chasing check."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import chasing, strata, timeadj
from .targets import DEFAULT, Targets
from .validate import ScreenConfig, Screened, screen


@dataclass
class Result:
    screened: Screened
    strata: pd.DataFrame
    chasing: pd.DataFrame
    focus_class: str
    targets: Targets
    n_rows: int
    time_adjustment: timeadj.TimeAdjustment | None = None


def run(
    df: pd.DataFrame,
    focus_class: str = "residential",
    targets: Targets = DEFAULT,
    screen_cfg: ScreenConfig | None = None,
    time_adjust: str | float | None = None,
    valuation_date: str | None = None,
) -> Result:
    """`time_adjust`: None (off), "auto" (estimate the yearly trend), or a percent per year."""
    ta = None
    if time_adjust is not None:
        if time_adjust == "auto":
            pct, n_used = timeadj.estimate_annual_pct(df)
            method = "estimated"
        else:
            pct, n_used, method = float(time_adjust), 0, "given"
        df, ta0 = timeadj.adjust(df, pct, valuation_date)
        ta = timeadj.TimeAdjustment(ta0.annual_pct, ta0.valuation_date, method, n_used)
    sc = screen(df, screen_cfg)
    table = strata.run(sc.sales, focus_class, targets, sc.excluded)
    # Chasing uses every sold parcel in the focus class (kept or excluded), versus unsold.
    sold_all = pd.concat([sc.sales, sc.excluded.drop(columns=["reason", "ratio"])])
    focus_sold = sold_all[sold_all["property_class"] == focus_class]
    focus_unsold = sc.unsold[sc.unsold["property_class"] == focus_class]
    ch = chasing.check(focus_sold, focus_unsold)
    return Result(sc, table, ch, focus_class, targets, len(df), ta)
